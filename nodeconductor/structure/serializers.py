from __future__ import unicode_literals

from collections import OrderedDict
from django.core.validators import RegexValidator, MaxLengthValidator
from django.contrib import auth
from django.db import models as django_models
from django.conf import settings
from django.utils import six
from django.utils.encoding import force_text
from rest_framework import exceptions, metadata, serializers
from rest_framework.reverse import reverse

from nodeconductor.core import serializers as core_serializers
from nodeconductor.core import models as core_models
from nodeconductor.core import utils as core_utils
from nodeconductor.core.tasks import send_task
from nodeconductor.core.fields import MappedChoiceField
from nodeconductor.quotas import serializers as quotas_serializers
from nodeconductor.structure import models, SupportedServices
from nodeconductor.structure.managers import filter_queryset_for_user


User = auth.get_user_model()


class IpCountValidator(MaxLengthValidator):
    message = 'Only %(limit_value)s ip address is supported.'


class PermissionFieldFilteringMixin(object):
    """
    Mixin allowing to filter related fields.

    In order to constrain the list of entities that can be used
    as a value for the field:

    1. Make sure that the entity in question has corresponding
       Permission class defined.

    2. Implement `get_filtered_field_names()` method
       in the class that this mixin is mixed into and return
       the field in question from that method.
    """
    def get_fields(self):
        fields = super(PermissionFieldFilteringMixin, self).get_fields()

        try:
            request = self.context['request']
            user = request.user
        except (KeyError, AttributeError):
            return fields

        for field_name in self.get_filtered_field_names():
            fields[field_name].queryset = filter_queryset_for_user(
                fields[field_name].queryset, user)

        return fields

    def get_filtered_field_names(self):
        raise NotImplementedError(
            'Implement get_filtered_field_names() '
            'to return list of filtered fields')


class BasicUserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = User
        fields = ('url', 'uuid', 'username', 'full_name', 'native_name',)
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }


class BasicProjectSerializer(core_serializers.BasicInfoSerializer):
    class Meta(core_serializers.BasicInfoSerializer.Meta):
        model = models.Project
        fields = ('url', 'uuid', 'name')


class BasicProjectGroupSerializer(core_serializers.BasicInfoSerializer):
    class Meta(core_serializers.BasicInfoSerializer.Meta):
        model = models.ProjectGroup
        fields = ('url', 'name', 'uuid')
        read_only_fields = ('name', 'uuid')


class NestedProjectGroupSerializer(core_serializers.HyperlinkedRelatedModelSerializer):
    class Meta(object):
        model = models.ProjectGroup
        fields = ('url', 'name', 'uuid')
        read_only_fields = ('name', 'uuid')
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }


class NestedServiceProjectLinkSerializer(serializers.Serializer):
    uuid = serializers.ReadOnlyField(source='service.uuid')
    url = serializers.SerializerMethodField()
    service_project_link_url = serializers.SerializerMethodField()
    name = serializers.ReadOnlyField(source='service.name')
    type = serializers.SerializerMethodField()
    state = serializers.ReadOnlyField(source='get_state_display')
    resources_count = serializers.SerializerMethodField(source='get_resources_count')
    shared = serializers.SerializerMethodField()
    settings_uuid = serializers.ReadOnlyField(source='service.settings.uuid')

    def get_url(self, link):
        """
        URL of service
        """
        view_name = SupportedServices.get_detail_view_for_model(link.service)
        return reverse(view_name, kwargs={'uuid': link.service.uuid.hex}, request=self.context['request'])

    def get_service_project_link_url(self, link):
        view_name = SupportedServices.get_detail_view_for_model(link)
        return reverse(view_name, kwargs={'pk': link.id}, request=self.context['request'])

    def get_type(self, link):
        return SupportedServices.get_name_for_model(link.service)

    def get_shared(self, link):
        # XXX: Backward compatibility with IAAS Cloud
        try:
            return link.service.settings.shared
        except AttributeError:
            return False

    def get_resources_count(self, link):
        """
        Count total number of all resources connected to link
        """
        total = 0
        for model in SupportedServices.get_service_resources(link.service):
            # Format query path from resource to service project link
            query = {model.Permissions.project_path.split('__')[0]: link}
            total += model.objects.filter(**query).count()
        return total


