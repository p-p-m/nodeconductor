from operator import or_

from django.db import models


def filter_queryset_for_user(queryset, user):
    filtered_relations = ('customer', 'project', 'project_group')

    if user is None or user.is_staff:
        return queryset

    def create_q(entity):
        try:
            path = getattr(permissions, '%s_path' % entity)
        except AttributeError:
            return None

        role = getattr(permissions, '%s_role' % entity, None)

        if path == 'self':
            prefix = ''
        else:
            prefix = path + '__'

        kwargs = {
            prefix + 'roles__permission_group__user': user,
        }

        if role:
            kwargs[prefix + 'roles__role_type'] = role

        return models.Q(**kwargs)

    try:
        permissions = queryset.model.Permissions
    except AttributeError:
        return queryset

    q_objects = [q_object for q_object in (
        create_q(entity) for entity in filtered_relations
    ) if q_object is not None]

    try:
        # Add extra query which basically allows to
        # additionally filter by some flag and ignore permissions
        extra_q = getattr(permissions, 'extra_query')
    except AttributeError:
        pass
    else:
        q_objects.append(models.Q(**extra_q))

    try:
        # Whether both customer and project filtering requested?
        any_of_q = reduce(or_, q_objects)
        return queryset.filter(any_of_q).distinct()
    except TypeError:
        # Or any of customer and project filtering requested?
        return queryset.filter(q_objects[0])
    except IndexError:
        # Looks like no filters are there
        return queryset


class StructureQueryset(models.QuerySet):
    """ Provides additional filtering by customer or project (based on permission definition).

        Example:

            .. code-block:: python

                Instance.objects.filter(project=12)

                Droplet.objects.filter(
                    customer__name__startswith='A',
                    state=Droplet.States.ONLINE)

                Droplet.objects.filter(Q(customer__name='Alice') | Q(customer__name='Bob'))
    """

    def exclude(self, *args, **kwargs):
        return super(StructureQueryset, self).exclude(
            *[self._patch_query_argument(a) for a in args],
            **self._filter_by_custom_fields(**kwargs))

    def filter(self, *args, **kwargs):
        return super(StructureQueryset, self).filter(
            *[self._patch_query_argument(a) for a in args],
            **self._filter_by_custom_fields(**kwargs))

    def _patch_query_argument(self, arg):
        # patch Q() objects if passed and add support of custom fields
        if isinstance(arg, models.Q):
            children = []
            for opt in arg.children:
                if isinstance(opt, models.Q):
                    children.append(self._patch_query_argument(opt))
                else:
                    args = self._filter_by_custom_fields(**dict([opt]))
                    children.append(tuple(args.items())[0])
            arg.children = children
        return arg

    def _filter_by_custom_fields(self, **kwargs):
        # traverse over filter arguments in search of custom fields
        args = {}
        fields = self.model._meta.get_all_field_names()
        for field, val in kwargs.items():
            base_field = field.split('__')[0]
            if base_field in fields:
                args.update(**{field: val})
            elif base_field in ('customer', 'project'):
                args.update(self._filter_by_permission_fields(base_field, field, val))
            else:
                args.update(**{field: val})

        return args

    def _filter_by_permission_fields(self, name, field, value):
        # handle fields connected via permissions relations
        extra = '__'.join(field.split('__')[1:]) if '__' in field else None
        try:
            # look for the target field path in Permissions class,
            path = getattr(self.model.Permissions, '%s_path' % name)
        except AttributeError:
            # fallback to FieldError if it's missed
            return {field: value}
        else:
            if path == 'self':
                if extra:
                    return {extra: value}
                else:
                    return {'pk': value.pk if isinstance(value, models.Model) else value}
            else:
                if extra:
                    path += '__' + extra
                return {path: value}


StructureManager = models.Manager.from_queryset(StructureQueryset)
