from rest_framework import serializers

from nodeconductor.quotas import models, utils
from nodeconductor.core.serializers import GenericRelatedField


class QuotaSerializer(serializers.HyperlinkedModelSerializer):
    owner = GenericRelatedField(related_models=utils.get_models_with_quotas())

    class Meta(object):
        model = models.BackupSchedule
        fields = ('url', 'uuid', 'name', 'limit', 'usage', 'owner')
        read_only_fields = ('owner', )
        lookup_field = 'uuid'

    # TODO: cleanup after migration to drf 3
    def validate(self, attrs):
        from nodeconductor.structure.serializers import fix_non_nullable_attrs
        return fix_non_nullable_attrs(attrs)