class ProjectSerializer(PermissionFieldFilteringMixin,
                        core_serializers.DynamicSerializer,
                        core_serializers.AugmentedSerializerMixin,
                        serializers.HyperlinkedModelSerializer):
    project_groups = NestedProjectGroupSerializer(
        queryset=models.ProjectGroup.objects.all(),
        many=True,
        required=False,
        default=(),
    )

    quotas = quotas_serializers.QuotaSerializer(many=True, read_only=True)
    # These fields exist for backward compatibility
    resource_quota = serializers.SerializerMethodField('get_resource_quotas')
    resource_quota_usage = serializers.SerializerMethodField('get_resource_quotas_usage')

    services = NestedServiceProjectLinkSerializer(source='get_links', many=True, read_only=True)

    app_count = serializers.SerializerMethodField()
    vm_count = serializers.SerializerMethodField()

    class Meta(object):
        model = models.Project
        fields = (
            'url', 'uuid',
            'name',
            'customer', 'customer_uuid', 'customer_name', 'customer_native_name', 'customer_abbreviation',
            'project_groups',
            'description',
            'quotas',
            'services',
            'resource_quota', 'resource_quota_usage',
            'created',
            'app_count', 'vm_count'
        )
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
            'customer': {'lookup_field': 'uuid'},
        }
        related_paths = {
            'customer': ('uuid', 'name', 'native_name', 'abbreviation')
        }

    def create(self, validated_data):
        project_groups = validated_data.pop('project_groups')
        project = super(ProjectSerializer, self).create(validated_data)
        project.project_groups.add(*project_groups)

        return project

    def get_resource_quotas(self, obj):
        return models.Project.get_sum_of_quotas_as_dict(
            [obj], ['ram', 'storage', 'max_instances', 'vcpu'], fields=['limit'])

    def get_resource_quotas_usage(self, obj):
        quota_values = models.Project.get_sum_of_quotas_as_dict(
            [obj], ['ram', 'storage', 'max_instances', 'vcpu'], fields=['usage'])
        # No need for '_usage' suffix in quotas names
        return {
            key[:-6]: value for key, value in quota_values.iteritems()
        }

    def get_filtered_field_names(self):
        return 'customer',

    def get_app_count(self, project):
        resources = models.Resource.get_all_models()
        return sum(resource.objects.filter(project=project).count()
                   for resource in resources
                   if not issubclass(resource, models.VirtualMachineMixin))

    def get_vm_count(self,  project):
        resources = models.Resource.get_all_models()
        return sum(resource.objects.filter(project=project).count()
                   for resource in resources
                   if issubclass(resource, models.VirtualMachineMixin))

    def update(self, instance, validated_data):
        if 'project_groups' in validated_data:
            project_groups = validated_data.pop('project_groups')
            instance.project_groups.clear()
            instance.project_groups.add(*project_groups)
        return super(ProjectSerializer, self).update(instance, validated_data)


class DefaultImageField(serializers.ImageField):
    def to_representation(self, image):
        if image:
            return super(DefaultImageField, self).to_representation(image)
        else:
            return settings.NODECONDUCTOR.get('DEFAULT_CUSTOMER_LOGO')


class CustomerImageSerializer(serializers.ModelSerializer):
    image = serializers.ImageField()

    class Meta:
        model = models.Customer
        fields = ['image']


class CustomerSerializer(core_serializers.DynamicSerializer,
                         core_serializers.AugmentedSerializerMixin,
                         serializers.HyperlinkedModelSerializer,):
    projects = serializers.SerializerMethodField()
    project_groups = serializers.SerializerMethodField()
    owners = BasicUserSerializer(source='get_owners', many=True, read_only=True)
    image = DefaultImageField(required=False, read_only=True)
    quotas = quotas_serializers.QuotaSerializer(many=True, read_only=True)

    class Meta(object):
        model = models.Customer
        fields = (
            'url',
            'uuid',
            'name', 'native_name', 'abbreviation', 'contact_details',
            'projects', 'project_groups',
            'owners', 'balance',
            'registration_code',
            'quotas',
            'image'
        )
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }
        # Balance should be modified by nodeconductor_paypal app
        read_only_fields = ('balance', )

    def _get_filtered_data(self, objects, serializer):
        try:
            user = self.context['request'].user
            queryset = filter_queryset_for_user(objects, user)
        except (KeyError, AttributeError):
            queryset = objects.all()

        serializer_instance = serializer(queryset, many=True, context=self.context)
        return serializer_instance.data

    def get_projects(self, obj):
        return self._get_filtered_data(obj.projects.all(), BasicProjectSerializer)

    def get_project_groups(self, obj):
        return self._get_filtered_data(obj.project_groups.all(), BasicProjectGroupSerializer)


class BalanceHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.BalanceHistory
        fields = ['created', 'amount']


class ProjectGroupSerializer(PermissionFieldFilteringMixin,
                             core_serializers.AugmentedSerializerMixin,
                             serializers.HyperlinkedModelSerializer):
    projects = serializers.SerializerMethodField()

    class Meta(object):
        model = models.ProjectGroup
        fields = (
            'url',
            'uuid',
            'name',
            'customer', 'customer_name', 'customer_native_name', 'customer_abbreviation',
            'projects',
            'description',
        )
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
            'customer': {'lookup_field': 'uuid'},
        }
        related_paths = {
            'customer': ('uuid', 'name', 'native_name', 'abbreviation')
        }

    def get_filtered_field_names(self):
        return 'customer',

    def get_fields(self):
        # TODO: Extract to a proper mixin
        fields = super(ProjectGroupSerializer, self).get_fields()

        try:
            method = self.context['view'].request.method
        except (KeyError, AttributeError):
            return fields

        if method in ('PUT', 'PATCH'):
            fields['customer'].read_only = True

        return fields

    def _get_filtered_data(self, objects, serializer):
        # XXX: this method completely duplicates _get_filtered_data in CustomerSerializer.
        # We need to create mixin to follow DRY principle. (NC-578)
        try:
            user = self.context['request'].user
            queryset = filter_queryset_for_user(objects, user)
        except (KeyError, AttributeError):
            queryset = objects.all()

        serializer_instance = serializer(queryset, many=True, context=self.context)
        return serializer_instance.data

    def get_projects(self, obj):
        return self._get_filtered_data(obj.projects.all(), BasicProjectSerializer)


