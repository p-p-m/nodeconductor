from __future__ import unicode_literals

import django.contrib.auth
import factory

from nodeconductor.structure import models


class UserFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = django.contrib.auth.get_user_model()

    username = factory.Sequence(lambda n: 'john%s' % n)
    email = factory.LazyAttribute(lambda o: '%s@example.org' % o.username)
    first_name = 'John'
    last_name = 'Doe'
    is_staff = False
    is_active = True
    is_superuser = False

    @factory.post_generation
    def organizations(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            for organization in extracted:
                self.organizations.add(organization)


class OrganizationFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Organization

    name = factory.Sequence(lambda n: 'Org%s' % n)
    abbreviation = factory.LazyAttribute(lambda o: o.name[:5])
    contact_details = factory.Sequence(lambda n: 'contacts %s' % n)


class ProjectFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Project

    name = factory.Sequence(lambda n: 'Proj%s' % n)
    organization = factory.SubFactory(OrganizationFactory)

    @factory.post_generation
    def cloud(self, create, extracted, **kwargs):
        if create and extracted:
            self.clouds.add(extracted)

    @factory.post_generation
    def clouds(self, create, extracted, **kwargs):
        if create and extracted:
            for cloud in extracted:
                self.clouds.add(cloud)