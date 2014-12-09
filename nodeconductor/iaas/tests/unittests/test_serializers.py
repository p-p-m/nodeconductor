from django.test import TestCase

from nodeconductor.iaas import serializers
from nodeconductor.iaas.tests import factories
from nodeconductor.structure.tests import factories as structure_factories


class InstanceCreateSerializerTest(TestCase):

    def setUp(self):
        user = structure_factories.UserFactory()
        self.serializer = serializers.InstanceCreateSerializer(context={'user': user})

    def test_validate_security_groups(self):
        # if security groups is none - they have to be deleted from attrs
        attrs = {'security_groups': None}
        attr_name = 'security_groups'
        self.serializer.validate_security_groups(attrs, attr_name)
        self.assertEqual(len(attrs), 0)
        # all ok:
        attrs = {'security_groups': [{'name': factories.SecurityGroupFactory().name}]}
        self.serializer.validate_security_groups(attrs, attr_name)
        self.assertIn('security_groups', attrs)