class ProjectGroupMembershipSerializer(PermissionFieldFilteringMixin,
                                       serializers.HyperlinkedModelSerializer):
    project_group = serializers.HyperlinkedRelatedField(
        source='projectgroup',
        view_name='projectgroup-detail',
        lookup_field='uuid',
        queryset=models.ProjectGroup.objects.all(),
    )
    project_group_name = serializers.ReadOnlyField(source='projectgroup.name')
    project = serializers.HyperlinkedRelatedField(
        view_name='project-detail',
        lookup_field='uuid',
        queryset=models.Project.objects.all(),
    )
    project_name = serializers.ReadOnlyField(source='project.name')

    class Meta(object):
        model = models.ProjectGroup.projects.through
        fields = (
            'url',
            'project_group', 'project_group_name',
            'project', 'project_name',
        )
        view_name = 'projectgroup_membership-detail'

    def get_filtered_field_names(self):
        return 'project', 'project_group'


STRUCTURE_PERMISSION_USER_FIELDS = {
    'fields': ('user', 'user_full_name', 'user_native_name', 'user_username', 'user_uuid', 'user_email'),
    'path': ('username', 'full_name', 'native_name', 'uuid', 'email')
}


class CustomerPermissionSerializer(PermissionFieldFilteringMixin,
                                   core_serializers.AugmentedSerializerMixin,
                                   serializers.HyperlinkedModelSerializer):
    customer = serializers.HyperlinkedRelatedField(
        source='group.customerrole.customer',
        view_name='customer-detail',
        lookup_field='uuid',
        queryset=models.Customer.objects.all(),
    )

    role = MappedChoiceField(
        source='group.customerrole.role_type',
        choices=(
            ('owner', 'Owner'),
        ),
        choice_mappings={
            'owner': models.CustomerRole.OWNER,
        },
    )

    class Meta(object):
        model = User.groups.through
        fields = (
            'url', 'pk', 'role',
            'customer', 'customer_uuid', 'customer_name', 'customer_native_name', 'customer_abbreviation',
        ) + STRUCTURE_PERMISSION_USER_FIELDS['fields']
        related_paths = {
            'user': STRUCTURE_PERMISSION_USER_FIELDS['path'],
            'group.customerrole.customer': ('name', 'native_name', 'abbreviation', 'uuid')
        }
        extra_kwargs = {
            'user': {
                'view_name': 'user-detail',
                'lookup_field': 'uuid',
                'queryset': User.objects.all(),
            },
        }
        view_name = 'customer_permission-detail'

    def create(self, validated_data):
        customer = validated_data['customer']
        user = validated_data['user']
        role = validated_data['role']

        permission, _ = customer.add_user(user, role)

        return permission

    def to_internal_value(self, data):
        value = super(CustomerPermissionSerializer, self).to_internal_value(data)
        return {
            'user': value['user'],
            'customer': value['group']['customerrole']['customer'],
            'role': value['group']['customerrole']['role_type'],
        }

    def validate(self, data):
        customer = data['customer']
        user = data['user']
        role = data['role']

        if customer.has_user(user, role):
            raise serializers.ValidationError('The fields customer, user, role must make a unique set.')

        return data

    def get_filtered_field_names(self):
        return 'customer',


class ProjectPermissionSerializer(PermissionFieldFilteringMixin,
                                  core_serializers.AugmentedSerializerMixin,
                                  serializers.HyperlinkedModelSerializer):
    project = serializers.HyperlinkedRelatedField(
        source='group.projectrole.project',
        view_name='project-detail',
        lookup_field='uuid',
        queryset=models.Project.objects.all(),
    )

    role = MappedChoiceField(
        source='group.projectrole.role_type',
        choices=(
            ('admin', 'Administrator'),
            ('manager', 'Manager'),
        ),
        choice_mappings={
            'admin': models.ProjectRole.ADMINISTRATOR,
            'manager': models.ProjectRole.MANAGER,
        },
    )

    class Meta(object):
        model = User.groups.through
        fields = (
            'url', 'pk',
            'role',
            'project', 'project_uuid', 'project_name',
        ) + STRUCTURE_PERMISSION_USER_FIELDS['fields']

        related_paths = {
            'group.projectrole.project': ('name', 'uuid'),
            'user': STRUCTURE_PERMISSION_USER_FIELDS['path']
        }
        extra_kwargs = {
            'user': {
                'view_name': 'user-detail',
                'lookup_field': 'uuid',
                'queryset': User.objects.all(),
            },
        }
        view_name = 'project_permission-detail'

    def create(self, validated_data):
        project = validated_data['project']
        user = validated_data['user']
        role = validated_data['role']

        permission, _ = project.add_user(user, role)

        return permission

    def to_internal_value(self, data):
        value = super(ProjectPermissionSerializer, self).to_internal_value(data)
        return {
            'user': value['user'],
            'project': value['group']['projectrole']['project'],
            'role': value['group']['projectrole']['role_type'],
        }

    def validate(self, data):
        project = data['project']
        user = data['user']
        role = data['role']

        if project.has_user(user, role):
            raise serializers.ValidationError('The fields project, user, role must make a unique set.')

        return data

    def get_filtered_field_names(self):
        return 'project',


