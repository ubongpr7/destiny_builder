# Generated by Django 5.2 on 2025-05-24 18:01

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0002_organizationalexpense_alter_budget_options_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='donationcampaign',
            name='current_amount',
        ),
    ]
