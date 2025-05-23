# Generated by Django 5.2 on 2025-04-28 03:05

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('project', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Budget',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('budget_type', models.CharField(choices=[('project', 'Project'), ('organizational', 'Organizational'), ('department', 'Department'), ('campaign', 'Campaign')], max_length=20)),
                ('fiscal_year', models.CharField(blank=True, max_length=10, null=True)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('total_amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('notes', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='created_budgets', to=settings.AUTH_USER_MODEL)),
                ('project', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='budgets', to='project.project')),
            ],
        ),
        migrations.CreateModel(
            name='BudgetItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(max_length=100)),
                ('description', models.TextField()),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('notes', models.TextField(blank=True, null=True)),
                ('budget', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='finance.budget')),
            ],
        ),
        migrations.CreateModel(
            name='DonationCampaign',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('target_amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('is_active', models.BooleanField(default=True)),
                ('image', models.ImageField(blank=True, null=True, upload_to='campaign_images/')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('project', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='campaigns', to='project.project')),
            ],
        ),
        migrations.CreateModel(
            name='Donation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('donation_type', models.CharField(choices=[('one_time', 'One Time'), ('recurring', 'Recurring'), ('in_kind', 'In-Kind')], max_length=20)),
                ('donation_date', models.DateTimeField()),
                ('payment_method', models.CharField(max_length=100)),
                ('transaction_id', models.CharField(blank=True, max_length=255, null=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('completed', 'Completed'), ('failed', 'Failed'), ('refunded', 'Refunded')], max_length=20)),
                ('is_anonymous', models.BooleanField(default=False)),
                ('notes', models.TextField(blank=True, null=True)),
                ('receipt_sent', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('donor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='donations', to=settings.AUTH_USER_MODEL)),
                ('project', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='donations', to='project.project')),
                ('campaign', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='donations', to='finance.donationcampaign')),
            ],
        ),
        migrations.AddField(
            model_name='budget',
            name='campaign',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='budgets', to='finance.donationcampaign'),
        ),
        migrations.CreateModel(
            name='Grant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('grantor', models.CharField(max_length=200)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('submission_date', models.DateField(blank=True, null=True)),
                ('approval_date', models.DateField(blank=True, null=True)),
                ('start_date', models.DateField(blank=True, null=True)),
                ('end_date', models.DateField(blank=True, null=True)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('submitted', 'Submitted'), ('under_review', 'Under Review'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('active', 'Active'), ('completed', 'Completed')], default='draft', max_length=20)),
                ('requirements', models.TextField(blank=True, null=True)),
                ('reporting_frequency', models.CharField(blank=True, max_length=100, null=True)),
                ('contact_person', models.CharField(blank=True, max_length=100, null=True)),
                ('contact_email', models.EmailField(blank=True, max_length=254, null=True)),
                ('notes', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('project', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='grants', to='project.project')),
            ],
        ),
        migrations.CreateModel(
            name='GrantReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('reporting_period_start', models.DateField()),
                ('reporting_period_end', models.DateField()),
                ('submission_date', models.DateField(blank=True, null=True)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('submitted', 'Submitted'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('revision_required', 'Revision Required')], default='draft', max_length=20)),
                ('narrative', models.TextField()),
                ('financial_report', models.TextField()),
                ('outcomes', models.TextField()),
                ('challenges', models.TextField(blank=True, null=True)),
                ('next_steps', models.TextField(blank=True, null=True)),
                ('feedback', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('grant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reports', to='finance.grant')),
                ('submitted_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='submitted_grant_reports', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='InKindDonation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('item_description', models.TextField()),
                ('estimated_value', models.DecimalField(decimal_places=2, max_digits=10)),
                ('donation_date', models.DateField()),
                ('is_anonymous', models.BooleanField(default=False)),
                ('notes', models.TextField(blank=True, null=True)),
                ('receipt_sent', models.BooleanField(default=False)),
                ('image', models.ImageField(blank=True, null=True, upload_to='in_kind_donations/')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('campaign', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='in_kind_donations', to='finance.donationcampaign')),
                ('donor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='in_kind_donations', to=settings.AUTH_USER_MODEL)),
                ('project', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='in_kind_donations', to='project.project')),
                ('received_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='received_donations', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='RecurringDonation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('frequency', models.CharField(choices=[('monthly', 'Monthly'), ('quarterly', 'Quarterly'), ('biannually', 'Biannually'), ('annually', 'Annually')], max_length=20)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField(blank=True, null=True)),
                ('payment_method', models.CharField(max_length=100)),
                ('status', models.CharField(choices=[('active', 'Active'), ('paused', 'Paused'), ('cancelled', 'Cancelled'), ('expired', 'Expired')], default='active', max_length=20)),
                ('is_anonymous', models.BooleanField(default=False)),
                ('notes', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('campaign', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recurring_donations', to='finance.donationcampaign')),
                ('donor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recurring_donations', to=settings.AUTH_USER_MODEL)),
                ('project', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recurring_donations', to='project.project')),
            ],
        ),
    ]
