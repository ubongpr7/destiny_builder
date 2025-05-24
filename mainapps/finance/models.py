from django.db import models
from mainapps.project.models import Project
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from decimal import Decimal

from django.utils import timezone

User = get_user_model()

class DonationCampaign(models.Model):
    """Fundraising campaigns"""
    title = models.CharField(max_length=200)
    description = models.TextField()
    target_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    current_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    start_date = models.DateField()
    end_date = models.DateField()
    project = models.ForeignKey(
        Project, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='campaigns'
    )
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    image = models.ImageField(upload_to='campaign_images/', blank=True, null=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='created_campaigns'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active', 'start_date']),
            models.Index(fields=['project', 'is_active']),
        ]
    
    def __str__(self):
        return self.title
    
    @property
    def progress_percentage(self):
        if self.target_amount > 0:
            return min((self.current_amount / self.target_amount) * 100, 100)
        return 0
    
    @property
    def is_completed(self):
        return self.current_amount >= self.target_amount

class Donation(models.Model):
    """Donations received by the organization"""
    DONATION_TYPE_CHOICES = [
        ('one_time', 'One Time'),
        ('recurring', 'Recurring'),
        ('in_kind', 'In-Kind'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('cancelled', 'Cancelled'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('credit_card', 'Credit Card'),
        ('debit_card', 'Debit Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('paypal', 'PayPal'),
        ('stripe', 'Stripe'),
        ('cash', 'Cash'),
        ('check', 'Check'),
        ('other', 'Other'),
    ]
    
    donor = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='donations'
    )
    campaign = models.ForeignKey(
        DonationCampaign, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='donations'
    )
    project = models.ForeignKey(
        Project, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='donations'
    )
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    donation_type = models.CharField(max_length=20, choices=DONATION_TYPE_CHOICES)
    donation_date = models.DateTimeField()
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    transaction_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    reference_number = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_anonymous = models.BooleanField(default=False)
    donor_name = models.CharField(max_length=200, blank=True, null=True)
    donor_email = models.EmailField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    receipt_sent = models.BooleanField(default=False)
    receipt_number = models.CharField(max_length=100, blank=True, null=True, unique=True)
    tax_deductible = models.BooleanField(default=True)
    processed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='processed_donations'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-donation_date']
        indexes = [
            models.Index(fields=['status', 'donation_date']),
            models.Index(fields=['donor', 'status']),
            models.Index(fields=['campaign', 'status']),
        ]
    def save(self, *args, **kwargs):
        if self.transaction_id=='':
            self.transaction_id = None
        super().save(*args, **kwargs)
    
    @property
    def donor_name_display(self):
        if self.donor and not self.is_anonymous:
            return self.donor.get_full_name
        elif self.donor_name and not self.is_anonymous:
            return self.donor_name
        else:
            return "Anonymous"
    
    def __str__(self):
        if self.donor and not self.is_anonymous:
            return f"{self.donor.get_full_name() or self.donor.username} - ${self.amount}"
        elif self.donor_name and not self.is_anonymous:
            return f"{self.donor_name} - ${self.amount}"
        return f"Anonymous - ${self.amount}"

class RecurringDonation(models.Model):
    """Recurring donation subscriptions"""
    FREQUENCY_CHOICES = [
        ('weekly', 'Weekly'),
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
        ('failed', 'Failed'),
    ]
    
    donor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recurring_donations')
    campaign = models.ForeignKey(
        DonationCampaign, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='recurring_donations'
    )
    project = models.ForeignKey(
        Project, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='recurring_donations'
    )
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    next_payment_date = models.DateField(null=True, blank=True)
    payment_method = models.CharField(max_length=100)
    subscription_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    is_anonymous = models.BooleanField(default=False)
    notes = models.TextField(blank=True, null=True)
    total_donated = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    payment_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'next_payment_date']),
            models.Index(fields=['donor', 'status']),
        ]
    
    def __str__(self):
        return f"{self.donor.get_full_name() or self.donor.username} - ${self.amount} {self.frequency}"

