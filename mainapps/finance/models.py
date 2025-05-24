from django.db import models
from mainapps.accounts.models import Department
from mainapps.project.models import Project
from mainapps.common.models import Currency
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.utils import timezone
from django.core.exceptions import ValidationError

User = get_user_model()

class FinancialInstitution(models.Model):
    """Banks and other financial institutions"""
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)  # Bank code/SWIFT
    branch_name = models.CharField(max_length=200, blank=True, null=True)
    branch_code = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    contact_phone = models.CharField(max_length=20, blank=True, null=True)
    contact_email = models.EmailField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = "Financial Institution"
        verbose_name_plural = "Financial Institutions"
    
    def __str__(self):
        return f"{self.name} - {self.branch_name or 'Main Branch'}"

class BankAccount(models.Model):
    """Organization's bank accounts with multi-currency support"""
    ACCOUNT_TYPE_CHOICES = [
        ('checking', 'Checking Account'),
        ('savings', 'Savings Account'),
        ('money_market', 'Money Market'),
        ('restricted', 'Restricted Fund Account'),
        ('project', 'Project-Specific Account'),
        ('grant', 'Grant-Specific Account'),
        ('emergency', 'Emergency Fund Account'),
        ('investment', 'Investment Account'),
        ('paypal', 'PayPal Account'),
        ('stripe', 'Stripe Account'),
        ('mobile_money', 'Mobile Money Account'),
    ]
    
    name = models.CharField(max_length=200)
    account_number = models.CharField(max_length=50, unique=True)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES)
    financial_institution = models.ForeignKey(
        FinancialInstitution, 
        on_delete=models.PROTECT,
        related_name='accounts'
    )
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name='bank_accounts'
    )
    
    # Account purpose and restrictions
    purpose = models.TextField(help_text="What this account is used for")
    is_restricted = models.BooleanField(
        default=False,
        help_text="Whether this account has usage restrictions"
    )
    restrictions = models.TextField(
        blank=True, 
        null=True,
        help_text="Details of any restrictions on this account"
    )
    
    # Account management
    primary_signatory = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='primary_accounts'
    )
    secondary_signatories = models.ManyToManyField(
        User,
        blank=True,
        related_name='secondary_accounts',
        help_text="Additional people who can authorize transactions"
    )
    
    # Account status and details
    is_active = models.BooleanField(default=True)
    opening_date = models.DateField()
    closing_date = models.DateField(blank=True, null=True)
    minimum_balance = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0
    )
    
    # Online account details (for digital payment platforms)
    api_key = models.CharField(max_length=255, blank=True, null=True)
    webhook_url = models.URLField(blank=True, null=True)
    
    # Tracking
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='created_accounts'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['account_type', 'is_active']),
            models.Index(fields=['financial_institution', 'is_active']),
            models.Index(fields=['currency', 'is_active']),
        ]
        verbose_name = "Bank Account"
        verbose_name_plural = "Bank Accounts"
    
    @property
    def current_balance(self):
        """Calculate current balance from transactions"""
        from django.db.models import Sum
        
        credits = self.transactions.filter(
            transaction_type='credit',
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        debits = self.transactions.filter(
            transaction_type='debit',
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        return credits - debits
    
    @property
    def formatted_balance(self):
        """Return balance formatted with currency"""
        return f"{self.currency.code} {self.current_balance:,.2f}"
    
    def __str__(self):
        return f"{self.name} ({self.currency.code}) - {self.account_number[-4:]}"

class ExchangeRate(models.Model):
    """Track exchange rates for currency conversions"""
    from_currency = models.ForeignKey(
        Currency,
        on_delete=models.CASCADE,
        related_name='exchange_rates_from'
    )
    to_currency = models.ForeignKey(
        Currency,
        on_delete=models.CASCADE,
        related_name='exchange_rates_to'
    )
    rate = models.DecimalField(
        max_digits=15,
        decimal_places=8,
        validators=[MinValueValidator(Decimal('0.00000001'))]
    )
    effective_date = models.DateTimeField()
    source = models.CharField(
        max_length=100,
        help_text="Source of exchange rate (e.g., Central Bank, XE.com)"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='created_exchange_rates'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-effective_date']
        indexes = [
            models.Index(fields=['from_currency', 'to_currency', 'effective_date']),
        ]
        unique_together = ['from_currency', 'to_currency', 'effective_date']
        verbose_name = "Exchange Rate"
        verbose_name_plural = "Exchange Rates"
    
    def __str__(self):
        return f"1 {self.from_currency.code} = {self.rate} {self.to_currency.code}"

class DonationCampaign(models.Model):
    """Fundraising campaigns with multi-currency support"""
    title = models.CharField(max_length=200)
    description = models.TextField()
    target_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    target_currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name='campaigns',
        help_text="Currency for the target amount",
        null=True,
        blank=True
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
            models.Index(fields=['target_currency']),
        ]
        verbose_name = "Donation Campaign"
        verbose_name_plural = "Donation Campaigns"
    
    def __str__(self):
        return self.title
    
    @property
    def current_amount_in_target_currency(self):
        """Calculate total raised in campaign's target currency"""
        total = Decimal('0.00')
        for donation in self.donations.filter(status='completed'):
            if donation.currency == self.target_currency:
                total += donation.amount
            else:
                converted_amount = donation.get_amount_in_currency(self.target_currency)
                total += converted_amount
        return total
    
    @property
    def progress_percentage(self):
        if self.target_amount > 0:
            current = self.current_amount_in_target_currency
            return min((current / self.target_amount) * 100, 100)
        return 0
    
    @property
    def is_completed(self):
        return self.current_amount_in_target_currency >= self.target_amount

class Donation(models.Model):
    """One-time donations with full multi-currency support"""
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
        ('mobile_money', 'Mobile Money'),
        ('cryptocurrency', 'Cryptocurrency'),
        ('other', 'Other'),
    ]
    
    # Donor information
    donor = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='donations'
    )
    is_anonymous = models.BooleanField(default=False)
    donor_name = models.CharField(max_length=200, blank=True, null=True)
    donor_email = models.EmailField(blank=True, null=True)
    
    # Donation details
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
    
    # Amount and currency
    amount = models.DecimalField(
        max_digits=16, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='donations',
        help_text="Currency of the donation"
    )
    
    # Exchange rate and conversion
    exchange_rate = models.DecimalField(
        max_digits=15,
        decimal_places=8,
        default=1.0,
        help_text="Exchange rate used if currency conversion was needed"
    )
    converted_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Amount after currency conversion"
    )
    converted_currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='converted_donations',
        help_text="Currency after conversion"
    )
    
    # Transaction details
    donation_date = models.DateTimeField(null=True, blank=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    transaction_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    reference_number = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Payment processor details
    processor_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Fee charged by payment processor"
    )
    processor_fee_currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='processor_fee_donations'
    )
    net_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Amount after processor fees"
    )
    
    # Bank account tracking
    deposited_to_account = models.ForeignKey(
        BankAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='donations',
        help_text="Bank account where this donation was deposited"
    )
    deposit_date = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When the donation was actually deposited"
    )
    bank_reference = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Bank's reference number for the deposit"
    )
    
    # Administrative
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
            models.Index(fields=['currency', 'donation_date']),
        ]
        verbose_name = "Donation"
        verbose_name_plural = "Donations"
    
    def save(self, *args, **kwargs):
        if self.transaction_id == '':
            self.transaction_id = None
        
        # Auto-calculate net amount if not provided
        if not self.net_amount and self.processor_fee:
            self.net_amount = self.amount - self.processor_fee
        elif not self.net_amount:
            self.net_amount = self.amount
            
        super().save(*args, **kwargs)
    
    def get_amount_in_currency(self, target_currency):
        """Convert donation amount to specified currency"""
        if self.currency == target_currency:
            return self.amount
        
        try:
            exchange_rate = ExchangeRate.objects.filter(
                from_currency=self.currency,
                to_currency=target_currency,
                effective_date__lte=self.donation_date
            ).order_by('-effective_date').first()
            
            if exchange_rate:
                return self.amount * exchange_rate.rate
        except ExchangeRate.DoesNotExist:
            pass
        
        # Return original amount if no exchange rate found
        return self.amount
    
    @property
    def donor_name_display(self):
        if self.is_anonymous:
            return "Anonymous"
        if self.donor:
            return self.donor.get_full_name() or self.donor.username
        return self.donor_name or "Unknown"
    
    @property
    def formatted_amount(self):
        return f"{self.currency.code} {self.amount:,.2f}"
    
    def __str__(self):
        return f"{self.donor_name_display} - {self.formatted_amount}"

