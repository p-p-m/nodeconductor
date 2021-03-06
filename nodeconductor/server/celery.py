from __future__ import absolute_import

import os

from celery import Celery
from celery import signals
from django.conf import settings

from nodeconductor.logging.middleware import get_event_context, set_event_context, reset_event_context

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nodeconductor.server.settings')  # XXX:

app = Celery('nodeconductor')

# Using a string here means the worker will not have to
# pickle the object when using Windows.
app.config_from_object('django.conf:settings')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)


class PriorityRouter(object):
    """ Run heavy tasks in a separate queue.
        One must supply is_heavy_task=True as a keyword argument to task decorator.
    """
    def route_for_task(self, task_name, *args, **kwargs):
        task = app.tasks.get(task_name)
        if getattr(task, 'is_heavy_task', False):
            return {'queue': 'heavy'}
        return None


# The workflow for passing event context to background tasks works as following:
# 1) Generate event context at CaptureEventContextMiddleware and bind it to local thread
# 2) At the Django side: fetch event context from local thread and pass it as parameter to task
# 3) At Celery worker side: fetch event context from task and bind it to local thread
@signals.before_task_publish.connect
def pass_event_context(sender=None, body=None, **kwargs):
    if body is None:
        return

    event_context = get_event_context()
    if event_context:
        body['kwargs']['event_context'] = event_context


@signals.task_prerun.connect
def bind_event_context(sender=None, **kwargs):
    try:
        event_context = kwargs['kwargs'].pop('event_context')
    except KeyError:
        return

    set_event_context(event_context)


@signals.task_postrun.connect
def unbind_event_context(sender=None, **kwargs):
    reset_event_context()
