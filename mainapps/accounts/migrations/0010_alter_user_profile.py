# Generated by Django 5.2 on 2025-05-02 18:53

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0009_alter_userprofile_expertise'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='profile',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='user', to='accounts.userprofile'),
        ),
    ]
