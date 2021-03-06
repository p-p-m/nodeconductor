from django.db import transaction
from django.db.models import signals

from nodeconductor.quotas import models, utils
from nodeconductor.quotas.log import alert_logger, event_logger


def add_quotas_to_scope(sender, instance, created=False, **kwargs):
    if created:
        from nodeconductor.quotas import models
        for quota_name in sender.QUOTAS_NAMES:
            models.Quota.objects.create(name=quota_name, scope=instance)


def quantity_quota_handler_factory(path_to_quota_scope, quota_name, count=1):
    """
    Return signal handler that increases or decreases quota usage by <count> on object creation or deletion

    :param path_to_quota_scope: path to object with quotas from created object
    :param quota_name: name of changed quota
    :param count: value, that will be added to quota usage

    Example.
    This code will add 1 to customer "nc_resource_count" quotas on instance creation and remove 1 on instance deletion:

    .. code-block:: python

        # handlers.py:

        change_customer_nc_instances_quota = quotas_handlers.quantity_quota_handler_factory(
            path_to_quota_scope='cloud_project_membership.project.customer',
            quota_name='nc_resource_count',
            count=1,
        )

        # apps.py

        signals.post_save.connect(
            handlers.change_customer_nc_instances_quota,
            sender=Instance,
            dispatch_uid='nodeconductor.iaas.handlers.increase_customer_nc_instances_quota',
        )

        signals.post_delete.connect(
            handlers.change_customer_nc_instances_quota,
            sender=Instance,
            dispatch_uid='nodeconductor.iaas.handlers.decrease_customer_nc_instances_quota',
        )

    """
    def handler(sender, instance, **kwargs):
        signal = kwargs['signal']
        assert signal in (signals.post_save, signals.post_delete), \
            '"quantity_quota_handler" can be used only with post_delete or post_save signals'

        scope = reduce(getattr, path_to_quota_scope.split("."), instance)
        if signal == signals.post_save and kwargs.get('created'):
            scope.add_quota_usage(quota_name, count)
        elif signal == signals.post_delete:
            scope.add_quota_usage(quota_name, -count, fail_silently=True)
            # fail silently is enabled for cascade deletion case:
            # if quotas can be deleted before other related objects

    return handler


def check_quota_threshold_breach(sender, instance, **kwargs):
    # XXX: This import creates circular dependency between quotas and structure
    from nodeconductor.structure.models import ServiceProjectLink

    quota = instance
    alert_threshold = 0.8

    if quota.scope is not None:
        if quota.is_exceeded(threshold=alert_threshold):
            alert_logger.quota.warning(
                'Quota {quota_name} is over threshold. Limit: {quota_limit}, usage: {quota_usage}',
                scope=quota.scope,
                alert_type='quota_usage_is_over_threshold',
                alert_context={
                    'quota': quota
                })

            if quota.scope in ServiceProjectLink.get_all_models():
                spl = quota.scope
                event_logger.quota.warning(
                    '{quota_name} quota threshold has been reached for project {project_name}.',
                    event_type='quota_threshold_reached',
                    event_context={
                        'quota': quota,
                        'service': spl.service,
                        'project': spl.project,
                        'project_group': spl.project.project_groups.first(),
                        'threshold': alert_threshold * quota.limit,
                    })
        else:
            alert_logger.quota.close(scope=quota.scope, alert_type='quota_usage_is_over_threshold')


def reset_quota_values_to_zeros_before_delete(sender, instance=None, **kwargs):
    quotas_scope = instance
    quotas_names = quotas_scope.quotas.values_list('name', flat=True)
    for name in quotas_names:
        quotas_scope.set_quota_usage(name, 0)


def create_global_quotas(**kwargs):
    for model in utils.get_models_with_quotas():
        if hasattr(model, 'GLOBAL_COUNT_QUOTA_NAME'):
            models.Quota.objects.get_or_create(name=getattr(model, 'GLOBAL_COUNT_QUOTA_NAME'))


def increase_global_quota(sender, instance=None, created=False, **kwargs):
    if created and hasattr(sender, 'GLOBAL_COUNT_QUOTA_NAME'):
        with transaction.atomic():
            global_quota = models.Quota.objects.select_for_update().get(
                name=getattr(sender, 'GLOBAL_COUNT_QUOTA_NAME'))
            global_quota.usage += 1
            global_quota.save()


def decrease_global_quota(sender, **kwargs):
    if hasattr(sender, 'GLOBAL_COUNT_QUOTA_NAME'):
        with transaction.atomic():
            global_quota = models.Quota.objects.select_for_update().get(
                name=getattr(sender, 'GLOBAL_COUNT_QUOTA_NAME'))
            global_quota.usage -= 1
            global_quota.save()
