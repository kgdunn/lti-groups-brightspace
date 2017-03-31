# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-03-30 20:41
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('formation', '0003_allowed'),
    ]

    operations = [
        migrations.AddField(
            model_name='group_formation_process',
            name='allow_multi_enrol',
            field=models.BooleanField(default=False, help_text='If True, the student can be in more than 1 group in this category.'),
        ),
    ]
