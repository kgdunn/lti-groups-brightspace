# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-03-30 18:13
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Course',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=300, verbose_name='Course name')),
                ('label', models.CharField(help_text="Obtain this from the HTML POST field: 'context_id' ", max_length=300, verbose_name='LTI POST label')),
                ('offering', models.PositiveIntegerField(blank=True, default='0000', help_text='Which year/quarter is it being offered?')),
            ],
        ),
        migrations.CreateModel(
            name='Enrolled',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_enrolled', models.BooleanField(default=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='Group',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=500, verbose_name='Group name')),
                ('description', models.TextField(blank=True, verbose_name='Detailed group description')),
                ('capacity', models.PositiveIntegerField(default=0, help_text='How many people in this particular group instance?')),
                ('order', models.PositiveIntegerField(default=0, help_text='For ordering purposes in the tables.')),
            ],
        ),
        migrations.CreateModel(
            name='Group_Formation_Process',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('LTI_id', models.CharField(help_text='In Brightspace LTI post: "resource_link_id"', max_length=50, verbose_name='LTI ID')),
                ('title', models.CharField(blank=True, max_length=300, verbose_name='Group formation name')),
                ('instructions', models.TextField(blank=True, help_text='May contain HTML instructions', verbose_name='Overall instructions to learners')),
                ('allow_unenroll', models.BooleanField(default=True, help_text='Can learners unenroll, which implies they will also be allowed to re-enroll, until the close off date/time.')),
                ('show_fellows', models.BooleanField(default=False, help_text='Can learners see the FirstName LastName of the other people enrolled in their groups.')),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='formation.Course')),
            ],
            options={
                'verbose_name_plural': 'Group formation processes',
                'verbose_name': 'Group formation process',
            },
        ),
        migrations.CreateModel(
            name='Person',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(max_length=254)),
                ('student_number', models.CharField(blank=True, default='', max_length=15)),
                ('display_name', models.CharField(blank=True, max_length=400, verbose_name='Display name')),
                ('user_ID', models.CharField(blank=True, max_length=100, verbose_name='User ID from LMS/LTI')),
                ('role', models.CharField(choices=[('Admin', 'Administrator'), ('Student', 'Student')], default='Student', max_length=7)),
            ],
        ),
        migrations.AddField(
            model_name='group',
            name='gp',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='formation.Group_Formation_Process'),
        ),
        migrations.AddField(
            model_name='enrolled',
            name='group',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='formation.Group'),
        ),
        migrations.AddField(
            model_name='enrolled',
            name='person',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='formation.Person'),
        ),
    ]
