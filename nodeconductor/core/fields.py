from __future__ import unicode_literals

import re
import json

from django.db import models
from django.core import validators
from rest_framework import serializers
import six

from nodeconductor.core.validators import validate_cron_schedule
from nodeconductor.core import utils


# XXX: This field is left only for migrations compatibility.
# It has to be removed after migrations compression
class CronScheduleBaseField(models.CharField):
    pass


class CronScheduleField(models.CharField):
    description = "A cron schedule in textual form"

    def __init__(self, *args, **kwargs):
        kwargs['validators'] = [validate_cron_schedule]
        kwargs['max_length'] = kwargs.get('max_length', 15)
        super(CronScheduleField, self).__init__(*args, **kwargs)


comma_separated_string_list_re = re.compile('^((\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(,\s+)?)+')
validate_comma_separated_string_list = validators.RegexValidator(comma_separated_string_list_re,
                                                                 'Enter ips separated by commas.', 'invalid')


class IPsField(models.CharField):
    default_validators = [validate_comma_separated_string_list]
    description = 'Comma-separated ips'

    def formfield(self, **kwargs):
        defaults = {
            'error_messages': {
                'invalid': 'Enter ips separated by commas.',
            }
        }
        defaults.update(kwargs)
        return super(IPsField, self).formfield(**defaults)


class MappedChoiceField(serializers.ChoiceField):
    """
    A choice field that maps enum values from representation to model ones and back.

    :Example:

    >>> # models.py
    >>> class IceCream(models.Model):
    >>>     class Meta:
    >>>         app_label = 'myapp'
    >>>
    >>>     CHOCOLATE = 0
    >>>     VANILLA = 1
    >>>
    >>>     FLAVOR_CHOICES = (
    >>>         (CHOCOLATE, _('Chocolate')),
    >>>         (VANILLA, _('Vanilla')),
    >>>     )
    >>>
    >>>     flavor = models.SmallIntegerField(choices=FLAVOR_CHOICES)
    >>>
    >>> # serializers.py
    >>> class IceCreamSerializer(serializers.ModelSerializer):
    >>>     class Meta:
    >>>         model = IceCream
    >>>
    >>>     flavor = MappedChoiceField(
    >>>         choices={
    >>>             'chocolate': _('Chocolate'),
    >>>             'vanilla': _('Vanilla'),
    >>>         },
    >>>         choice_mappings={
    >>>             'chocolate': IceCream.CHOCOLATE,
    >>>             'vanilla': IceCream.VANILLA,
    >>>         },
    >>>     )
    >>>
    >>> model1 = IceCream(flavor=IceCream.CHOCOLATE)
    >>> serializer1 = IceCreamSerializer(instance=model1)
    >>> serializer1.data
    {'flavor': 'chocolate', u'id': None}
    >>>
    >>> data2 = {'flavor': 'vanilla'}
    >>> serializer2 = IceCreamSerializer(data=data2)
    >>> serializer2.is_valid()
    True
    >>> serializer2.validated_data["flavor"] == IceCream.VANILLA
    True
    """
    def __init__(self, choice_mappings, **kwargs):
        super(MappedChoiceField, self).__init__(**kwargs)

        assert set(self.choices.keys()) == set(choice_mappings.keys()), 'Choices do not match mappings'
        assert len(set(choice_mappings.values())) == len(choice_mappings), 'Mappings are not unique'

        self.mapped_to_model = choice_mappings
        self.model_to_mapped = {v: k for k, v in six.iteritems(choice_mappings)}

    def to_internal_value(self, data):
        if data == '' and self.allow_blank:
            return ''

        data = super(MappedChoiceField, self).to_internal_value(data)

        try:
            return self.mapped_to_model[six.text_type(data)]
        except KeyError:
            self.fail('invalid_choice', input=data)

    def to_representation(self, value):
        if value in ('', None):
            return value

        value = self.model_to_mapped[value]

        return super(MappedChoiceField, self).to_representation(value)


class JsonField(serializers.Field):
    """
    A read-write DRF field for the jsonfield.JSONField objects.
    """

    def to_representation(self, obj):
        return obj if obj != "" else None

    def to_internal_value(self, data):
        try:
            data = json.loads(data)
        except ValueError:
            raise serializers.ValidationError('This field should a be valid JSON string.')
        return data


class TimestampField(serializers.Field):
    """
    Unix timestamp field mapped to datetime object.
    """
    def to_representation(self, value):
        return utils.datetime_to_timestamp(value)

    def to_internal_value(self, value):
        try:
            return utils.timestamp_to_datetime(value)
        except ValueError:
            raise serializers.ValidationError('Value "{}" should be valid UNIX timestamp.'.format(value))