class ProjectGroupPermissionSerializer(PermissionFieldFilteringMixin,
                                       core_serializers.AugmentedSerializerMixin,
                                       serializers.HyperlinkedModelSerializer):
    project_group = serializers.HyperlinkedRelatedField(
        source='group.projectgrouprole.project_group',
        view_name='projectgroup-detail',
        lookup_field='uuid',
        queryset=models.ProjectGroup.objects.all(),
    )

    role = MappedChoiceField(
        source='group.projectgrouprole.role_type',
        choices=(
            ('manager', 'Manager'),
        ),
        choice_mappings={
            'manager': models.ProjectGroupRole.MANAGER,
        },
    )

    class Meta(object):
        model = User.groups.through
        fields = (
            'url', 'pk',
            'role',
            'project_group', 'project_group_uuid', 'project_group_name',
        ) + STRUCTURE_PERMISSION_USER_FIELDS['fields']
        related_paths = {
            'user': STRUCTURE_PERMISSION_USER_FIELDS['path'],
            'group.projectgrouprole.project_group': ('name', 'uuid'),
        }
        extra_kwargs = {
            'user': {
                'view_name': 'user-detail',
                'lookup_field': 'uuid',
                'queryset': User.objects.all(),
            },
        }
        view_name = 'projectgroup_permission-detail'

    def create(self, validated_data):
        project_group = validated_data['project_group']
        user = validated_data['user']
        role = validated_data['role']

        permission, _ = project_group.add_user(user, role)

        return permission

    def to_internal_value(self, data):
        value = super(ProjectGroupPermissionSerializer, self).to_internal_value(data)
        return {
            'user': value['user'],
            'project_group': value['group']['projectgrouprole']['project_group'],
            'role': value['group']['projectgrouprole']['role_type'],
        }

    def validate(self, data):
        project_group = data['project_group']
        user = data['user']
        role = data['role']

        if project_group.has_user(user, role):
            raise serializers.ValidationError('The fields project_group, user, role must make a unique set.')

        return data

    def get_filtered_field_names(self):
        return 'project_group',


class UserOrganizationSerializer(serializers.Serializer):
    organization = serializers.CharField(max_length=80)


class UserSerializer(serializers.HyperlinkedModelSerializer):
    email = serializers.EmailField()

    class Meta(object):
        model = User
        fields = (
            'url',
            'uuid', 'username',
            'full_name', 'native_name',
            'job_title', 'email', 'phone_number',
            'organization', 'organization_approved',
            'civil_number',
            'description',
            'is_staff', 'is_active',
            'date_joined',
        )
        read_only_fields = (
            'uuid',
            'civil_number',
            'organization',
            'organization_approved',
            'date_joined',
        )
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }

    def get_fields(self):
        fields = super(UserSerializer, self).get_fields()

        try:
            request = self.context['view'].request
            user = request.user
        except (KeyError, AttributeError):
            return fields

        if not user.is_staff:
            del fields['is_active']
            del fields['is_staff']
            fields['description'].read_only = True

        if request.method in ('PUT', 'PATCH'):
            fields['username'].read_only = True

        return fields

    def validate(self, attrs):
        user = User(id=getattr(self.instance, 'id', None), **attrs)
        user.clean()
        return attrs


class CreationTimeStatsSerializer(serializers.Serializer):
    MODEL_NAME_CHOICES = (('project', 'project'), ('customer', 'customer'), ('project_group', 'project_group'))
    MODEL_CLASSES = {'project': models.Project, 'customer': models.Customer, 'project_group': models.ProjectGroup}

    model_name = serializers.ChoiceField(choices=MODEL_NAME_CHOICES)
    start_timestamp = serializers.IntegerField(min_value=0)
    end_timestamp = serializers.IntegerField(min_value=0)
    segments_count = serializers.IntegerField(min_value=0)

    def get_stats(self, user):
        start_datetime = core_utils.timestamp_to_datetime(self.data['start_timestamp'])
        end_datetime = core_utils.timestamp_to_datetime(self.data['end_timestamp'])

        model = self.MODEL_CLASSES[self.data['model_name']]
        filtered_queryset = filter_queryset_for_user(model.objects.all(), user)
        created_datetimes = (
            filtered_queryset
            .filter(created__gte=start_datetime, created__lte=end_datetime)
            .values('created')
            .annotate(count=django_models.Count('id', distinct=True)))

        time_and_value_list = [
            (core_utils.datetime_to_timestamp(dt['created']), dt['count']) for dt in created_datetimes]

        return core_utils.format_time_and_value_to_segment_list(
            time_and_value_list, self.data['segments_count'],
            self.data['start_timestamp'], self.data['end_timestamp'])


class PasswordSerializer(serializers.Serializer):
    password = serializers.CharField(min_length=7, validators=[
        RegexValidator(
            regex='\d',
            message='Ensure this field has at least one digit.',
        ),
        RegexValidator(
            regex='[a-zA-Z]',
            message='Ensure this field has at least one latin letter.',
        ),
    ])


class SshKeySerializer(serializers.HyperlinkedModelSerializer):
    user_uuid = serializers.ReadOnlyField(source='user.uuid')

    class Meta(object):
        model = core_models.SshPublicKey
        fields = ('url', 'uuid', 'name', 'public_key', 'fingerprint', 'user_uuid')
        read_only_fields = ('fingerprint',)
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }

    def validate(self, attrs):
        try:
            fingerprint = core_models.get_ssh_key_fingerprint(attrs['public_key'])
        except (IndexError, TypeError):
            raise serializers.ValidationError('Key is not valid: cannot generate fingerprint from it.')
        if core_models.SshPublicKey.objects.filter(fingerprint=fingerprint).exists():
            raise serializers.ValidationError('Key with same fingerprint already exists')
        return attrs

    def get_fields(self):
        fields = super(SshKeySerializer, self).get_fields()

        try:
            user = self.context['request'].user
        except (KeyError, AttributeError):
            return fields

        if not user.is_staff:
            del fields['user_uuid']

        return fields