class RecurringDonation(models.Model):
    """Recurring donation subscriptions with multi-currency support"""
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
    
    # Donor information
    donor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recurring_donations')
    is_anonymous = models.BooleanField(default=False)
    
    # Donation targets
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
    
    # Amount and currency
    amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name='recurring_donations',
        null=True,
        blank=True

    )
    
    # Subscription details
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    next_payment_date = models.DateField(null=True, blank=True)
    payment_method = models.CharField(max_length=100)
    subscription_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Tracking
    total_donated = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    payment_count = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'next_payment_date']),
            models.Index(fields=['donor', 'status']),
            models.Index(fields=['currency', 'status']),
        ]
        verbose_name = "Recurring Donation"
        verbose_name_plural = "Recurring Donations"
    
    @property
    def formatted_amount(self):
        return f"{self.currency.code} {self.amount:,.2f}"
    
    def __str__(self):
        return f"{self.donor.get_full_name() or self.donor.username} - {self.formatted_amount} {self.frequency}"

class InKindDonation(models.Model):
    """Non-monetary donations with valuation in multiple currencies"""
    STATUS_CHOICES = [
        ('pledged', 'Pledged'),
        ('received', 'Received'),
        ('declined', 'Declined'),
        ('expired', 'Expired'),
    ]
    
    # Donor information
    donor = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='in_kind_donations'
    )
    is_anonymous = models.BooleanField(default=False)
    donor_name = models.CharField(max_length=200, blank=True, null=True)
    donor_email = models.EmailField(blank=True, null=True)
    
    # Donation targets
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
    
    # Item details
    item_description = models.TextField()
    category = models.CharField(max_length=100, blank=True, null=True)
    quantity = models.PositiveIntegerField(default=1)
    
    # Valuation
    estimated_value = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    valuation_currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name='in_kind_donations',
        null=True,
        blank=True
    )
    
    # Dates and status
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
    
    # Administrative
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
            models.Index(fields=['valuation_currency']),
        ]
        verbose_name = "In-Kind Donation"
        verbose_name_plural = "In-Kind Donations"
    
    @property
    def donor_name_display(self):
        if self.is_anonymous:
            return "Anonymous"
        if self.donor:
            return self.donor.get_full_name() or self.donor.username
        return self.donor_name or "Unknown"
    
    @property
    def formatted_value(self):
        return f"{self.valuation_currency.code} {self.estimated_value:,.2f}"
    
    def __str__(self):
        return f"{self.item_description} - {self.formatted_value}"

