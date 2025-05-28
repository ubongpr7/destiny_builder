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
from django.db.models import Sum, Q
from django.core.cache import cache

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
    """Organization's bank accounts with multi-currency support and enhanced features"""
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
    
    ACCOUNT_STATUS_CHOICES = [
        ('active', 'Active'),
        ('frozen', 'Frozen'),
        ('closed', 'Closed'),
        ('pending', 'Pending Activation'),
        ('suspended', 'Suspended'),
    ]
    
    RISK_LEVEL_CHOICES = [
        ('low', 'Low Risk'),
        ('medium', 'Medium Risk'),
        ('high', 'High Risk'),
    ]
    
    COMPLIANCE_STATUS_CHOICES = [
        ('compliant', 'Compliant'),
        ('pending_review', 'Pending Review'),
        ('non_compliant', 'Non-Compliant'),
        ('under_investigation', 'Under Investigation'),
    ]
    
    # Basic Account Information
    name = models.CharField(max_length=200)
    account_number = models.CharField(max_length=50, unique=True)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES)
    financial_institution = models.ForeignKey(
        'FinancialInstitution', 
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
    account_status = models.CharField(
        max_length=20, 
        choices=ACCOUNT_STATUS_CHOICES, 
        default='active',
        help_text="Current status of the account"
    )
    accepts_donations = models.BooleanField(
        default=True,
        help_text="Whether this account can receive donations"
    )
    opening_date = models.DateField()
    closing_date = models.DateField(blank=True, null=True)
    minimum_balance = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0
    )
    
    # Enhanced Banking Features
    online_banking_enabled = models.BooleanField(
        default=False,
        help_text="Whether online banking is enabled for this account"
    )
    mobile_banking_enabled = models.BooleanField(
        default=False,
        help_text="Whether mobile banking is enabled for this account"
    )
    debit_card_enabled = models.BooleanField(
        default=False,
        help_text="Whether a debit card is available for this account"
    )
    
    # Account Details and Identifiers
    routing_number = models.CharField(
        max_length=20, 
        blank=True, 
        null=True,
        help_text="Bank routing number (for US accounts)"
    )
    swift_code = models.CharField(
        max_length=11, 
        blank=True, 
        null=True,
        help_text="SWIFT/BIC code for international transfers"
    )
    iban = models.CharField(
        max_length=34, 
        blank=True, 
        null=True,
        help_text="International Bank Account Number"
    )
    branch_address = models.TextField(
        blank=True, 
        null=True,
        help_text="Physical address of the bank branch"
    )
    
    # Financial Features
    overdraft_protection = models.BooleanField(
        default=False,
        help_text="Whether overdraft protection is enabled"
    )
    overdraft_limit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Maximum overdraft amount allowed"
    )
    interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Annual interest rate (as decimal, e.g., 0.0250 for 2.5%)"
    )
    monthly_maintenance_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Monthly maintenance fee charged by the bank"
    )
    
    # Risk and Compliance
    risk_level = models.CharField(
        max_length=10,
        choices=RISK_LEVEL_CHOICES,
        default='low',
        help_text="Risk assessment level for this account"
    )
    compliance_status = models.CharField(
        max_length=20,
        choices=COMPLIANCE_STATUS_CHOICES,
        default='compliant',
        help_text="Compliance status with banking regulations"
    )
    
    # Reconciliation and Tracking
    last_reconciled_date = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Date when account was last reconciled"
    )
    auto_reconciliation_enabled = models.BooleanField(
        default=False,
        help_text="Whether automatic reconciliation is enabled"
    )
    last_transaction_date = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Date of the most recent transaction"
    )
    
    # Online account details (for digital payment platforms)
    api_key = models.CharField(max_length=255, blank=True, null=True)
    webhook_url = models.URLField(blank=True, null=True)
    
    # Additional Information
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Additional notes about this account"
    )
    
    # Tracking
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='created_accounts',
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['account_type', 'is_active']),
            models.Index(fields=['financial_institution', 'is_active']),
            models.Index(fields=['currency', 'is_active']),
            models.Index(fields=['accepts_donations', 'is_active']),
            models.Index(fields=['account_status']),
            models.Index(fields=['compliance_status']),
            models.Index(fields=['risk_level']),
        ]
        verbose_name = "Bank Account"
        verbose_name_plural = "Bank Accounts"
    
    @property
    def current_balance(self):
        """Calculate current balance from transactions with null safety"""
        try:
            credits = self.transactions.filter(
                transaction_type__in=['credit', 'transfer_in'],
                status='completed'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            debits = self.transactions.filter(
                transaction_type__in=['debit', 'transfer_out'],
                status='completed'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            return credits - debits
        except Exception:
            return Decimal('0.00')
    
    @property
    def formatted_balance(self):
        """Return balance formatted with currency"""
        if self.currency:
            return f"{self.currency.code} {self.current_balance:,.2f}"
        return f"{self.current_balance:,.2f}"
    
    @property
    def is_overdrawn(self):
        """Check if account is overdrawn"""
        return self.current_balance < 0
    
    @property
    def available_balance(self):
        """Calculate available balance including overdraft"""
        balance = self.current_balance
        if self.overdraft_protection and self.overdraft_limit:
            return balance + self.overdraft_limit
        return balance
    
    @property
    def is_low_balance(self):
        """Check if account has low balance (below minimum)"""
        return self.current_balance < (self.minimum_balance or Decimal('0.00'))
    
    @property
    def days_since_last_reconciliation(self):
        """Calculate days since last reconciliation"""
        if not self.last_reconciled_date:
            return None
        return (timezone.now() - self.last_reconciled_date).days
    
    @property
    def needs_reconciliation(self):
        """Check if account needs reconciliation (more than 30 days)"""
        days = self.days_since_last_reconciliation
        return days is None or days > 30
    
    @property
    def monthly_fee_due_date(self):
        """Calculate next monthly fee due date"""
        if not self.monthly_maintenance_fee:
            return None
        
        try:
            today = timezone.now().date()
            next_due = today.replace(day=self.opening_date.day)
            if next_due <= today:
                if next_due.month == 12:
                    next_due = next_due.replace(year=next_due.year + 1, month=1)
                else:
                    next_due = next_due.replace(month=next_due.month + 1)
            return next_due
        except (ValueError, AttributeError):
            return None
    
    @property
    def transaction_volume_30_days(self):
        """Calculate transaction volume for last 30 days"""
        try:
            from datetime import timedelta
            thirty_days_ago = timezone.now() - timedelta(days=30)
            volume = self.transactions.filter(
                transaction_date__gte=thirty_days_ago,
                status='completed'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            return volume
        except Exception:
            return Decimal('0.00')
    
    def save(self, *args, **kwargs):
        if not self.currency:
            currency = Currency.objects.filter(code='USD').first()
            self.currency = currency or Currency.objects.first() 
        super().save(*args, **kwargs)
    
    def __str__(self):
        currency_code = self.currency.code if self.currency else 'N/A'
        return f"{self.name} ({currency_code}) - {self.account_number[-4:]}"

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
        from_code = self.from_currency.code if self.from_currency else 'N/A'
        to_code = self.to_currency.code if self.to_currency else 'N/A'
        return f"1 {from_code} = {self.rate} {to_code}"

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
    
    # Bank accounts that can receive donations for this campaign
    bank_accounts = models.ManyToManyField(
        BankAccount,
        through='CampaignBankAccount',
        related_name='campaigns',
        blank=True,
        help_text="Bank accounts that can receive donations for this campaign"
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
    
    @property
    def current_amount_in_target_currency(self):
        """Calculate total raised in campaign's target currency including all donation types"""
        if not self.target_currency:
            return Decimal('0.00')
            
        total = Decimal('0.00')
        
        try:
            # Regular completed donations
            for donation in self.donations.filter(status='completed'):
                if donation.currency == self.target_currency:
                    total += donation.amount or Decimal('0.00')
                else:
                    converted_amount = donation.get_amount_in_currency(self.target_currency)
                    total += converted_amount or Decimal('0.00')
            
            # In-kind donations (received)
            for in_kind in self.in_kind_donations.filter(status='received'):
                if in_kind.valuation_currency == self.target_currency:
                    total += in_kind.estimated_value or Decimal('0.00')
                else:
                    try:
                        exchange_rate = ExchangeRate.objects.filter(
                            from_currency=in_kind.valuation_currency,
                            to_currency=self.target_currency,
                            effective_date__lte=in_kind.donation_date
                        ).order_by('-effective_date').first()
                        
                        if exchange_rate and in_kind.estimated_value:
                            total += in_kind.estimated_value * exchange_rate.rate
                        else:
                            total += in_kind.estimated_value or Decimal('0.00')
                    except Exception:
                        total += in_kind.estimated_value or Decimal('0.00')
            
            # Recurring donations (total donated so far)
            for recurring in self.recurring_donations.filter(status__in=['active', 'completed']):
                if recurring.currency == self.target_currency:
                    total += recurring.total_donated or Decimal('0.00')
                else:
                    try:
                        exchange_rate = ExchangeRate.objects.filter(
                            from_currency=recurring.currency,
                            to_currency=self.target_currency
                        ).order_by('-effective_date').first()
                        
                        if exchange_rate and recurring.total_donated:
                            total += recurring.total_donated * exchange_rate.rate
                        else:
                            total += recurring.total_donated or Decimal('0.00')
                    except Exception:
                        total += recurring.total_donated or Decimal('0.00')
        except Exception:
            pass
        
        return total
    
    @property
    def progress_percentage(self):
        if self.target_amount and self.target_amount > 0:
            current = self.current_amount_in_target_currency
            return min((current / self.target_amount) * 100, 100)
        return 0
    
    @property
    def is_completed(self):
        return self.current_amount_in_target_currency >= (self.target_amount or Decimal('0.00'))
    
    def __str__(self):
        return self.title

class CampaignBankAccount(models.Model):
    """Through model for campaign-bank account relationship"""
    campaign = models.ForeignKey(
        DonationCampaign,
        on_delete=models.CASCADE,
        related_name='campaign_bank_accounts'
    )
    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.CASCADE,
        related_name='campaign_bank_accounts'
    )
    
    # Additional metadata for the relationship
    is_primary = models.BooleanField(
        default=False,
        help_text="Primary account for this campaign"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this account is currently accepting donations for this campaign"
    )
    priority_order = models.PositiveIntegerField(
        default=1,
        help_text="Display order for donation options (1 = highest priority)"
    )
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Special instructions for this account"
    )
    
    # Tracking
    added_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='added_campaign_accounts'
    )
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['campaign', 'bank_account']
        ordering = ['priority_order', 'bank_account__name']
        verbose_name = "Campaign Bank Account"
        verbose_name_plural = "Campaign Bank Accounts"
    
    def __str__(self):
        return f"{self.campaign.title} - {self.bank_account.name}"

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
        ('fundraising_event', 'Fundraising Event'),
        ('corporate_sponsorship', 'Corporate Sponsorship'),
        ('foundation_grant', 'Foundation Grant'),
        ('crowdfunding', 'Crowdfunding'),
        ('other', 'Other'),
    ]
    
    name = models.CharField(max_length=200)
    funding_type = models.CharField(max_length=100, choices=FUNDING_TYPE_CHOICES)
    description = models.TextField(blank=True, null=True)
    
    # Link to existing models
    donation = models.ForeignKey(
        'Donation', 
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
        'Grant', 
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
    
    # Dates and restrictions
    available_from = models.DateField(
        blank=True,
        null=True,
        help_text="Date when funds become available"
    )
    available_until = models.DateField(
        blank=True,
        null=True,
        help_text="Date when funds expire if not used"
    )
    restrictions = models.TextField(
        blank=True,
        null=True,
        help_text="Any restrictions on how these funds can be used"
    )
    
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='created_funding_sources',
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['funding_type', 'is_active']),
            models.Index(fields=['currency', 'is_active']),
            models.Index(fields=['available_from', 'available_until']),
        ]
        verbose_name = "Funding Source"
        verbose_name_plural = "Funding Sources"
    
    @property
    def amount_allocated(self):
        """Calculate total allocated from budget funding relationships"""
        try:
            return self.budget_funding.aggregate(
                total=Sum('amount_allocated')
            )['total'] or Decimal('0.00')
        except Exception:
            return Decimal('0.00')
    
    @property
    def amount_remaining(self):
        available = self.amount_available or Decimal('0.00')
        allocated = self.amount_allocated
        return available - allocated
    
    @property
    def formatted_amount(self):
        if self.currency:
            return f"{self.currency.code} {self.amount_available:,.2f}"
        else:
            return f"{self.amount_available:,.2f}"
    
    @property
    def is_expired(self):
        if self.available_until:
            return timezone.now().date() > self.available_until
        return False
    
    @property
    def is_available_now(self):
        now = timezone.now().date()
        if self.available_from and now < self.available_from:
            return False
        if self.available_until and now > self.available_until:
            return False
        return self.is_active and self.amount_remaining > 0
    
    def __str__(self):
        return f"{self.name} ({self.get_funding_type_display()}) - {self.formatted_amount}"

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
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name='donations',
        help_text="Currency of the donation",
        null=True,
        blank=True
    )
    
    # Exchange rate and conversion
    exchange_rate = models.DecimalField(
        max_digits=15,
        decimal_places=8,
        null=True,
        blank=True,
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

    # Receipt management
    receipt_image = models.ImageField(
        upload_to='donation_receipts/',
        blank=True,
        null=True,
        help_text="Upload receipt or proof of donation"
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
    
    @property
    def net_amount(self):
        """Amount after processor fees"""
        amount = self.amount or Decimal('0.00')
        fee = self.processor_fee or Decimal('0.00')
        return amount - fee
    
    @property
    def donor_name_display(self):
        if self.is_anonymous:
            return "Anonymous"
        if self.donor:
            return self.donor.get_full_name or self.donor.username
        return self.donor_name or "Unknown"
    
    @property
    def formatted_amount(self):
        if self.currency:
            return f"{self.currency.code} {self.amount:,.2f}"
        return f"{self.amount:,.2f}"
    
    def get_amount_in_currency(self, target_currency):
        """Convert donation amount to specified currency"""
        if not target_currency or not self.currency:
            return self.amount or Decimal('0.00')
            
        if self.currency == target_currency:
            return self.amount or Decimal('0.00')
        
        try:
            exchange_rate = ExchangeRate.objects.filter(
                from_currency=self.currency,
                to_currency=target_currency,
                effective_date__lte=self.donation_date or timezone.now()
            ).order_by('-effective_date').first()
            
            if exchange_rate and self.amount:
                return self.amount * exchange_rate.rate
        except Exception:
            pass
        
        return self.amount or Decimal('0.00')
    
    def save(self, *args, **kwargs):
        if self.transaction_id == '':
            self.transaction_id = None
        super().save(*args, **kwargs)
    
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

    # Receipt management
    receipt_image = models.ImageField(
        upload_to='recurring_donation_receipts/',
        blank=True,
        null=True,
        help_text="Upload receipt or proof of recurring donation setup"
    )

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
        if self.currency:
            return f"{self.currency.code} {self.amount:,.2f}"
        return f"{self.amount:,.2f}"
    
    def __str__(self):
        donor_name = self.donor.get_full_name or self.donor.username
        return f"{donor_name} - {self.formatted_amount} {self.frequency}"

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
    receipt_image = models.ImageField(
        upload_to='in_kind_donation_receipts/', 
        blank=True, 
        null=True,
        help_text="Upload receipt or photo of in-kind donation"
    )
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
            return self.donor.get_full_name or self.donor.username
        return self.donor_name or "Unknown"
    
    @property
    def formatted_value(self):
        if self.valuation_currency:
            return f"{self.valuation_currency.code} {self.estimated_value:,.2f}"
        return f"{self.estimated_value:,.2f}"
    
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
        amount = self.amount or Decimal('0.00')
        received = self.amount_received or Decimal('0.00')
        return amount - received
    
    @property
    def formatted_amount(self):
        if self.currency:
            return f"{self.currency.code} {self.amount:,.2f}"
        return f"{self.amount:,.2f}"
    
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
        blank=True,
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
    def spent_amount(self):
        """Calculate total spent from all budget items"""
        try:
            return self.items.aggregate(
                total=Sum('spent_amount')
            )['total'] or Decimal('0.00')
        except Exception:
            return Decimal('0.00')
    
    @property
    def allocated_amount(self):
        """Total amount allocated to budget items"""
        try:
            return self.items.aggregate(
                total=Sum('budgeted_amount')
            )['total'] or Decimal('0.00')
        except Exception:
            return Decimal('0.00')
    
    @property
    def remaining_amount(self):
        total = self.total_amount or Decimal('0.00')
        spent = self.spent_amount
        return total - spent
    
    @property
    def unallocated_amount(self):
        """Amount not yet allocated to budget items"""
        total = self.total_amount or Decimal('0.00')
        allocated = self.allocated_amount
        return total - allocated
    
    @property
    def spent_percentage(self):
        total = self.total_amount or Decimal('0.00')
        if total > 0:
            spent = self.spent_amount
            return float((spent / total) * 100)
        return 0
    
    @property
    def allocation_percentage(self):
        """Percentage of total budget allocated to items"""
        total = self.total_amount or Decimal('0.00')
        if total > 0:
            allocated = self.allocated_amount
            return float((allocated / total) * 100)
        return 0
    
    @property
    def variance(self):
        """Budget variance (positive = under budget, negative = over budget)"""
        total = self.total_amount or Decimal('0.00')
        spent = self.spent_amount
        return total - spent
    
    @property
    def variance_percentage(self):
        """Variance as percentage"""
        total = self.total_amount or Decimal('0.00')
        if total > 0:
            variance = self.variance
            return float((variance / total) * 100)
        return 0
    
    @property
    def budget_health(self):
        """Overall budget health status"""
        percentage = self.spent_percentage
        if percentage >= 100:
            return 'OVER_BUDGET'
        elif percentage >= 90:
            return 'CRITICAL'
        elif percentage >= 75:
            return 'WARNING'
        elif percentage >= 50:
            return 'MODERATE'
        else:
            return 'HEALTHY'
    
    @property
    def is_over_budget(self):
        """Check if budget is over spent"""
        return self.spent_amount > (self.total_amount or Decimal('0.00'))
    
    @property
    def is_fully_allocated(self):
        """Check if all budget is allocated to items"""
        return self.allocated_amount >= (self.total_amount or Decimal('0.00'))
    
    @property
    def total_funding_allocated(self):
        try:
            return self.budget_funding.aggregate(
                total=Sum('amount_allocated')
            )['total'] or Decimal('0.00')
        except Exception:
            return Decimal('0.00')
    
    @property
    def funding_gap(self):
        """Amount still needed from funding sources"""
        total = self.total_amount or Decimal('0.00')
        funded = self.total_funding_allocated
        gap = total - funded
        return max(Decimal('0.00'), gap)
    
    @property
    def is_fully_funded(self):
        """Check if budget is fully funded"""
        return self.total_funding_allocated >= (self.total_amount or Decimal('0.00'))
    
    @property
    def days_remaining(self):
        """Days remaining in budget period"""
        if self.end_date:
            today = timezone.now().date()
            if today <= self.end_date:
                return (self.end_date - today).days
        return 0
    
    @property
    def is_expired(self):
        """Check if budget period has ended"""
        return timezone.now().date() > self.end_date
    
    @property
    def progress_percentage(self):
        """Time progress percentage"""
        if self.start_date and self.end_date:
            today = timezone.now().date()
            total_days = (self.end_date - self.start_date).days
            if total_days > 0:
                elapsed_days = (today - self.start_date).days
                return min(max(float((elapsed_days / total_days) * 100), 0), 100)
        return 0
    
    @property
    def burn_rate(self):
        """Daily spending rate"""
        if self.start_date:
            today = timezone.now().date()
            days_elapsed = (today - self.start_date).days
            if days_elapsed > 0:
                return self.spent_amount / days_elapsed
        return Decimal('0.00')
    
    @property
    def projected_total_spend(self):
        """Projected total spend based on current burn rate"""
        burn_rate = self.burn_rate
        if burn_rate > 0 and self.end_date:
            total_days = (self.end_date - self.start_date).days
            return burn_rate * total_days
        return self.spent_amount
    
    @property
    def formatted_amount(self):
        if self.currency:
            return f"{self.currency.code} {self.total_amount:,.2f}"
        return f"{self.total_amount:,.2f}"
    
    @property
    def formatted_spent_amount(self):
        if self.currency:
            return f"{self.currency.code} {self.spent_amount:,.2f}"
        return f"{self.spent_amount:,.2f}"
    
    @property
    def formatted_remaining_amount(self):
        if self.currency:
            return f"{self.currency.code} {self.remaining_amount:,.2f}"
        return f"{self.remaining_amount:,.2f}"
    
    @property
    def formatted_variance(self):
        variance = self.variance
        sign = "+" if variance >= 0 else ""
        if self.currency:
            return f"{sign}{self.currency.code} {variance:,.2f}"
        return f"{sign}{variance:,.2f}"
    
    @property
    def budget_summary(self):
        """Comprehensive budget summary"""
        return {
            'total_budget': self.total_amount,
            'allocated': self.allocated_amount,
            'spent': self.spent_amount,
            'remaining': self.remaining_amount,
            'funded': self.total_funding_allocated,
            'funding_gap': self.funding_gap,
            'spent_percentage': self.spent_percentage,
            'allocation_percentage': self.allocation_percentage,
            'health_status': self.budget_health,
            'days_remaining': self.days_remaining,
            'currency': self.currency.code if self.currency else None
        }
    
    # RESTORED METHODS - These were missing and causing the error
    def get_funding_breakdown(self):
        """Get detailed funding breakdown by source"""
        try:
            funding_data = []
            for funding in self.budget_funding.select_related('funding_source', 'funding_source__currency'):
                funding_data.append({
                    'source_name': funding.funding_source.name,
                    'source_type': funding.funding_source.get_funding_type_display(),
                    'amount_allocated': str(funding.amount_allocated),
                    'currency': funding.funding_source.currency.code if funding.funding_source.currency else None,
                    'allocation_date': funding.allocation_date.isoformat() if funding.allocation_date else None,
                    'percentage_of_budget': float((funding.amount_allocated / self.total_amount) * 100) if self.total_amount > 0 else 0
                })
            return funding_data
        except Exception:
            return []
    
    def get_spending_by_category(self):
        """Get spending breakdown by budget item category"""
        try:
            from django.db.models import Sum
            categories = self.items.values('category').annotate(
                total_budgeted=Sum('budgeted_amount'),
                total_spent=Sum('spent_amount')
            ).order_by('category')
            
            category_data = []
            for category in categories:
                category_data.append({
                    'category': category['category'],
                    'budgeted_amount': str(category['total_budgeted'] or Decimal('0.00')),
                    'spent_amount': str(category['total_spent'] or Decimal('0.00')),
                    'remaining_amount': str((category['total_budgeted'] or Decimal('0.00')) - (category['total_spent'] or Decimal('0.00'))),
                    'spent_percentage': float(((category['total_spent'] or Decimal('0.00')) / (category['total_budgeted'] or Decimal('1.00'))) * 100) if category['total_budgeted'] and category['total_budgeted'] > 0 else 0
                })
            return category_data
        except Exception:
            return []
    
    def get_monthly_spending_trend(self):
        """Get monthly spending trend for this budget"""
        try:
            from django.db.models import Sum
            from django.db.models.functions import TruncMonth
            from datetime import datetime, timedelta
            
            # Get spending data for the last 12 months or budget period
            start_date = max(
                self.start_date,
                (timezone.now().date() - timedelta(days=365))
            )
            
            monthly_data = self.items.filter(
                project_expenses__expense_date__gte=start_date,
                project_expenses__expense_date__lte=self.end_date
            ).annotate(
                month=TruncMonth('project_expenses__expense_date')
            ).values('month').annotate(
                total_spent=Sum('project_expenses__amount')
            ).order_by('month')
            
            trend_data = []
            for month_data in monthly_data:
                if month_data['month']:
                    trend_data.append({
                        'month': month_data['month'].strftime('%Y-%m'),
                        'spent_amount': str(month_data['total_spent'] or Decimal('0.00')),
                        'currency': self.currency.code if self.currency else None
                    })
            return trend_data
        except Exception:
            return []
    
    def get_budget_utilization_by_item(self):
        """Get utilization percentage for each budget item"""
        try:
            items_data = []
            for item in self.items.all():
                utilization = 0
                if item.budgeted_amount and item.budgeted_amount > 0:
                    utilization = float((item.spent_amount / item.budgeted_amount) * 100)
                
                items_data.append({
                    'id': item.id,
                    'category': item.category,
                    'subcategory': item.subcategory or '',
                    'description': item.description,
                    'budgeted_amount': str(item.budgeted_amount),
                    'spent_amount': str(item.spent_amount),
                    'remaining_amount': str(item.remaining_amount),
                    'utilization_percentage': utilization,
                    'status': item.utilization_status,
                    'is_locked': item.is_locked,
                    'responsible_person': item.responsible_person.get_full_name if item.responsible_person else None
                })
            return items_data
        except Exception:
            return []
    
    def get_funding_vs_spending_analysis(self):
        """Compare funding received vs actual spending"""
        try:
            return {
                'total_budget': str(self.total_amount),
                'total_funded': str(self.total_funding_allocated),
                'total_spent': str(self.spent_amount),
                'funding_gap': str(self.funding_gap),
                'spending_vs_funding_ratio': float((self.spent_amount / self.total_funding_allocated) * 100) if self.total_funding_allocated > 0 else 0,
                'budget_utilization': self.spent_percentage,
                'funding_utilization': float((self.total_funding_allocated / self.total_amount) * 100) if self.total_amount > 0 else 0,
                'is_overspent': self.is_over_budget,
                'is_underfunded': not self.is_fully_funded,
                'currency': self.currency.code if self.currency else None
            }
        except Exception:
            return {}
    
    def get_budget_alerts(self):
        """Get budget alerts and warnings"""
        alerts = []
        
        try:
            # Over budget alert
            if self.is_over_budget:
                alerts.append({
                    'type': 'error',
                    'message': f'Budget is over spent by {self.currency.code if self.currency else ""} {abs(self.variance):,.2f}',
                    'severity': 'high'
                })
            
            # High utilization warning
            elif self.spent_percentage >= 90:
                alerts.append({
                    'type': 'warning',
                    'message': f'Budget is {self.spent_percentage:.1f}% utilized - approaching limit',
                    'severity': 'medium'
                })
            
            # Funding gap alert
            if self.funding_gap > 0:
                alerts.append({
                    'type': 'warning',
                    'message': f'Funding gap of {self.currency.code if self.currency else ""} {self.funding_gap:,.2f}',
                    'severity': 'medium'
                })
            
            # Expiring budget
            if self.days_remaining <= 30 and self.days_remaining > 0:
                alerts.append({
                    'type': 'info',
                    'message': f'Budget expires in {self.days_remaining} days',
                    'severity': 'low'
                })
            
            # Expired budget
            if self.is_expired:
                alerts.append({
                    'type': 'error',
                    'message': 'Budget period has expired',
                    'severity': 'high'
                })
            
        except Exception:
            pass
        
        return alerts
    
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
        currency_code = self.funding_source.currency.code if self.funding_source.currency else 'N/A'
        return f"{self.budget.title} - {self.funding_source.name} ({currency_code} {self.amount_allocated:,.2f})"

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
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_budget_items')
    
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
    def spent_amount(self):
        """Calculate total spent from related expenses"""
        try:
            return self.project_expenses.aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0.00')
        except Exception:
            return Decimal('0.00')

    @property
    def utilization_status(self):
        """Returns budget utilization status"""
        percentage = self.spent_percentage
        if percentage >= 100:
            return 'OVER_BUDGET'
        elif percentage >= 90:
            return 'CRITICAL'
        elif percentage >= 75:
            return 'WARNING'
        else:
            return 'NORMAL'

    @property
    def is_over_budget(self):
        """Check if spending exceeds budget"""
        return self.spent_amount > (self.budgeted_amount or Decimal('0.00'))

    @property
    def variance(self):
        """Budget variance (positive = under budget, negative = over budget)"""
        budgeted = self.budgeted_amount or Decimal('0.00')
        spent = self.spent_amount
        return budgeted - spent

    @property
    def variance_percentage(self):
        """Variance as percentage"""
        budgeted = self.budgeted_amount or Decimal('0.00')
        if budgeted > 0:
            variance = self.variance
            return float((variance / budgeted) * 100)
        return 0

    @property
    def remaining_amount(self):
        budgeted = self.budgeted_amount or Decimal('0.00')
        spent = self.spent_amount
        return budgeted - spent
    
    @property
    def spent_percentage(self):
        budgeted = self.budgeted_amount or Decimal('0.00')
        if budgeted > 0:
            spent = self.spent_amount
            return float((spent / budgeted) * 100)
        return 0
    
    @property
    def formatted_amount(self):
        if self.budget and self.budget.currency:
            return f"{self.budget.currency.code} {self.budgeted_amount:,.2f}"
        return f"{self.budgeted_amount:,.2f}"

    @property
    def formatted_spent_amount(self):
        if self.budget and self.budget.currency:
            return f"{self.budget.currency.code} {self.spent_amount:,.2f}"
        return f"{self.spent_amount:,.2f}"

    @property
    def formatted_remaining_amount(self):
        if self.budget and self.budget.currency:
            return f"{self.budget.currency.code} {self.remaining_amount:,.2f}"
        return f"{self.remaining_amount:,.2f}"

    @property
    def can_spend(self):
        """Check if item allows spending (not locked and has remaining budget)"""
        return not self.is_locked and self.remaining_amount > 0

    @property
    def available_without_approval(self):
        """Maximum amount that can be spent without approval"""
        if not self.approval_required_threshold:
            return self.remaining_amount
        return min(self.remaining_amount, self.approval_required_threshold or Decimal('0.00'))
    
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
        blank=True,
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
        if self.currency:
            return f"{self.currency.code} {self.amount:,.2f}"
        return f"{self.amount:,.2f}"
    
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
    
    # Authorization
    authorized_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='authorized_transactions',
        null=True,
        blank=True,
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
    
    @property
    def net_amount(self):
        """Amount after processor fees"""
        amount = self.amount or Decimal('0.00')
        fee = self.processor_fee or Decimal('0.00')
        return amount - fee
    
    @property
    def formatted_amount(self):
        currency_info = ""
        if self.original_currency and self.original_currency != self.account.currency:
            if self.original_amount:
                currency_info = f" (from {self.original_currency.code} {self.original_amount:,.2f})"
        
        account_currency = self.account.currency.code if self.account.currency else 'N/A'
        return f"{account_currency} {self.amount:,.2f}{currency_info}"
    
    def save(self, *args, **kwargs):
        # Auto-calculate net amount if processor fee is provided
        if self.processor_fee and not hasattr(self, '_net_amount_calculated'):
            self._net_amount_calculated = True
        super().save(*args, **kwargs)
    
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
        currency_code = self.source_account.currency.code if self.source_account.currency else 'N/A'
        return f"{currency_code} {self.amount_allocated:,.2f}"
    
    def __str__(self):
        return f"{self.source_account.name} → {self.budget.title} ({self.formatted_amount})"
