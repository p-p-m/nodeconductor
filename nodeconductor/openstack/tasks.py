import logging

from celery import shared_task, chain

from nodeconductor.core.tasks import save_error_message, transition, throttle
from nodeconductor.core.models import SynchronizationStates
from nodeconductor.openstack.backend import OpenStackBackendError
from nodeconductor.openstack.models import OpenStackServiceProjectLink, Instance, SecurityGroup
from nodeconductor.structure.models import ServiceSettings
from nodeconductor.structure.tasks import (
    begin_syncing_service_project_links, sync_service_project_link_succeeded, sync_service_project_link_failed)


logger = logging.getLogger(__name__)


@shared_task(name='nodeconductor.openstack.provision')
def provision(instance_uuid, **kwargs):
    instance = Instance.objects.get(uuid=instance_uuid)
    spl = instance.service_project_link
    if spl.state == SynchronizationStates.NEW:
        # Sync NEW SPL before instance provision
        spl.schedule_creating()
        spl.save()
        begin_syncing_service_project_links.apply_async(
            args=(spl.to_string(),),
            kwargs={'initial': True, 'transition_method': 'begin_creating'},
            link=chain(sync_service_project_link_succeeded.si(spl.to_string()),
                       provision.si(instance_uuid, **kwargs)),
            link_error=chain(sync_service_project_link_failed.si(spl.to_string()),
                             set_erred.si(instance_uuid)),
        )
    else:
        provision_instance.apply_async(
            args=(instance_uuid,),
            kwargs=kwargs,
            link=set_online.si(instance_uuid),
            link_error=set_erred.si(instance_uuid)
        )


@shared_task(name='nodeconductor.openstack.destroy')
def destroy(instance_uuid, transition_entity=None):
    destroy_instance.apply_async(
        args=(instance_uuid,),
        link=delete.si(instance_uuid),
        link_error=set_erred.si(instance_uuid))


@shared_task(name='nodeconductor.openstack.start')
def start(instance_uuid):
    start_instance.apply_async(
        args=(instance_uuid,),
        link=set_online.si(instance_uuid),
        link_error=set_erred.si(instance_uuid))


@shared_task(name='nodeconductor.openstack.stop')
def stop(instance_uuid):
    stop_instance.apply_async(
        args=(instance_uuid,),
        link=set_offline.si(instance_uuid),
        link_error=set_erred.si(instance_uuid))


@shared_task(name='nodeconductor.openstack.restart')
def restart(instance_uuid):
    restart_instance.apply_async(
        args=(instance_uuid,),
        link=set_online.si(instance_uuid),
        link_error=set_erred.si(instance_uuid))


@shared_task(name='nodeconductor.openstack.remove_tenant')
def remove_tenant(settings_uuid, tenant_id):
    settings = ServiceSettings.objects.get(uuid=settings_uuid)
    backend = settings.get_backend(tenant_id=tenant_id)
    backend.cleanup(dryrun=False)


@shared_task(name='nodeconductor.openstack.sync_instance_security_groups')
def sync_instance_security_groups(instance_uuid):
    instance = Instance.objects.get(uuid=instance_uuid)
    backend = instance.get_backend()
    backend.sync_instance_security_groups(instance)


@shared_task(name='nodeconductor.openstack.sync_security_group')
@transition(SecurityGroup, 'begin_syncing')
def sync_security_group(security_group_uuid, action, transition_entity=None):
    security_group = transition_entity
    backend = security_group.service_project_link.get_backend()

    @transition(SecurityGroup, 'set_in_sync')
    def succeeded(security_group_uuid, transition_entity=None):
        pass

    @transition(SecurityGroup, 'set_erred')
    def failed(security_group_uuid, transition_entity=None):
        pass

    try:
        func = getattr(backend, '%s_security_group' % action)
        func(security_group)
    except:
        failed(security_group_uuid)
        raise
    else:
        if action == 'delete':
            security_group.delete()
        else:
            succeeded(security_group_uuid)


@shared_task(name='nodeconductor.openstack.sync_external_network')
def sync_external_network(service_project_link_str, action, data=()):
    service_project_link = next(OpenStackServiceProjectLink.from_string(service_project_link_str))
    backend = service_project_link.get_backend()

    try:
        func = getattr(backend, '%s_external_network' % action)
        func(service_project_link, **data)
    except OpenStackBackendError:
        logger.warning(
            "Failed to %s external network for service project link %s.",
            action, service_project_link_str)


@shared_task(name='nodeconductor.openstack.allocate_floating_ip')
def allocate_floating_ip(service_project_link_str):
    service_project_link = next(OpenStackServiceProjectLink.from_string(service_project_link_str))
    backend = service_project_link.get_backend()

    try:
        backend.allocate_floating_ip_address(service_project_link)
    except OpenStackBackendError:
        logger.warning(
            "Failed to allocate floating IP for service project link %s.",
            service_project_link_str)