class ServiceSettingsSerializer(PermissionFieldFilteringMixin,
                                core_serializers.AugmentedSerializerMixin,
                                serializers.HyperlinkedModelSerializer):

    customer_native_name = serializers.ReadOnlyField(source='customer.native_name')
    state = MappedChoiceField(
        choices=[(v, k) for k, v in core_models.SynchronizationStates.CHOICES],
        choice_mappings={v: k for k, v in core_models.SynchronizationStates.CHOICES},
        read_only=True)

    class Meta(object):
        model = models.ServiceSettings
        fields = (
            'url', 'uuid', 'name', 'type', 'state', 'error_message', 'shared',
            'backend_url', 'username', 'password', 'token', 'certificate',
            'customer', 'customer_name', 'customer_native_name',
            'dummy'
        )
        protected_fields = ('type', 'customer')
        read_only_fields = ('shared', 'state', 'error_message')
        write_only_fields = ('backend_url', 'username', 'token', 'password', 'certificate')
        related_paths = ('customer',)
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
            'customer': {'lookup_field': 'uuid'},
        }

    def get_filtered_field_names(self):
        return 'customer',

    def get_fields(self):
        fields = super(ServiceSettingsSerializer, self).get_fields()
        request = self.context['request']

        if isinstance(self.instance, self.Meta.model):
            perm = 'structure.change_%s' % self.Meta.model._meta.model_name
            if request.user.has_perms([perm], self.instance):
                # If user can change settings he should be able to see value
                for field in self.Meta.write_only_fields:
                    fields[field].write_only = False

                serializer = self.get_service_serializer()

                # Remove fields if they are not needed for service
                filter_fields = serializer.SERVICE_ACCOUNT_FIELDS
                if filter_fields is not NotImplemented:
                    for field in self.Meta.write_only_fields:
                        if field in filter_fields:
                            fields[field].help_text = filter_fields[field]
                        elif field in fields:
                            del fields[field]

                # Add extra fields stored in options dictionary
                extra_fields = serializer.SERVICE_ACCOUNT_EXTRA_FIELDS
                if extra_fields is not NotImplemented:
                    for field in extra_fields:
                        fields[field] = serializers.CharField(required=False,
                                                              source='options.' + field,
                                                              allow_blank=True,
                                                              help_text=extra_fields[field])

        if request.method == 'GET':
            fields['type'] = serializers.ReadOnlyField(source='get_type_display')

        return fields

    def get_service_serializer(self):
        # Find service serializer by service type of settings object
        return next(cls for cls in BaseServiceSerializer.__subclasses__()
                    if cls.SERVICE_TYPE == self.instance.type)


class ServiceSerializerMetaclass(serializers.SerializerMetaclass):
    """ Build a list of supported services via serializers definition.
        See SupportedServices for details.
    """
    def __new__(cls, name, bases, args):
        service_type = args.get('SERVICE_TYPE', NotImplemented)
        SupportedServices.register_service(service_type, args['Meta'])
        return super(ServiceSerializerMetaclass, cls).__new__(cls, name, bases, args)