class InKindDonation(models.Model):
    """Non-monetary donations"""
    STATUS_CHOICES = [
        ('pledged', 'Pledged'),
        ('received', 'Received'),
        ('declined', 'Declined'),
        ('expired', 'Expired'),
    ]
    
    donor = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='in_kind_donations'
    )
    campaign = models.ForeignKey(
        DonationCampaign, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='in_kind_donations'
    )
    project = models.ForeignKey(
        Project, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='in_kind_donations'
    )
    item_description = models.TextField()
    category = models.CharField(max_length=100, blank=True, null=True)
    quantity = models.PositiveIntegerField(default=1)
    estimated_value = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    donation_date = models.DateField()
    received_date = models.DateField(blank=True, null=True)
    received_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='received_donations'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pledged')
    is_anonymous = models.BooleanField(default=False)
    donor_name = models.CharField(max_length=200, blank=True, null=True)
    donor_email = models.EmailField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    receipt_sent = models.BooleanField(default=False)
    receipt_number = models.CharField(max_length=100, blank=True, null=True, unique=True)
    image = models.ImageField(upload_to='in_kind_donations/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-donation_date']
        indexes = [
            models.Index(fields=['status', 'donation_date']),
            models.Index(fields=['donor', 'status']),
        ]
    
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
        ('cancelled', 'Cancelled'),
    ]
    
    GRANT_TYPE_CHOICES = [
        ('government', 'Government'),
        ('foundation', 'Foundation'),
        ('corporate', 'Corporate'),
        ('individual', 'Individual'),
        ('other', 'Other'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    grantor = models.CharField(max_length=200)
    grantor_type = models.CharField(max_length=20, choices=GRANT_TYPE_CHOICES, default='foundation')
    amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    amount_received = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    submission_date = models.DateField(blank=True, null=True)
    approval_date = models.DateField(blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    project = models.ForeignKey(
        Project, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='grants'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    requirements = models.TextField(blank=True, null=True)
    reporting_frequency = models.CharField(max_length=100, blank=True, null=True)
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    contact_email = models.EmailField(blank=True, null=True)
    contact_phone = models.CharField(max_length=20, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    application_deadline = models.DateField(blank=True, null=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='created_grants'
    )
    managed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='managed_grants'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'start_date']),
            models.Index(fields=['grantor_type', 'status']),
        ]
    
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
    
    REPORT_TYPE_CHOICES = [
        ('interim', 'Interim Report'),
        ('final', 'Final Report'),
        ('financial', 'Financial Report'),
        ('narrative', 'Narrative Report'),
        ('annual', 'Annual Report'),
    ]
    
    grant = models.ForeignKey(Grant, on_delete=models.CASCADE, related_name='reports')
    title = models.CharField(max_length=200)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES, default='interim')
    reporting_period_start = models.DateField()
    reporting_period_end = models.DateField()
    due_date = models.DateField(blank=True, null=True)
    submission_date = models.DateField(blank=True, null=True)
    submitted_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='submitted_grant_reports'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    narrative = models.TextField()
    financial_report = models.TextField()
    outcomes = models.TextField()
    challenges = models.TextField(blank=True, null=True)
    next_steps = models.TextField(blank=True, null=True)
    feedback = models.TextField(blank=True, null=True)
    attachments = models.FileField(upload_to='grant_reports/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['grant', 'status']),
            models.Index(fields=['due_date', 'status']),
        ]
    
    def __str__(self):
        return f"{self.grant.title} - {self.title}"

class Budget(models.Model):
    """Budget for projects or the organization"""
    BUDGET_TYPE_CHOICES = [
        ('project', 'Project'),
        ('organizational', 'Organizational'),
        ('department', 'Department'),
        ('campaign', 'Campaign'),
        ('grant', 'Grant'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending_approval', 'Pending Approval'),
        ('approved', 'Approved'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    title = models.CharField(max_length=200)
    budget_type = models.CharField(max_length=20, choices=BUDGET_TYPE_CHOICES)
    project = models.ForeignKey(
        Project, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='budgets'
    )
    campaign = models.ForeignKey(
        DonationCampaign, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='budgets'
    )
    grant = models.ForeignKey(
        Grant, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='budgets'
    )
    fiscal_year = models.CharField(max_length=10, blank=True, null=True)
    start_date = models.DateField()
    end_date = models.DateField()
    total_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    spent_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='created_budgets'
    )
    approved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='approved_budgets'
    )
    approved_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['budget_type', 'status']),
            models.Index(fields=['fiscal_year', 'status']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.budget_type} (${self.total_amount})"
    
    @property
    def remaining_amount(self):
        return self.total_amount - self.spent_amount
    
    @property
    def spent_percentage(self):
        if self.total_amount > 0:
            return (self.spent_amount / self.total_amount) * 100
        return 0

class BudgetItem(models.Model):
    """Line items within a budget"""
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name='items')
    category = models.CharField(max_length=100)
    subcategory = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField()
    budgeted_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    spent_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    project_expenses = models.ManyToManyField(
        'project.ProjectExpense', 
        blank=True, 
        related_name='budget_items',
        help_text="Project expenses allocated to this budget item"
    )
    
    class Meta:
        ordering = ['category', 'subcategory']
        indexes = [
            models.Index(fields=['budget', 'category']),
        ]
    
    def __str__(self):
        return f"{self.budget.title} - {self.category} (${self.budgeted_amount})"
    
    @property
    def remaining_amount(self):
        return self.budgeted_amount - self.spent_amount
    
    @property
    def spent_percentage(self):
        if self.budgeted_amount > 0:
            return (self.spent_amount / self.budgeted_amount) * 100
        return 0

class OrganizationalExpense(models.Model):
    """Non-project organizational expenses"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('rejected', 'Rejected'),
    ]
    
    EXPENSE_TYPE_CHOICES = [
        ('administrative', 'Administrative'),
        ('operational', 'Operational'),
        ('travel', 'Travel'),
        ('equipment', 'Equipment'),
        ('supplies', 'Supplies'),
        ('services', 'Services'),
        ('utilities', 'Utilities'),
        ('rent', 'Rent'),
        ('insurance', 'Insurance'),
        ('other', 'Other'),
    ]
    
    budget_item = models.ForeignKey(
        BudgetItem, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='organizational_expenses'
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    expense_type = models.CharField(max_length=20, choices=EXPENSE_TYPE_CHOICES)
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    expense_date = models.DateField()
    vendor = models.CharField(max_length=200, blank=True, null=True)
    receipt = models.FileField(upload_to='org_expense_receipts/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    submitted_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='submitted_org_expenses'
    )
    approved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='approved_org_expenses'
    )
    approved_at = models.DateTimeField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-expense_date']
        indexes = [
            models.Index(fields=['status', 'expense_date']),
            models.Index(fields=['submitted_by', 'status']),
        ]
    
    def __str__(self):
        return f"{self.title} - ${self.amount}"