class Grant(models.Model):
    """Grants received by the organization with multi-currency support"""
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
        ('multilateral', 'Multilateral Organization'),
        ('other', 'Other'),
    ]
    
    # Grant details
    title = models.CharField(max_length=200)
    description = models.TextField()
    grantor = models.CharField(max_length=200)
    grantor_type = models.CharField(max_length=20, choices=GRANT_TYPE_CHOICES, default='foundation')
    
    # Amount and currency
    amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name='grants',
        null=True,
        blank=True

    )
    amount_received = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    # Dates
    submission_date = models.DateField(blank=True, null=True)
    approval_date = models.DateField(blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    application_deadline = models.DateField(blank=True, null=True)
    
    # Relationships
    project = models.ForeignKey(
        Project, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='grants'
    )
    designated_account = models.ForeignKey(
        BankAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='grants',
        help_text="Specific account designated for this grant"
    )
    
    # Grant management
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    requirements = models.TextField(blank=True, null=True)
    reporting_frequency = models.CharField(max_length=100, blank=True, null=True)
    disbursement_schedule = models.TextField(
        blank=True,
        null=True,
        help_text="Schedule of when grant funds will be received"
    )
    
    # Contact information
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    contact_email = models.EmailField(blank=True, null=True)
    contact_phone = models.CharField(max_length=20, blank=True, null=True)
    
    # Administrative
    notes = models.TextField(blank=True, null=True)
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
            models.Index(fields=['currency', 'status']),
        ]
        verbose_name = "Grant"
        verbose_name_plural = "Grants"
    
    @property
    def remaining_amount(self):
        return self.amount - self.amount_received
    
    @property
    def formatted_amount(self):
        return f"{self.currency.code} {self.amount:,.2f}"
    
    def __str__(self):
        return f"{self.title} - {self.grantor} ({self.formatted_amount})"

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
        verbose_name = "Grant Report"
        verbose_name_plural = "Grant Reports"
    
    def __str__(self):
        return f"{self.grant.title} - {self.title}"

