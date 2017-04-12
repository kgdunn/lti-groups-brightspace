# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-04-12 13:48
from __future__ import unicode_literals

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('formation', '0010_group_formation_process_dt_group_selection_stops'),
    ]

    operations = [
        migrations.AddField(
            model_name='group_formation_process',
            name='setup_mode',
            field=models.BooleanField(default=True, help_text='When the group settings are still being added/edited; outside of `setup_mode` it is not possible to update the group names and descriptions anymore.'),
        ),
        migrations.AlterField(
            model_name='group_formation_process',
            name='dt_group_selection_stops',
            field=models.DateTimeField(default=datetime.datetime(2050, 12, 31, 23, 59, 59, 999999), verbose_name='When does group enrolment stop?'),
        ),
    ]