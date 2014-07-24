from rest_framework import filters
from rest_framework import viewsets

from nodeconductor.cloud import models
from nodeconductor.cloud import serializers
from nodeconductor.core import permissions


class FlavorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Flavor.objects.all()
    serializer_class = serializers.FlavorSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.DjangoObjectPermissionsFilter,)
    permission_classes = (permissions.DjangoObjectLevelPermissions,)


class OpenStackCloudViewSet(viewsets.ModelViewSet):
    queryset = models.OpenStackCloud.objects.all()
    serializer_class = serializers.OpenStackCloudSerializer
    lookup_field = 'uuid'