class FundingSource(models.Model):
    """Sources of funding for budgets with multi-currency support"""
    FUNDING_TYPE_CHOICES = [
        ('donation', 'General Donation'),
        ('campaign', 'Campaign'),
        ('grant', 'Grant'),
        ('internal', 'Internal Funds'),
        ('partnership', 'Partnership Funding'),
        ('government', 'Government Funding'),
        ('investment', 'Investment Returns'),
    ]
    
    name = models.CharField(max_length=200)
    funding_type = models.CharField(max_length=20, choices=FUNDING_TYPE_CHOICES)
    
    # Link to existing models
    donation = models.ForeignKey(
        Donation, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='funding_sources'
    )
    campaign = models.ForeignKey(
        DonationCampaign, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='funding_sources'
    )
    grant = models.ForeignKey(
        Grant, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='funding_sources'
    )
    
    # Amount and currency
    amount_available = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name='funding_sources'
    )
    amount_allocated = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['funding_type', 'is_active']),
            models.Index(fields=['currency', 'is_active']),
        ]
        verbose_name = "Funding Source"
        verbose_name_plural = "Funding Sources"
    
    @property
    def amount_remaining(self):
        return self.amount_available - self.amount_allocated
    
    @property
    def formatted_amount(self):
        return f"{self.currency.code} {self.amount_available:,.2f}"
    
    def __str__(self):
        return f"{self.name} ({self.get_funding_type_display()}) - {self.formatted_amount}"