class BaseServiceSerializer(six.with_metaclass(ServiceSerializerMetaclass,
                            PermissionFieldFilteringMixin,
                            core_serializers.AugmentedSerializerMixin,
                            serializers.HyperlinkedModelSerializer)):

    SERVICE_TYPE = NotImplemented
    SERVICE_ACCOUNT_FIELDS = NotImplemented
    SERVICE_ACCOUNT_EXTRA_FIELDS = NotImplemented

    projects = BasicProjectSerializer(many=True, read_only=True)
    customer_native_name = serializers.ReadOnlyField(source='customer.native_name')
    settings = serializers.HyperlinkedRelatedField(
        queryset=models.ServiceSettings.objects.filter(shared=True),
        view_name='servicesettings-detail',
        lookup_field='uuid',
        allow_null=True)

    backend_url = serializers.URLField(max_length=200, allow_null=True, write_only=True, required=False)
    username = serializers.CharField(max_length=100, allow_null=True, write_only=True, required=False)
    password = serializers.CharField(max_length=100, allow_null=True, write_only=True, required=False)
    token = serializers.CharField(allow_null=True, write_only=True, required=False)
    certificate = serializers.FileField(allow_null=True, write_only=True, required=False)
    dummy = serializers.BooleanField(write_only=True, required=False)
    resources_count = serializers.SerializerMethodField()
    service_type = serializers.SerializerMethodField()
    shared = serializers.ReadOnlyField(source='settings.shared')
    state = serializers.SerializerMethodField()
    error_message = serializers.ReadOnlyField(source='settings.error_message')

    class Meta(object):
        model = NotImplemented
        view_name = NotImplemented
        fields = (
            'uuid',
            'url',
            'name', 'projects',
            'customer', 'customer_name', 'customer_native_name',
            'settings', 'dummy',
            'backend_url', 'username', 'password', 'token', 'certificate',
            'resources_count', 'service_type', 'shared', 'state', 'error_message'
        )
        settings_fields = ('backend_url', 'username', 'password', 'token', 'certificate')
        protected_fields = ('customer', 'settings', 'dummy') + settings_fields
        related_paths = ('customer',)
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
            'customer': {'lookup_field': 'uuid'},
            'settings': {'lookup_field': 'uuid'},
        }

    def __new__(cls, *args, **kwargs):
        if cls.SERVICE_ACCOUNT_EXTRA_FIELDS is not NotImplemented:
            cls.Meta.fields += tuple(cls.SERVICE_ACCOUNT_EXTRA_FIELDS.keys())
            cls.Meta.protected_fields += tuple(cls.SERVICE_ACCOUNT_EXTRA_FIELDS.keys())
        return super(BaseServiceSerializer, cls).__new__(cls, *args, **kwargs)

    def get_filtered_field_names(self):
        return 'customer',

    def get_fields(self):
        fields = super(BaseServiceSerializer, self).get_fields()
        if self.SERVICE_TYPE is not NotImplemented:
            fields['settings'].queryset = fields['settings'].queryset.filter(type=self.SERVICE_TYPE)

        if self.SERVICE_ACCOUNT_FIELDS is not NotImplemented:
            for field in self.Meta.settings_fields:
                if field in self.SERVICE_ACCOUNT_FIELDS:
                    fields[field].help_text = self.SERVICE_ACCOUNT_FIELDS[field]
                else:
                    del fields[field]

        return fields

    def build_unknown_field(self, field_name, model_class):
        if self.SERVICE_ACCOUNT_EXTRA_FIELDS is not NotImplemented:
            if field_name in self.SERVICE_ACCOUNT_EXTRA_FIELDS:
                return serializers.CharField, {
                    'write_only': True,
                    'required': False,
                    'allow_blank': True,
                    'help_text': self.SERVICE_ACCOUNT_EXTRA_FIELDS[field_name]}

        return super(BaseServiceSerializer, self).build_unknown_field(field_name, model_class)

    def validate_empty_values(self, data):
        # required=False is ignored for settings FK, deal with it here
        if 'settings' not in data:
            data['settings'] = None
        return super(BaseServiceSerializer, self).validate_empty_values(data)

    def validate(self, attrs):
        user = self.context['user']
        customer = attrs.get('customer') or self.instance.customer
        settings = attrs.get('settings')
        if not user.is_staff:
            if not customer.has_user(user, models.CustomerRole.OWNER):
                raise exceptions.PermissionDenied()
            if not self.instance and settings and not settings.shared:
                if attrs.get('customer') != settings.customer:
                    raise serializers.ValidationError('Customer must match settings customer.')

        if self.context['request'].method == 'POST':
            # Make shallow copy to protect from mutations
            settings_fields = self.Meta.settings_fields[:]
            create_settings = any([attrs.get(f) for f in settings_fields])
            if not settings and not create_settings:
                raise serializers.ValidationError(
                    "Either service settings or credentials must be supplied.")

            extra_fields = tuple()
            if self.SERVICE_ACCOUNT_EXTRA_FIELDS is not NotImplemented:
                extra_fields += tuple(self.SERVICE_ACCOUNT_EXTRA_FIELDS.keys())

            settings_fields += 'dummy',
            if create_settings:
                args = {f: attrs.get(f) for f in settings_fields if f in attrs}
                if extra_fields:
                    args['options'] = {f: attrs[f] for f in extra_fields if f in attrs}

                settings = models.ServiceSettings.objects.create(
                    type=self.SERVICE_TYPE,
                    name=attrs['name'],
                    customer=customer,
                    **args)
                attrs['settings'] = settings

            for f in settings_fields + extra_fields:
                if f in attrs:
                    del attrs[f]

        return attrs

    def get_resources_count(self, obj):
        resources_count = 0
        resource_models = SupportedServices.get_service_resources(obj)
        for resource_model in resource_models:
            # Format query path to service project link
            query = {resource_model.Permissions.project_path.split('__')[0] + '__service': obj}
            resources_count += resource_model.objects.filter(**query).count()
        return resources_count

    def get_service_type(self, obj):
        return SupportedServices.get_name_for_model(obj)

    def get_state(self, obj):
        return obj.settings.get_state_display()


class BaseServiceProjectLinkSerializer(PermissionFieldFilteringMixin,
                                       core_serializers.AugmentedSerializerMixin,
                                       serializers.HyperlinkedModelSerializer):

    project = serializers.HyperlinkedRelatedField(
        queryset=models.Project.objects.all(),
        view_name='project-detail',
        lookup_field='uuid')

    state = MappedChoiceField(
        choices=[(v, k) for k, v in core_models.SynchronizationStates.CHOICES],
        choice_mappings={v: k for k, v in core_models.SynchronizationStates.CHOICES},
        read_only=True)

    class Meta(object):
        model = NotImplemented
        view_name = NotImplemented
        fields = (
            'url',
            'project', 'project_name', 'project_uuid',
            'service', 'service_name', 'service_uuid',
            'state', 'error_message'
        )
        related_paths = ('project', 'service')
        read_only_fields = ('error_message',)
        extra_kwargs = {
            'service': {'lookup_field': 'uuid', 'view_name': NotImplemented},
        }

    def get_filtered_field_names(self):
        return 'project', 'service'

    def validate(self, attrs):
        if attrs['service'].customer != attrs['project'].customer:
            raise serializers.ValidationError("Service customer doesn't match project customer")

        # XXX: Consider adding unique key (service, project) to the model instead
        if self.Meta.model.objects.filter(service=attrs['service'], project=attrs['project']).exists():
            raise serializers.ValidationError("This service project link already exists")

        return attrs


