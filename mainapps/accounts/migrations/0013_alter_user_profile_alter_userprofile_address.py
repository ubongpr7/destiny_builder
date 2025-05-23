# Generated by Django 5.2 on 2025-05-04 09:23

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0012_remove_userprofile_user_user_profile'),
        ('common', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='profile',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='user', to='accounts.userprofile'),
        ),
        migrations.AlterField(
            model_name='userprofile',
            name='address',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='user_profile', to='common.address'),
        ),
    ]