class Budget(models.Model):
    """Budget for projects or the organization with multi-currency support"""
    BUDGET_TYPE_CHOICES = [
        ('project', 'Project'),
        ('organizational', 'Organizational'),
        ('departmental', 'Departmental'),
        ('program', 'Program'),
        ('emergency', 'Emergency Response'),
        ('capacity_building', 'Capacity Building'),
        ('advocacy', 'Advocacy & Policy'),
        ('research', 'Research & Development'),
        ('partnership', 'Partnership'),
        ('event', 'Event'),
        ('maintenance', 'Maintenance & Operations'),
        ('contingency', 'Contingency'),
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
    
    # Relationships
    project = models.ForeignKey(
        Project, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='budgets'
    )
    department = models.ForeignKey(
        Department, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='budgets',
        help_text="Required for departmental budgets"
    )
    
    # Amount and currency
    total_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name='budgets',
        null=True,
        blank=True
    )
    spent_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    # Funding
    funding_sources = models.ManyToManyField(
        FundingSource,
        through='BudgetFunding',
        related_name='budgets'
    )
    
    # Dates and status
    fiscal_year = models.CharField(max_length=10, blank=True, null=True)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    notes = models.TextField(blank=True, null=True)
    
    # Management
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
            models.Index(fields=['department', 'status']),
            models.Index(fields=['currency', 'status']),
        ]
        verbose_name = "Budget"
        verbose_name_plural = "Budgets"
    
    def clean(self):
        if self.budget_type == 'departmental' and not self.department:
            raise ValidationError("Departmental budgets must have a department assigned.")
        
        if self.budget_type == 'project' and not self.project:
            raise ValidationError("Project budgets must have a project assigned.")
    
    @property
    def remaining_amount(self):
        return self.total_amount - self.spent_amount
    
    @property
    def spent_percentage(self):
        if self.total_amount > 0:
            return (self.spent_amount / self.total_amount) * 100
        return 0
    
    @property
    def formatted_amount(self):
        return f"{self.currency.code} {self.total_amount:,.2f}"
    
    def get_funding_breakdown(self):
        """Get breakdown of funding sources for this budget"""
        breakdown = []
        for budget_funding in self.budget_funding.all():
            breakdown.append({
                'source': budget_funding.funding_source.name,
                'type': budget_funding.funding_source.get_funding_type_display(),
                'amount': budget_funding.amount_allocated,
                'currency': budget_funding.funding_source.currency.code,
                'percentage': (budget_funding.amount_allocated / self.total_amount) * 100
            })
        return breakdown
    
    @property
    def total_funding_allocated(self):
        return self.budget_funding.aggregate(
            total=models.Sum('amount_allocated')
        )['total'] or 0
    
    def __str__(self):
        return f"{self.title} - {self.get_budget_type_display()} ({self.formatted_amount})"

class BudgetFunding(models.Model):
    """Through model for budget funding sources"""
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name='budget_funding')
    funding_source = models.ForeignKey(FundingSource, on_delete=models.CASCADE)
    amount_allocated = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    allocation_date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        unique_together = ['budget', 'funding_source']
        verbose_name = "Budget Funding"
        verbose_name_plural = "Budget Funding"
    
    def __str__(self):
        return f"{self.budget.title} - {self.funding_source.name} ({self.funding_source.currency.code} {self.amount_allocated:,.2f})"

class BudgetItem(models.Model):
    """Line items within a budget"""
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name='items')
    category = models.CharField(max_length=100)
    subcategory = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField()
    budgeted_amount = models.DecimalField(
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
    
    # Enhanced controls
    is_locked = models.BooleanField(
        default=False, 
        help_text="Prevent further spending on this item"
    )
    approval_required_threshold = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        null=True, 
        blank=True,
        help_text="Amount above which approval is required for expenses"
    )
    responsible_person = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='responsible_budget_items',
        help_text="Person responsible for this budget line"
    )
    
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Relationships
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
            models.Index(fields=['responsible_person']),
        ]
        verbose_name = "Budget Item"
        verbose_name_plural = "Budget Items"
    
    @property
    def remaining_amount(self):
        return self.budgeted_amount - self.spent_amount
    
    @property
    def spent_percentage(self):
        if self.budgeted_amount > 0:
            return (self.spent_amount / self.budgeted_amount) * 100
        return 0
    
    @property
    def formatted_amount(self):
        return f"{self.budget.currency.code} {self.budgeted_amount:,.2f}"
    
    def __str__(self):
        return f"{self.budget.title} - {self.category} ({self.formatted_amount})"