@shared_task
def assign_floating_ip(instance_uuid, floating_ip_uuid):
    instance = Instance.objects.get(uuid=instance_uuid)
    floating_ip = instance.service_project_link.floating_ips.get(uuid=floating_ip_uuid)
    backend = instance.cloud.get_backend()

    try:
        backend.assign_floating_ip_to_instance(instance, floating_ip)
    except OpenStackBackendError:
        logger.warning("Failed to assign floating IP to the instance with id %s.", instance_uuid)


@shared_task(is_heavy_task=True)
@transition(Instance, 'begin_provisioning')
@save_error_message
def provision_instance(instance_uuid, transition_entity=None, **kwargs):
    instance = transition_entity
    with throttle(key=instance.service_project_link.service.settings.backend_url):
        backend = instance.get_backend()
        backend.provision_instance(instance, **kwargs)


@shared_task
@transition(Instance, 'begin_starting')
@save_error_message
def start_instance(instance_uuid, transition_entity=None):
    instance = transition_entity
    backend = instance.get_backend()
    backend._old_backend.start_instance(instance)


@shared_task
@transition(Instance, 'begin_stopping')
@save_error_message
def stop_instance(instance_uuid, transition_entity=None):
    instance = transition_entity
    backend = instance.get_backend()
    backend._old_backend.stop_instance(instance)


@shared_task
@transition(Instance, 'begin_restarting')
@save_error_message
def restart_instance(instance_uuid, transition_entity=None):
    instance = transition_entity
    backend = instance.get_backend()
    backend._old_backend.restart_instance(instance)


@shared_task
@transition(Instance, 'begin_deleting')
@save_error_message
def destroy_instance(instance_uuid, transition_entity=None):
    instance = transition_entity
    backend = instance.get_backend()
    backend.delete_instance(instance)


@shared_task
@transition(Instance, 'set_online')
def set_online(instance_uuid, transition_entity=None):
    pass


@shared_task
@transition(Instance, 'set_offline')
def set_offline(instance_uuid, transition_entity=None):
    pass


@shared_task
@transition(Instance, 'set_erred')
def set_erred(instance_uuid, transition_entity=None):
    pass


@shared_task
def delete(instance_uuid):
    Instance.objects.get(uuid=instance_uuid).delete()


# Security-group related methods
# XXX: copy-paste from iaas.tasks.security_groups
@shared_task(name='nodeconductor.openstack.create_security_group')
@transition(SecurityGroup, 'begin_syncing')
def create_security_group(security_group_uuid, transition_entity=None):
    security_group = transition_entity

    openstack_create_security_group.apply_async(
        args=(security_group.uuid.hex,),
        link=security_group_sync_succeeded.si(security_group_uuid),
        link_error=security_group_sync_failed.si(security_group_uuid),
    )


@shared_task(name='nodeconductor.openstack.update_security_group')
@transition(SecurityGroup, 'begin_syncing')
def update_security_group(security_group_uuid, transition_entity=None):
    security_group = transition_entity

    openstack_update_security_group.apply_async(
        args=(security_group.uuid.hex,),
        link=security_group_sync_succeeded.si(security_group_uuid),
        link_error=security_group_sync_failed.si(security_group_uuid),
    )


@shared_task(name='nodeconductor.openstack.delete_security_group')
@transition(SecurityGroup, 'begin_syncing')
def delete_security_group(security_group_uuid, transition_entity=None):
    security_group = transition_entity

    openstack_delete_security_group.apply_async(
        args=(security_group.uuid.hex,),
        link=security_group_deletion_succeeded.si(security_group_uuid),
        link_error=security_group_sync_failed.si(security_group_uuid),
    )


@shared_task
@transition(SecurityGroup, 'set_in_sync')
def security_group_sync_succeeded(security_group_uuid, transition_entity=None):
    pass


@shared_task
@transition(SecurityGroup, 'set_erred')
def security_group_sync_failed(security_group_uuid, transition_entity=None):
    pass


@shared_task
def security_group_deletion_succeeded(security_group_uuid):
    SecurityGroup.objects.filter(uuid=security_group_uuid).delete()


@shared_task
def openstack_create_security_group(security_group_uuid):
    security_group = SecurityGroup.objects.get(uuid=security_group_uuid)
    backend = security_group.service_project_link.get_backend()
    backend.create_security_group(security_group)


@shared_task
def openstack_update_security_group(security_group_uuid):
    security_group = SecurityGroup.objects.get(uuid=security_group_uuid)
    backend = security_group.service_project_link.get_backend()
    backend.update_security_group(security_group)


@shared_task
def openstack_delete_security_group(security_group_uuid):
    security_group = SecurityGroup.objects.get(uuid=security_group_uuid)
    backend = security_group.service_project_link.get_backend()
    backend.delete_security_group(security_group)