class ResourceSerializerMetaclass(serializers.SerializerMetaclass):
    """ Build a list of supported resource via serializers definition.
        See SupportedServices for details.
    """
    def __new__(cls, name, bases, args):
        SupportedServices.register_resource(args.get('service'), args['Meta'])
        return super(ResourceSerializerMetaclass, cls).__new__(cls, name, bases, args)


class BasicResourceSerializer(serializers.Serializer):
    uuid = serializers.ReadOnlyField()
    name = serializers.ReadOnlyField()

    project_name = serializers.ReadOnlyField(source='service_project_link.project.name')
    project_uuid = serializers.ReadOnlyField(source='service_project_link.project.uuid')

    customer_uuid = serializers.ReadOnlyField(source='service_project_link.project.customer.uuid')
    customer_name = serializers.ReadOnlyField(source='service_project_link.project.customer.name')

    resource_type = serializers.SerializerMethodField()

    def get_resource_type(self, resource):
        return SupportedServices.get_name_for_model(resource)


class BaseResourceSerializer(six.with_metaclass(ResourceSerializerMetaclass,
                             PermissionFieldFilteringMixin,
                             core_serializers.AugmentedSerializerMixin,
                             serializers.HyperlinkedModelSerializer)):

    state = serializers.ReadOnlyField(source='get_state_display')
    project_groups = BasicProjectGroupSerializer(
        source='service_project_link.project.project_groups', many=True, read_only=True)

    project = serializers.HyperlinkedRelatedField(
        source='service_project_link.project',
        view_name='project-detail',
        read_only=True,
        lookup_field='uuid')

    project_name = serializers.ReadOnlyField(source='service_project_link.project.name')
    project_uuid = serializers.ReadOnlyField(source='service_project_link.project.uuid')

    service_project_link = serializers.HyperlinkedRelatedField(
        view_name=NotImplemented,
        queryset=NotImplemented,
        write_only=True)

    service = serializers.HyperlinkedRelatedField(
        source='service_project_link.service',
        view_name=NotImplemented,
        read_only=True,
        lookup_field='uuid')

    service_name = serializers.ReadOnlyField(source='service_project_link.service.name')
    service_uuid = serializers.ReadOnlyField(source='service_project_link.service.uuid')

    customer = serializers.HyperlinkedRelatedField(
        source='service_project_link.project.customer',
        view_name='customer-detail',
        read_only=True,
        lookup_field='uuid')

    customer_name = serializers.ReadOnlyField(source='service_project_link.project.customer.name')
    customer_abbreviation = serializers.ReadOnlyField(source='service_project_link.project.customer.abbreviation')
    customer_native_name = serializers.ReadOnlyField(source='service_project_link.project.customer.native_name')

    created = serializers.DateTimeField(read_only=True)
    resource_type = serializers.SerializerMethodField()

    class Meta(object):
        model = NotImplemented
        view_name = NotImplemented
        fields = (
            'url', 'uuid', 'name', 'description', 'start_time',
            'service', 'service_name', 'service_uuid',
            'project', 'project_name', 'project_uuid',
            'customer', 'customer_name', 'customer_native_name', 'customer_abbreviation',
            'project_groups', 'error_message',
            'resource_type', 'state', 'created', 'service_project_link',
        )
        protected_fields = ('service', 'service_project_link')
        read_only_fields = ('start_time', 'error_message')
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }

    def get_filtered_field_names(self):
        return 'service_project_link',

    def get_resource_type(self, obj):
        return SupportedServices.get_name_for_model(obj)

    def to_representation(self, instance):
        # We need this hook, because ips have to be represented as list
        if hasattr(instance, 'external_ips'):
            instance.external_ips = [instance.external_ips] if instance.external_ips else []
        if hasattr(instance, 'internal_ips'):
            instance.internal_ips = [instance.internal_ips] if instance.internal_ips else []
        return super(BaseResourceSerializer, self).to_representation(instance)

    def get_resource_fields(self):
        return self.Meta.model._meta.get_all_field_names()

    def create(self, validated_data):
        data = validated_data.copy()
        fields = self.get_resource_fields()
        # Remove `virtual` properties which ain't actually belong to the model
        for prop in data.keys():
            if prop not in fields:
                del data[prop]

        return super(BaseResourceSerializer, self).create(data)


class BaseResourceImportSerializer(PermissionFieldFilteringMixin,
                                   serializers.HyperlinkedModelSerializer):

    backend_id = serializers.CharField(write_only=True)
    project = serializers.HyperlinkedRelatedField(
        queryset=models.Project.objects.all(),
        view_name='project-detail',
        lookup_field='uuid',
        write_only=True)

    state = serializers.ReadOnlyField(source='get_state_display')
    created = serializers.DateTimeField(read_only=True)

    class Meta(object):
        model = NotImplemented
        view_name = NotImplemented
        fields = (
            'url', 'uuid', 'name', 'state', 'created',
            'backend_id', 'project'
        )
        read_only_fields = ('name',)
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }

    def get_filtered_field_names(self):
        return 'project',

    def get_fields(self):
        fields = super(BaseResourceImportSerializer, self).get_fields()
        fields['project'].queryset = self.context['service'].projects.all()
        return fields

    def run_validation(self, data):
        validated_data = super(BaseResourceImportSerializer, self).run_validation(data)

        if self.Meta.model.objects.filter(backend_id=validated_data['backend_id']).exists():
            raise serializers.ValidationError(
                {'backend_id': "This resource is already linked to NodeConductor"})

        spl_class = SupportedServices.get_related_models(self.Meta.model)['service_project_link']
        spl = spl_class.objects.get(service=self.context['service'], project=validated_data['project'])

        if spl.state == core_models.SynchronizationStates.ERRED:
            raise serializers.ValidationError(
                {'project': "Service project link must be in non-erred state"})

        validated_data['service_project_link'] = spl

        return validated_data


