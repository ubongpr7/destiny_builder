# Generated by Django 5.2 on 2025-05-07 10:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0014_disability_user_disabled_alter_user_sex_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='profile_link',
            field=models.URLField(blank=True, null=True),
        ),
    ]