class OrganizationalExpense(models.Model):
    """Non-project organizational expenses with multi-currency support"""
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
    
    # Amount and currency
    amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name='organizational_expenses',
        null=True,
        blank=True

    )
    
    expense_date = models.DateField()
    vendor = models.CharField(max_length=200, blank=True, null=True)
    receipt = models.FileField(upload_to='org_expense_receipts/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Management
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
            models.Index(fields=['currency', 'expense_date']),
        ]
        verbose_name = "Organizational Expense"
        verbose_name_plural = "Organizational Expenses"
    
    @property
    def formatted_amount(self):
        return f"{self.currency.code} {self.amount:,.2f}"
    
    def __str__(self):
        return f"{self.title} - {self.formatted_amount}"

class AccountTransaction(models.Model):
    """Track all money movements with multi-currency support"""
    TRANSACTION_TYPE_CHOICES = [
        ('credit', 'Credit (Money In)'),
        ('debit', 'Debit (Money Out)'),
        ('transfer_in', 'Transfer In'),
        ('transfer_out', 'Transfer Out'),
        ('currency_exchange', 'Currency Exchange'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        related_name='transactions'
    )
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    
    # Amount in account's currency
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    
    # Original amount and currency (if different)
    original_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Original amount before currency conversion"
    )
    original_currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='original_transactions',
        help_text="Original currency before conversion"
    )
    exchange_rate_used = models.DecimalField(
        max_digits=15,
        decimal_places=8,
        null=True,
        blank=True,
        help_text="Exchange rate used for conversion"
    )
    
    # Link to source records
    donation = models.ForeignKey(
        Donation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='account_transactions'
    )
    grant = models.ForeignKey(
        Grant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='account_transactions'
    )
    expense = models.ForeignKey(
        OrganizationalExpense,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='account_transactions'
    )
    
    # Transfer details
    transfer_to_account = models.ForeignKey(
        BankAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incoming_transfers'
    )
    
    # Transaction details
    reference_number = models.CharField(max_length=100, unique=True)
    bank_reference = models.CharField(max_length=100, blank=True, null=True)
    transaction_date = models.DateTimeField()
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Payment processor details
    processor_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Fee charged by payment processor"
    )
    net_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Amount after processor fees"
    )
    
    # Authorization
    authorized_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='authorized_transactions'
    )
    
    # Reconciliation
    is_reconciled = models.BooleanField(default=False)
    reconciled_date = models.DateTimeField(blank=True, null=True)
    reconciled_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reconciled_transactions'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-transaction_date']
        indexes = [
            models.Index(fields=['account', 'transaction_date']),
            models.Index(fields=['status', 'transaction_date']),
            models.Index(fields=['original_currency', 'transaction_date']),
            models.Index(fields=['is_reconciled']),
        ]
        verbose_name = "Account Transaction"
        verbose_name_plural = "Account Transactions"
    
    def save(self, *args, **kwargs):
        # Auto-calculate net amount if processor fee is provided
        if self.processor_fee and not self.net_amount:
            self.net_amount = self.amount - self.processor_fee
        super().save(*args, **kwargs)
    
    @property
    def formatted_amount(self):
        currency_info = ""
        if self.original_currency and self.original_currency != self.account.currency:
            currency_info = f" (from {self.original_currency.code} {self.original_amount:,.2f})"
        
        return f"{self.account.currency.code} {self.amount:,.2f}{currency_info}"
    
    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.account.name} - {self.formatted_amount}"

class FundAllocation(models.Model):
    """Track how funds are allocated from accounts to budgets"""
    source_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        related_name='fund_allocations'
    )
    budget = models.ForeignKey(
        Budget,
        on_delete=models.PROTECT,
        related_name='fund_allocations'
    )
    amount_allocated = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    allocation_date = models.DateTimeField()
    purpose = models.TextField()
    
    # Authorization
    allocated_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='fund_allocations'
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_allocations'
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-allocation_date']
        verbose_name = "Fund Allocation"
        verbose_name_plural = "Fund Allocations"
    
    @property
    def formatted_amount(self):
        return f"{self.source_account.currency.code} {self.amount_allocated:,.2f}"
    
    def __str__(self):
        return f"{self.source_account.name} → {self.budget.title} ({self.formatted_amount})"