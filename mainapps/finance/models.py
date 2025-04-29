from django.db import models
from mainapps.project.models import Project
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
User=get_user_model()

class DonationCampaign(models.Model):
    """Fundraising campaigns"""
    title = models.CharField(max_length=200)
    description = models.TextField()
    target_amount = models.DecimalField(max_digits=12, decimal_places=2)
    start_date = models.DateField()
    end_date = models.DateField()
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='campaigns')
    is_active = models.BooleanField(default=True)
    image = models.ImageField(upload_to='campaign_images/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.title

class Donation(models.Model):
    """Donations received by the organization"""
    DONATION_TYPE_CHOICES = [
        ('one_time', 'One Time'),
        ('recurring', 'Recurring'),
        ('in_kind', 'In-Kind'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    donor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='donations')
    campaign = models.ForeignKey(DonationCampaign, on_delete=models.SET_NULL, null=True, blank=True, related_name='donations')
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='donations')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    donation_type = models.CharField(max_length=20, choices=DONATION_TYPE_CHOICES)
    donation_date = models.DateTimeField()
    payment_method = models.CharField(max_length=100)
    transaction_id = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    is_anonymous = models.BooleanField(default=False)
    notes = models.TextField(blank=True, null=True)
    receipt_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        if self.donor and not self.is_anonymous:
            return f"{self.donor.username} - ${self.amount}"
        return f"Anonymous - ${self.amount}"

class RecurringDonation(models.Model):
    """Recurring donation subscriptions"""
    FREQUENCY_CHOICES = [
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('biannually', 'Biannually'),
        ('annually', 'Annually'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ]
    
    donor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recurring_donations')
    campaign = models.ForeignKey(DonationCampaign, on_delete=models.SET_NULL, null=True, blank=True, related_name='recurring_donations')
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='recurring_donations')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    payment_method = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    is_anonymous = models.BooleanField(default=False)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.donor.username} - ${self.amount} {self.frequency}"

class InKindDonation(models.Model):
    """Non-monetary donations"""
    donor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='in_kind_donations')
    campaign = models.ForeignKey(DonationCampaign, on_delete=models.SET_NULL, null=True, blank=True, related_name='in_kind_donations')
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='in_kind_donations')
    item_description = models.TextField()
    estimated_value = models.DecimalField(max_digits=10, decimal_places=2)
    donation_date = models.DateField()
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='received_donations')
    is_anonymous = models.BooleanField(default=False)
    notes = models.TextField(blank=True, null=True)
    receipt_sent = models.BooleanField(default=False)
    image = models.ImageField(upload_to='in_kind_donations/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.item_description} - ${self.estimated_value}"

class Grant(models.Model):
    """Grants received by the organization"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('active', 'Active'),
        ('completed', 'Completed'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    grantor = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    submission_date = models.DateField(blank=True, null=True)
    approval_date = models.DateField(blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='grants')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    requirements = models.TextField(blank=True, null=True)
    reporting_frequency = models.CharField(max_length=100, blank=True, null=True)
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    contact_email = models.EmailField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.title} - {self.grantor} (${self.amount})"

class GrantReport(models.Model):
    """Reports submitted for grants"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('revision_required', 'Revision Required'),
    ]
    
    grant = models.ForeignKey(Grant, on_delete=models.CASCADE, related_name='reports')
    title = models.CharField(max_length=200)
    reporting_period_start = models.DateField()
    reporting_period_end = models.DateField()
    submission_date = models.DateField(blank=True, null=True)
    submitted_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='submitted_grant_reports')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    narrative = models.TextField()
    financial_report = models.TextField()
    outcomes = models.TextField()
    challenges = models.TextField(blank=True, null=True)
    next_steps = models.TextField(blank=True, null=True)
    feedback = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.grant.title} - {self.title}"

class Budget(models.Model):
    """Budget for projects or the organization"""
    BUDGET_TYPE_CHOICES = [
        ('project', 'Project'),
        ('organizational', 'Organizational'),
        ('department', 'Department'),
        ('campaign', 'Campaign'),
    ]
    
    title = models.CharField(max_length=200)
    budget_type = models.CharField(max_length=20, choices=BUDGET_TYPE_CHOICES)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='budgets')
    campaign = models.ForeignKey(DonationCampaign, on_delete=models.SET_NULL, null=True, blank=True, related_name='budgets')
    fiscal_year = models.CharField(max_length=10, blank=True, null=True)
    start_date = models.DateField()
    end_date = models.DateField()
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_budgets')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.title} - {self.budget_type} (${self.total_amount})"

class BudgetItem(models.Model):
    """Line items within a budget"""
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name='items')
    category = models.CharField(max_length=100)
    description = models.TextField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.budget.title} - {self.category} (${self.amount})"