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
    
    # def clean(self):
    #     """Validate account data"""
    #     super().clean()
        
    #     # Validate overdraft limit only if overdraft protection is enabled
    #     if self.overdraft_protection and not self.overdraft_limit:
    #         raise ValidationError("Overdraft limit is required when overdraft protection is enabled")
        
    #     # Validate closing date is after opening date
    #     if self.closing_date and self.closing_date <= self.opening_date:
    #         raise ValidationError("Closing date must be after opening date")
        
    #     # Validate IBAN format (basic check)
    #     if self.iban and len(self.iban) < 15:
    #         raise ValidationError("IBAN must be at least 15 characters long")
        
    #     # Validate SWIFT code format (basic check)
    #     if self.swift_code and len(self.swift_code) not in [8, 11]:
    #         raise ValidationError("SWIFT code must be 8 or 11 characters long")
    
    @property
    def current_balance(self):
        """Calculate current balance from transactions"""
        from django.db.models import Sum, Q
        
        credits = self.transactions.filter(
            transaction_type__in=['credit', 'transfer_in'],
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        debits = self.transactions.filter(
            transaction_type__in=['debit', 'transfer_out'],
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        return credits - debits
    
    @property
    def formatted_balance(self):
        """Return balance formatted with currency"""
        return f"{self.currency.code} {self.current_balance:,.2f}"
    
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
        return self.current_balance < self.minimum_balance
    
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
        
        from datetime import datetime
        today = timezone.now().date()
        # Assume fee is due on the same day each month as opening date
        try:
            next_due = today.replace(day=self.opening_date.day)
            if next_due <= today:
                # Move to next month
                if next_due.month == 12:
                    next_due = next_due.replace(year=next_due.year + 1, month=1)
                else:
                    next_due = next_due.replace(month=next_due.month + 1)
            return next_due
        except ValueError:
            # Handle cases where opening day doesn't exist in current month (e.g., Feb 30)
            return None
    
    @property
    def transaction_volume_30_days(self):
        """Calculate transaction volume for last 30 days"""
        from datetime import timedelta
        from django.db.models import Sum
        
        thirty_days_ago = timezone.now() - timedelta(days=30)
        volume = self.transactions.filter(
            transaction_date__gte=thirty_days_ago,
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        return volume
    
    @property
    def average_monthly_balance(self):
        """Calculate average balance over the last 3 months (simplified)"""
        # This is a simplified calculation - in practice, you'd want daily balance snapshots
        return self.current_balance  # Placeholder - implement proper calculation
    
    def update_last_transaction_date(self):
        """Update the last transaction date"""
        latest_transaction = self.transactions.filter(
            status='completed'
        ).order_by('-transaction_date').first()
        
        if latest_transaction:
            self.last_transaction_date = latest_transaction.transaction_date
            self.save(update_fields=['last_transaction_date'])
    
    def mark_reconciled(self, reconciled_by=None):
        """Mark account as reconciled"""
        self.last_reconciled_date = timezone.now()
        if reconciled_by:
            # You might want to add a reconciled_by field to track who reconciled
            pass
        self.save(update_fields=['last_reconciled_date'])
    
    def freeze_account(self, reason=None):
        """Freeze the account"""
        self.account_status = 'frozen'
        self.is_active = False
        if reason and self.notes:
            self.notes = f"FROZEN: {reason}\n{self.notes}"
        elif reason:
            self.notes = f"FROZEN: {reason}"
        self.save(update_fields=['account_status', 'is_active', 'notes'])
    
    def unfreeze_account(self):
        """Unfreeze the account"""
        self.account_status = 'active'
        self.is_active = True
        self.save(update_fields=['account_status', 'is_active'])
    
    def close_account(self, closing_date=None):
        """Close the account"""
        self.account_status = 'closed'
        self.is_active = False
        self.closing_date = closing_date or timezone.now().date()
        self.save(update_fields=['account_status', 'is_active', 'closing_date'])
    # def save(self, *args, **kwargs):
    #     if not self.currency:
    #         currency = Currency.objects.filter(code='USD').first()
    #         self.currency = currency or Currency.objects.first()           
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
    
    def __str__(self):
        return self.title
    
    @property
    def current_amount_in_target_currency(self):
        """Calculate total raised in campaign's target currency including all donation types"""
        total = Decimal('0.00')
        
        # Regular completed donations
        for donation in self.donations.filter(status='completed'):
            if donation.currency == self.target_currency:
                total += donation.amount
            else:
                converted_amount = donation.get_amount_in_currency(self.target_currency)
                total += converted_amount
        
        # In-kind donations (received)
        for in_kind in self.in_kind_donations.filter(status='received'):
            if in_kind.valuation_currency == self.target_currency:
                total += in_kind.estimated_value
            else:
                # Convert using exchange rate
                try:
                    exchange_rate = ExchangeRate.objects.filter(
                        from_currency=in_kind.valuation_currency,
                        to_currency=self.target_currency,
                        effective_date__lte=in_kind.donation_date
                    ).order_by('-effective_date').first()
                    
                    if exchange_rate:
                        total += in_kind.estimated_value * exchange_rate.rate
                    else:
                        # If no exchange rate found, add original amount
                        total += in_kind.estimated_value
                except ExchangeRate.DoesNotExist:
                    total += in_kind.estimated_value
        
        # Recurring donations (total donated so far)
        for recurring in self.recurring_donations.filter(status__in=['active', 'completed']):
            if recurring.currency == self.target_currency:
                total += recurring.total_donated
            else:
                # Convert using latest exchange rate
                try:
                    exchange_rate = ExchangeRate.objects.filter(
                        from_currency=recurring.currency,
                        to_currency=self.target_currency
                    ).order_by('-effective_date').first()
                    
                    if exchange_rate:
                        total += recurring.total_donated * exchange_rate.rate
                    else:
                        # If no exchange rate found, add original amount
                        total += recurring.total_donated
                except ExchangeRate.DoesNotExist:
                    total += recurring.total_donated
        
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
    
    def get_available_bank_accounts(self):
        """Get bank accounts available for donations to this campaign"""
        return self.bank_accounts.filter(
            is_active=True,
            accepts_donations=True
        ).select_related('financial_institution', 'currency')
    
    def get_bank_accounts_by_currency(self):
        """Get bank accounts grouped by currency"""
        accounts = self.get_available_bank_accounts()
        grouped = {}
        for account in accounts:
            currency_code = account.currency.code
            if currency_code not in grouped:
                grouped[currency_code] = []
            grouped[currency_code].append(account)
        return grouped

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
    amount_allocated = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(Decimal('0.00'))]
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
    def amount_remaining(self):
        return self.amount_available - self.amount_allocated
    
    @property
    def formatted_amount(self):
        return f"{self.currency.code} {self.amount_available:,.2f}"
    
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
    donation_date = models.DateTimeField(null=True,blank=True)
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
    
    def save(self, *args, **kwargs):
        if self.transaction_id == '':
            self.transaction_id = None
        
        # Auto-calculate net amount if not provided
        if not self.net_amount and self.processor_fee:
            self.net_amount = self.amount - self.processor_fee
        elif not self.net_amount:
            self.net_amount = self.amount
            
        super().save(*args, **kwargs)
        
        # Auto-create funding source if this is a completed donation
        if self.status == 'completed' and not hasattr(self, '_funding_source_created'):
            self._create_funding_source()
    
    def _create_funding_source(self):
        """Create a funding source for this donation"""
        funding_source, created = FundingSource.objects.get_or_create(
            donation=self,
            defaults={
                'name': f"Donation from {self.donor_name_display}",
                'funding_type': 'donation',
                'description': f"Individual donation of {self.formatted_amount}",
                'amount_available': self.net_amount or self.amount,
                'currency': self.currency,
                'created_by': self.processed_by or self.donor,
            }
        )
        self._funding_source_created = True
        return funding_source
    
    def get_amount_in_currency(self, target_currency):
        """Convert donation amount to specified currency"""
        if self.currency == target_currency:
            return self.amount
        
        # Try to find exchange rate
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
            return self.donor.get_full_name or self.donor.username
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
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        
        # Auto-create funding source for active recurring donations
        if self.status == 'active' and not hasattr(self, '_funding_source_created'):
            self._create_funding_source()
    
    def _create_funding_source(self):
        """Create a funding source for this recurring donation"""
        # Calculate projected annual amount
        multiplier = {
            'weekly': 52,
            'monthly': 12,
            'quarterly': 4,
            'biannually': 2,
            'annually': 1
        }
        
        projected_annual = self.amount * multiplier.get(self.frequency, 12)
        
        funding_source, created = FundingSource.objects.get_or_create(
            name=f"Recurring Donation - {self.donor.get_full_name or self.donor.username}",
            funding_type='donation',
            defaults={
                'description': f"Recurring {self.frequency} donation of {self.currency.code} {self.amount}",
                'amount_available': projected_annual,
                'currency': self.currency,
                'available_from': self.start_date,
                'available_until': self.end_date,
                'created_by': self.donor,
            }
        )
        self._funding_source_created = True
        return funding_source
    
    @property
    def formatted_amount(self):
        return f"{self.currency.code} {self.amount:,.2f}"
    
    def __str__(self):
        return f"{self.donor.get_full_name or self.donor.username} - {self.formatted_amount} {self.frequency}"

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
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        
        # Auto-create funding source for received in-kind donations
        if self.status == 'received' and not hasattr(self, '_funding_source_created'):
            self._create_funding_source()
    
    def _create_funding_source(self):
        """Create a funding source for this in-kind donation"""
        funding_source, created = FundingSource.objects.get_or_create(
            name=f"In-Kind: {self.item_description[:50]}...",
            funding_type='donation',
            defaults={
                'description': f"In-kind donation: {self.item_description}",
                'amount_available': self.estimated_value,
                'currency': self.valuation_currency,
                'created_by': self.received_by or self.donor,
            }
        )
        self._funding_source_created = True
        return funding_source
    
    @property
    def donor_name_display(self):
        if self.is_anonymous:
            return "Anonymous"
        if self.donor:
            return self.donor.get_full_name or self.donor.username
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
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        
        # Auto-create funding source for approved/active grants
        if self.status in ['approved', 'active'] and not hasattr(self, '_funding_source_created'):
            self._create_funding_source()
    
    def _create_funding_source(self):
        """Create a funding source for this grant"""
        funding_source, created = FundingSource.objects.get_or_create(
            grant=self,
            defaults={
                'name': f"Grant: {self.title}",
                'funding_type': 'grant',
                'description': f"Grant from {self.grantor}",
                'amount_available': self.amount,
                'currency': self.currency,
                'available_from': self.start_date,
                'available_until': self.end_date,
                'restrictions': self.requirements,
                'created_by': self.created_by,
            }
        )
        self._funding_source_created = True
        return funding_source
    
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
    
    def save(self, *args, **kwargs):
        # Auto-calculate net amount if processor fee is provided
        if self.processor_fee and not self.net_amount:
            self.net_amount = self.amount - self.processor_fee
        super().save(*args, **kwargs)
    
    @property
    def formatted_amount(self):
        currency_info = ""
        if self.original_currency and self.original_currency != self.account.currency:
            if self.original_amount:
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
