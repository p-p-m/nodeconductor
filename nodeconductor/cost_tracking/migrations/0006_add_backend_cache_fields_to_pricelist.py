# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0001_initial'),
        ('cost_tracking', '0005_expand_item_type_size'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='defaultpricelistitem',
            name='service_content_type',
        ),
        migrations.AddField(
            model_name='defaultpricelistitem',
            name='backend_choice_id',
            field=models.CharField(max_length=255, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='defaultpricelistitem',
            name='backend_option_id',
            field=models.CharField(max_length=255, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='defaultpricelistitem',
            name='backend_product_id',
            field=models.CharField(max_length=255, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='defaultpricelistitem',
            name='resource_content_type',
            field=models.ForeignKey(default=None, to='contenttypes.ContentType'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='pricelistitem',
            name='resource_content_type',
            field=models.ForeignKey(related_name='+', default=None, to='contenttypes.ContentType'),
            preserve_default=True,
        ),
    ]
