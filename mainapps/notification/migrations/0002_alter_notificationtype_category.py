# Generated by Django 5.2 on 2025-05-23 12:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notification', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notificationtype',
            name='category',
            field=models.CharField(choices=[('project', 'Project'), ('milestone', 'Milestone'), ('task', 'Task'), ('expense', 'Expense'), ('team', 'Team'), ('system', 'System'), ('kyc', 'KYC Verification'), ('payment', 'Payment'), ('document', 'Document'), ('other', 'Other'), ('update', 'Update'), ('media', 'Media'), ('comment', 'Comment'), ('feedback', 'Feedback')], default='system', max_length=20),
        ),
    ]