class VirtualMachineSerializer(BaseResourceSerializer):

    external_ips = serializers.ListField(
        child=core_serializers.IPAddressField(),
        read_only=True,
    )
    internal_ips = serializers.ListField(
        child=core_serializers.IPAddressField(),
        read_only=True,
    )

    ssh_public_key = serializers.HyperlinkedRelatedField(
        view_name='sshpublickey-detail',
        lookup_field='uuid',
        queryset=core_models.SshPublicKey.objects.all(),
        required=False,
        write_only=True)

    class Meta(BaseResourceSerializer.Meta):
        read_only_fields = ('start_time', 'cores', 'ram', 'disk', 'external_ips', 'internal_ips')
        protected_fields = BaseResourceSerializer.Meta.protected_fields + (
            'user_data', 'ssh_public_key'
        )
        write_only_fields = ('user_data',)
        fields = BaseResourceSerializer.Meta.fields + (
            'cores', 'ram', 'disk', 'ssh_public_key', 'user_data', 'external_ips', 'internal_ips',
        )

    def get_fields(self):
        fields = super(VirtualMachineSerializer, self).get_fields()
        fields['ssh_public_key'].queryset = fields['ssh_public_key'].queryset.filter(
            user=self.context['user'])
        return fields


class PropertySerializerMetaclass(serializers.SerializerMetaclass):
    """ Build a list of supported properties via serializers definition.
        See SupportedServices for details.
    """
    def __new__(cls, name, bases, args):
        service_type = args.get('SERVICE_TYPE', NotImplemented)
        SupportedServices.register_property(service_type, args['Meta'])
        return super(PropertySerializerMetaclass, cls).__new__(cls, name, bases, args)


class BasePropertySerializer(six.with_metaclass(PropertySerializerMetaclass,
                             serializers.HyperlinkedModelSerializer)):

    SERVICE_TYPE = NotImplemented

    class Meta(object):
        model = NotImplemented


class AggregateSerializer(serializers.Serializer):
    MODEL_NAME_CHOICES = (
        ('project', 'project'),
        ('customer', 'customer'),
        ('project_group', 'project_group')
    )
    MODEL_CLASSES = {
        'project': models.Project,
        'customer': models.Customer,
        'project_group': models.ProjectGroup,
    }

    aggregate = serializers.ChoiceField(choices=MODEL_NAME_CHOICES, default='customer')
    uuid = serializers.CharField(allow_null=True, default=None)

    def get_aggregates(self, user):
        model = self.MODEL_CLASSES[self.data['aggregate']]
        queryset = filter_queryset_for_user(model.objects.all(), user)

        if 'uuid' in self.data and self.data['uuid']:
            queryset = queryset.filter(uuid=self.data['uuid'])
        return queryset

    def get_projects(self, user):
        queryset = self.get_aggregates(user)

        if self.data['aggregate'] == 'project':
            return queryset.all()
        elif self.data['aggregate'] == 'project_group':
            queryset = models.Project.objects.filter(project_groups__in=list(queryset))
            return filter_queryset_for_user(queryset, user)
        else:
            queryset = models.Project.objects.filter(customer__in=list(queryset))
            return filter_queryset_for_user(queryset, user)


class ResourceProvisioningMetadata(metadata.SimpleMetadata):
    """
    Difference from SimpleMetadata class:
    1) Skip read-only fields, because options are used only for provisioning new resource.
    2) Don't expose choices for fields with queryset in order to reduce size of response.
    """
    def get_serializer_info(self, serializer):
        """
        Given an instance of a serializer, return a dictionary of metadata
        about its fields.
        """
        if hasattr(serializer, 'child'):
            # If this is a `ListSerializer` then we want to examine the
            # underlying child serializer instance instead.
            serializer = serializer.child
        return OrderedDict([
            (field_name, self.get_field_info(field))
            for field_name, field in serializer.fields.items()
            if not getattr(field, 'read_only', False)
        ])

    def get_field_info(self, field):
        """
        Given an instance of a serializer field, return a dictionary
        of metadata about it.
        """
        field_info = OrderedDict()
        field_info['type'] = self.label_lookup[field]
        field_info['required'] = getattr(field, 'required', False)

        attrs = [
            'read_only', 'label', 'help_text',
            'min_length', 'max_length',
            'min_value', 'max_value'
        ]

        for attr in attrs:
            value = getattr(field, attr, None)
            if value is not None and value != '':
                field_info[attr] = force_text(value, strings_only=True)

        if not field_info.get('read_only') and hasattr(field, 'choices') \
           and not hasattr(field, 'queryset'):
            field_info['choices'] = [
                {
                    'value': choice_value,
                    'display_name': force_text(choice_name, strings_only=True)
                }
                for choice_value, choice_name in field.choices.items()
            ]

        return field_info
