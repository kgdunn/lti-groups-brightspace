# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-04-05 20:17
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('formation', '0007_tracking'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tracking',
            name='action',
            field=models.CharField(choices=[('create', 'create'), ('login', 'login'), ('join', 'group-join'), ('leave', 'group-leave'), ('waitlist-add', 'waitlist-add'), ('waitlist-left', 'waitlist-left')], max_length=80),
        ),
    ]
