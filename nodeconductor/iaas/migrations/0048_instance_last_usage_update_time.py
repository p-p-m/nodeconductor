# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0047_refactor_application_type_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='instance',
            name='last_usage_update_time',
            field=models.DateTimeField(null=True, blank=True),
            preserve_default=True,
        ),
    ]
