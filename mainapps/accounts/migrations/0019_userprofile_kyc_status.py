# Generated by Django 5.2 on 2025-05-09 09:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0018_alter_userprofile_profile_image'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='kyc_status',
            field=models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('flagged', 'Flagged'), ('scammer', 'Scammer')], default='pending', help_text='Current KYC verification status', max_length=20),
        ),
    ]
