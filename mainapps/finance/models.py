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
    """Enhanced fundraising campaigns with comprehensive donation tracking"""
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    CAMPAIGN_TYPE_CHOICES = [
        ('general', 'General Fundraising'),
        ('emergency', 'Emergency Response'),
        ('project_specific', 'Project Specific'),
        ('capacity_building', 'Capacity Building'),
        ('equipment', 'Equipment Purchase'),
        ('scholarship', 'Scholarship Fund'),
        ('research', 'Research Initiative'),
        ('community_outreach', 'Community Outreach'),
    ]
    
    # Basic Information
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField()
    campaign_type = models.CharField(max_length=20, choices=CAMPAIGN_TYPE_CHOICES, default='general')
    
    # Financial Goals
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
        blank=False
    )
    minimum_goal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Minimum amount needed for campaign success"
    )
    
    # Timeline
    start_date = models.DateField()
    end_date = models.DateField()
    launch_date = models.DateTimeField(null=True, blank=True)
    
    # Relationships
    project = models.ForeignKey(
        Project, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='campaigns'
    )
    
    # Campaign Settings
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    is_featured = models.BooleanField(default=False)
    allow_anonymous_donations = models.BooleanField(default=True)
    allow_recurring_donations = models.BooleanField(default=True)
    allow_in_kind_donations = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    # Media
    image = models.FileField(upload_to='campaign_images/', blank=True, null=True)
    video = models.FileField(upload_to='campaign_videos/',blank=True, null=True)
    
    # Management
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='created_campaigns'
    )
    managed_by = models.ManyToManyField(
        User,
        blank=True,
        related_name='managed_campaigns',
        help_text="Users who can manage this campaign"
    )
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'start_date']),
            models.Index(fields=['campaign_type', 'status']),
            models.Index(fields=['target_currency']),
            models.Index(fields=['is_featured', 'status']),
        ]
        verbose_name = "Donation Campaign"
        verbose_name_plural = "Donation Campaigns"
    
    # ============================================================================
    # CORE DONATION AMOUNT CALCULATIONS
    # ============================================================================
    
    @property
    def total_donations_amount(self):
        """Total from one-time donations in target currency"""
        total = Decimal('0.00')
        try:
            for donation in self.donations.filter(status='completed'):
                total += self._convert_to_target_currency(
                    donation.amount, 
                    donation.currency, 
                    donation.donation_date
                )
        except Exception:
            pass
        return total
    
    @property
    def total_recurring_amount(self):
        """Total from recurring donations in target currency"""
        total = Decimal('0.00')
        try:
            for recurring in self.recurring_donations.filter(status__in=['active', 'completed']):
                total += self._convert_to_target_currency(
                    recurring.total_donated,
                    recurring.currency,
                    timezone.now()
                )
        except Exception:
            pass
        return total
    
    @property
    def total_in_kind_amount(self):
        """Total from in-kind donations in target currency"""
        total = Decimal('0.00')
        try:
            for in_kind in self.in_kind_donations.filter(status='received'):
                total += self._convert_to_target_currency(
                    in_kind.estimated_value,
                    in_kind.valuation_currency,
                    in_kind.donation_date
                )
        except Exception:
            pass
        return total
    
    @property
    def current_amount(self):
        """Total raised across all donation types in target currency"""
        return (self.total_donations_amount + 
                self.total_recurring_amount + 
                self.total_in_kind_amount)
    
    @property
    def net_donations_amount(self):
        """Net amount after processor fees from one-time donations"""
        total = Decimal('0.00')
        try:
            for donation in self.donations.filter(status='completed'):
                net_amount = donation.net_amount
                total += self._convert_to_target_currency(
                    net_amount,
                    donation.currency,
                    donation.donation_date
                )
        except Exception:
            pass
        return total
    
    # ============================================================================
    # PROGRESS AND GOAL CALCULATIONS
    # ============================================================================
    
    @property
    def progress_percentage(self):
        """Progress towards target goal"""
        if self.target_amount and self.target_amount > 0:
            return min((self.current_amount / self.target_amount) * 100, 100)
        return 0
    
    @property
    def minimum_goal_percentage(self):
        """Progress towards minimum goal"""
        if self.minimum_goal and self.minimum_goal > 0:
            return min((self.current_amount / self.minimum_goal) * 100, 100)
        return 0
    
    @property
    def amount_remaining(self):
        """Amount remaining to reach target"""
        remaining = (self.target_amount or Decimal('0.00')) - self.current_amount
        return max(remaining, Decimal('0.00'))
    
    @property
    def amount_over_target(self):
        """Amount raised over target (if any)"""
        over = self.current_amount - (self.target_amount or Decimal('0.00'))
        return max(over, Decimal('0.00'))
    
    @property
    def is_target_reached(self):
        """Check if target goal is reached"""
        return self.current_amount >= (self.target_amount or Decimal('0.00'))
    
    @property
    def is_minimum_reached(self):
        """Check if minimum goal is reached"""
        if not self.minimum_goal:
            return True
        return self.current_amount >= self.minimum_goal
    
    # ============================================================================
    # DONATION STATISTICS
    # ============================================================================
    
    @property
    def total_donors_count(self):
        """Total unique donors across all donation types"""
        donor_ids = set()
        
        # One-time donations
        for donation in self.donations.filter(status='completed'):
            if donation.donor_id:
                donor_ids.add(donation.donor_id)
        
        # Recurring donations
        for recurring in self.recurring_donations.filter(status__in=['active', 'completed']):
            if recurring.donor_id:
                donor_ids.add(recurring.donor_id)
        
        # In-kind donations
        for in_kind in self.in_kind_donations.filter(status='received'):
            if in_kind.donor_id:
                donor_ids.add(in_kind.donor_id)
        
        return len(donor_ids)
    
    @property
    def total_donations_count(self):
        """Total number of completed donations"""
        return (self.donations.filter(status='completed').count() +
                self.recurring_donations.filter(status__in=['active', 'completed']).count() +
                self.in_kind_donations.filter(status='received').count())
    
    @property
    def average_donation_amount(self):
        """Average donation amount in target currency"""
        count = self.donations.filter(status='completed').count()
        if count > 0:
            return self.total_donations_amount / count
        return Decimal('0.00')
    
    @property
    def largest_donation_amount(self):
        """Largest single donation in target currency"""
        largest = Decimal('0.00')
        try:
            for donation in self.donations.filter(status='completed'):
                converted = self._convert_to_target_currency(
                    donation.amount,
                    donation.currency,
                    donation.donation_date
                )
                if converted > largest:
                    largest = converted
        except Exception:
            pass
        return largest
    
    # ============================================================================
    # TIME-BASED CALCULATIONS
    # ============================================================================
    
    @property
    def days_remaining(self):
        """Days remaining in campaign"""
        if self.end_date:
            today = timezone.now().date()
            if today <= self.end_date:
                return (self.end_date - today).days
        return 0
    
    @property
    def days_elapsed(self):
        """Days since campaign started"""
        if self.start_date:
            today = timezone.now().date()
            if today >= self.start_date:
                return (today - self.start_date).days
        return 0
    
    @property
    def total_campaign_days(self):
        """Total days in campaign period"""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days
        return 0
    
    @property
    def time_progress_percentage(self):
        """Time progress percentage"""
        total_days = self.total_campaign_days
        if total_days > 0:
            elapsed_days = self.days_elapsed
            return min(max((elapsed_days / total_days) * 100, 0), 100)
        return 0
    
    @property
    def daily_fundraising_rate(self):
        """Average daily fundraising rate"""
        days_elapsed = self.days_elapsed
        if days_elapsed > 0:
            return self.current_amount / days_elapsed
        return Decimal('0.00')
    
    @property
    def projected_final_amount(self):
        """Projected final amount based on current rate"""
        rate = self.daily_fundraising_rate
        total_days = self.total_campaign_days
        if rate > 0 and total_days > 0:
            return rate * total_days
        return self.current_amount
    
    # ============================================================================
    # STATUS AND HEALTH CHECKS
    # ============================================================================
    
    @property
    def campaign_status(self):
        """Enhanced campaign status"""
        today = timezone.now().date()
        
        if self.status == 'cancelled':
            return 'CANCELLED'
        elif self.status == 'completed':
            return 'COMPLETED'
        elif self.status == 'paused':
            return 'PAUSED'
        elif today < self.start_date:
            return 'UPCOMING'
        elif today > self.end_date:
            if self.is_target_reached:
                return 'SUCCESSFUL'
            elif self.is_minimum_reached:
                return 'PARTIALLY_SUCCESSFUL'
            else:
                return 'UNSUCCESSFUL'
        elif self.status == 'active':
            return 'ACTIVE'
        else:
            return 'DRAFT'
    
    @property
    def fundraising_health(self):
        """Campaign fundraising health assessment"""
        if self.time_progress_percentage == 0:
            return 'NOT_STARTED'
        
        progress_ratio = self.progress_percentage / max(self.time_progress_percentage, 1)
        
        if progress_ratio >= 1.5:
            return 'EXCELLENT'
        elif progress_ratio >= 1.2:
            return 'VERY_GOOD'
        elif progress_ratio >= 1.0:
            return 'ON_TRACK'
        elif progress_ratio >= 0.8:
            return 'SLIGHTLY_BEHIND'
        elif progress_ratio >= 0.6:
            return 'BEHIND'
        else:
            return 'SIGNIFICANTLY_BEHIND'
    
    @property
    def is_active_period(self):
        """Check if campaign is in active period"""
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date
    
    @property
    def is_expired(self):
        """Check if campaign has expired"""
        return timezone.now().date() > self.end_date
    
    @property
    def can_receive_donations(self):
        """Check if campaign can receive donations"""
        return (self.status == 'active' and 
                self.is_active_period and 
                not self.is_expired)
    
    # ============================================================================
    # FORMATTING PROPERTIES
    # ============================================================================
    
    @property
    def formatted_target_amount(self):
        """Formatted target amount with currency"""
        return f"{self.target_currency.code} {self.target_amount:,.2f}"
    
    @property
    def formatted_current_amount(self):
        """Formatted current amount with currency"""
        return f"{self.target_currency.code} {self.current_amount:,.2f}"
    
    @property
    def formatted_amount_remaining(self):
        """Formatted remaining amount with currency"""
        return f"{self.target_currency.code} {self.amount_remaining:,.2f}"
    
    @property
    def formatted_minimum_goal(self):
        """Formatted minimum goal with currency"""
        if self.minimum_goal:
            return f"{self.target_currency.code} {self.minimum_goal:,.2f}"
        return None
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    def _convert_to_target_currency(self, amount, from_currency, conversion_date):
        """Convert amount to target currency"""
        if not amount or not from_currency:
            return Decimal('0.00')
            
        if from_currency == self.target_currency:
            return amount
        
        try:
            # Import here to avoid circular imports
            
            exchange_rate = ExchangeRate.objects.filter(
                from_currency=from_currency,
                to_currency=self.target_currency,
                effective_date__lte=conversion_date
            ).order_by('-effective_date').first()
            
            if exchange_rate:
                return amount * exchange_rate.rate
        except Exception:
            pass
        
        return amount
    
    def update_monetary_fields(self):
        """Method to recalculate all monetary properties - useful for data migrations"""
        # This method can be called to refresh calculated values
        # Useful when exchange rates change or when migrating data
        pass
    
    def get_donation_breakdown(self):
        """Get detailed breakdown of donations by type"""
        return {
            'one_time_donations': {
                'amount': self.total_donations_amount,
                'count': self.donations.filter(status='completed').count(),
                'formatted_amount': f"{self.target_currency.code} {self.total_donations_amount:,.2f}"
            },
            'recurring_donations': {
                'amount': self.total_recurring_amount,
                'count': self.recurring_donations.filter(status__in=['active', 'completed']).count(),
                'formatted_amount': f"{self.target_currency.code} {self.total_recurring_amount:,.2f}"
            },
            'in_kind_donations': {
                'amount': self.total_in_kind_amount,
                'count': self.in_kind_donations.filter(status='received').count(),
                'formatted_amount': f"{self.target_currency.code} {self.total_in_kind_amount:,.2f}"
            },
            'total': {
                'amount': self.current_amount,
                'count': self.total_donations_count,
                'formatted_amount': self.formatted_current_amount
            }
        }
    
    def get_performance_metrics(self):
        """Get comprehensive performance metrics"""
        return {
            'progress_percentage': round(self.progress_percentage, 2),
            'time_progress_percentage': round(self.time_progress_percentage, 2),
            'fundraising_health': self.fundraising_health,
            'daily_rate': float(self.daily_fundraising_rate),
            'projected_final': float(self.projected_final_amount),
            'average_donation': float(self.average_donation_amount),
            'largest_donation': float(self.largest_donation_amount),
            'total_donors': self.total_donors_count,
            'days_remaining': self.days_remaining,
            'is_target_reached': self.is_target_reached,
            'is_minimum_reached': self.is_minimum_reached
        }
    
    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.title} ({self.formatted_target_amount})"

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
            return self.allocations.aggregate(
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
    """Enhanced one-time donations with comprehensive tracking"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('cancelled', 'Cancelled'),
        ('disputed', 'Disputed'),
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
        ('wire_transfer', 'Wire Transfer'),
        ('other', 'Other'),
    ]
    
    DONATION_SOURCE_CHOICES = [
        ('website', 'Website'),
        ('mobile_app', 'Mobile App'),
        ('event', 'Fundraising Event'),
        ('mail', 'Direct Mail'),
        ('phone', 'Phone Campaign'),
        ('social_media', 'Social Media'),
        ('peer_to_peer', 'Peer-to-Peer'),
        ('corporate', 'Corporate Partnership'),
        ('grant', 'Grant/Foundation'),
        ('other', 'Other'),
    ]
    
    # Donor Information
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
    donor_phone = models.CharField(max_length=20, blank=True, null=True)
    
    # Donation Targets
    campaign = models.ForeignKey(
        'DonationCampaign', 
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
    
    # Financial Details
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
        blank=False

    )
    
    # Exchange Rate Information
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
    
    # Payment Processing
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
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
    
    # Transaction Details
    transaction_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    reference_number = models.CharField(max_length=100, blank=True, null=True)
    bank_reference = models.CharField(max_length=100, blank=True, null=True)
    
    # Dates and Status
    donation_date = models.DateTimeField(default=timezone.now)
    processed_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Source and Attribution
    donation_source = models.CharField(max_length=20, choices=DONATION_SOURCE_CHOICES, default='website')
    referral_source = models.CharField(max_length=200, blank=True, null=True)
    utm_source = models.CharField(max_length=100, blank=True, null=True)
    utm_medium = models.CharField(max_length=100, blank=True, null=True)
    utm_campaign = models.CharField(max_length=100, blank=True, null=True)
    
    # Donor Preferences
    is_recurring_eligible = models.BooleanField(default=True)
    marketing_opt_in = models.BooleanField(default=False)
    newsletter_opt_in = models.BooleanField(default=False)
    
    # Receipt and Tax
    receipt_sent = models.BooleanField(default=False)
    receipt_number = models.CharField(max_length=100, blank=True, null=True, unique=True)
    receipt_sent_date = models.DateTimeField(null=True, blank=True)
    tax_deductible = models.BooleanField(default=True)
    receipt_image = models.ImageField(
        upload_to='donation_receipts/',
        blank=True,
        null=True,
        help_text="Upload receipt or proof of donation"
    )
    
    # Administrative
    notes = models.TextField(blank=True, null=True)
    internal_notes = models.TextField(blank=True, null=True)
    processed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='processed_donations'
    )
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-donation_date']
        indexes = [
            models.Index(fields=['status', 'donation_date']),
            models.Index(fields=['donor', 'status']),
            models.Index(fields=['campaign', 'status']),
            models.Index(fields=['currency', 'donation_date']),
            models.Index(fields=['payment_method', 'status']),
            models.Index(fields=['donation_source', 'donation_date']),
        ]
        verbose_name = "Donation"
        verbose_name_plural = "Donations"
    
    # ============================================================================
    # FINANCIAL CALCULATIONS
    # ============================================================================
    
    @property
    def net_amount(self):
        """Amount after processor fees in original currency"""
        amount = self.amount or Decimal('0.00')
        
        # Convert processor fee to donation currency if different
        fee = self.processor_fee or Decimal('0.00')
        if (self.processor_fee_currency and 
            self.processor_fee_currency != self.currency and 
            fee > 0):
            fee = self._convert_currency(
                fee, 
                self.processor_fee_currency, 
                self.currency, 
                self.donation_date
            )
        
        return amount - fee
    
    @property
    def effective_amount(self):
        """Amount that actually benefits the organization"""
        return self.net_amount
    
    @property
    def processor_fee_percentage(self):
        """Processor fee as percentage of donation"""
        if self.amount and self.amount > 0:
            fee = self.processor_fee or Decimal('0.00')
            return float((fee / self.amount) * 100)
        return 0
    
    @property
    def net_percentage(self):
        """Net amount as percentage of gross donation"""
        if self.amount and self.amount > 0:
            return float((self.net_amount / self.amount) * 100)
        return 0
    
    # ============================================================================
    # CURRENCY CONVERSION METHODS
    # ============================================================================
    
    def get_amount_in_currency(self, target_currency):
        """Convert donation amount to specified currency"""
        if not target_currency or not self.currency:
            return self.amount or Decimal('0.00')
            
        if self.currency == target_currency:
            return self.amount or Decimal('0.00')
        
        return self._convert_currency(
            self.amount,
            self.currency,
            target_currency,
            self.donation_date
        )
    
    def get_net_amount_in_currency(self, target_currency):
        """Get net amount in specified currency"""
        if not target_currency or not self.currency:
            return self.net_amount
            
        if self.currency == target_currency:
            return self.net_amount
        
        return self._convert_currency(
            self.net_amount,
            self.currency,
            target_currency,
            self.donation_date
        )
    
    def _convert_currency(self, amount, from_currency, to_currency, conversion_date):
        """Helper method for currency conversion"""
        if not amount or not from_currency or not to_currency:
            return Decimal('0.00')
            
        if from_currency == to_currency:
            return amount
        
        try:
            # Import here to avoid circular imports
            
            exchange_rate = ExchangeRate.objects.filter(
                from_currency=from_currency,
                to_currency=to_currency,
                effective_date__lte=conversion_date
            ).order_by('-effective_date').first()
            
            if exchange_rate:
                return amount * exchange_rate.rate
        except Exception:
            pass
        
        return amount
    
    # ============================================================================
    # STATUS AND VALIDATION PROPERTIES
    # ============================================================================
    
    @property
    def is_completed(self):
        """Check if donation is completed"""
        return self.status == 'completed'
    
    @property
    def is_refundable(self):
        """Check if donation can be refunded"""
        return (self.status == 'completed' and 
                self.payment_method in ['credit_card', 'debit_card', 'paypal', 'stripe'])
    
    @property
    def is_tax_receipt_eligible(self):
        """Check if eligible for tax receipt"""
        return (self.tax_deductible and 
                self.status == 'completed' and 
                not self.is_anonymous)
    
    @property
    def requires_receipt(self):
        """Check if receipt is required but not sent"""
        return (self.is_tax_receipt_eligible and 
                not self.receipt_sent and 
                self.status == 'completed')
    
    @property
    def days_since_donation(self):
        """Days since donation was made"""
        if self.donation_date:
            return (timezone.now() - self.donation_date).days
        return 0
    
    @property
    def is_recent(self):
        """Check if donation was made recently (within 7 days)"""
        return self.days_since_donation <= 7
    
    # ============================================================================
    # DONOR INFORMATION PROPERTIES
    # ============================================================================
    
    @property
    def donor_name_display(self):
        """Display name for donor"""
        if self.is_anonymous:
            return "Anonymous"
        if self.donor:
            return self.donor.get_full_name() or self.donor.username
        return self.donor_name or "Unknown"
    
    @property
    def donor_email_display(self):
        """Display email for donor"""
        if self.is_anonymous:
            return None
        if self.donor:
            return self.donor.email
        return self.donor_email
    
    @property
    def has_complete_donor_info(self):
        """Check if donor information is complete"""
        if self.is_anonymous:
            return True
        return bool(self.donor_name_display and self.donor_email_display)
    
    # ============================================================================
    # FORMATTING PROPERTIES
    # ============================================================================
    
    @property
    def formatted_amount(self):
        """Formatted amount with currency"""
        return f"{self.currency.code} {self.amount:,.2f}"
    
    @property
    def formatted_net_amount(self):
        """Formatted net amount with currency"""
        return f"{self.currency.code} {self.net_amount:,.2f}"
    
    @property
    def formatted_processor_fee(self):
        """Formatted processor fee with currency"""
        if self.processor_fee and self.processor_fee > 0:
            currency = self.processor_fee_currency or self.currency
            return f"{currency.code} {self.processor_fee:,.2f}"
        return None
    
    @property
    def formatted_converted_amount(self):
        """Formatted converted amount if applicable"""
        if self.converted_amount and self.converted_currency:
            return f"{self.converted_currency.code} {self.converted_amount:,.2f}"
        return None
    
    # ============================================================================
    # BUSINESS LOGIC METHODS
    # ============================================================================
    
    def update_monetary_calculations(self):
        """Recalculate all monetary fields - useful for data migrations"""
        # This method can be called to refresh calculated values
        # Useful when exchange rates change or when migrating data
        if self.currency and self.campaign and self.campaign.target_currency:
            if self.currency != self.campaign.target_currency:
                self.converted_amount = self.get_amount_in_currency(
                    self.campaign.target_currency
                )
                self.converted_currency = self.campaign.target_currency
    
    def generate_receipt_number(self):
        """Generate unique receipt number"""
        if not self.receipt_number and self.is_tax_receipt_eligible:
            import uuid
            year = self.donation_date.year
            self.receipt_number = f"RCP-{year}-{str(uuid.uuid4())[:8].upper()}"
    
    def mark_receipt_sent(self):
        """Mark receipt as sent"""
        self.receipt_sent = True
        self.receipt_sent_date = timezone.now()
        self.save(update_fields=['receipt_sent', 'receipt_sent_date'])
    
    def get_attribution_data(self):
        """Get attribution and tracking data"""
        return {
            'donation_source': self.get_donation_source_display(),
            'referral_source': self.referral_source,
            'utm_source': self.utm_source,
            'utm_medium': self.utm_medium,
            'utm_campaign': self.utm_campaign,
            'payment_method': self.get_payment_method_display()
        }
    
    def get_financial_summary(self):
        """Get comprehensive financial summary"""
        return {
            'gross_amount': float(self.amount),
            'processor_fee': float(self.processor_fee or 0),
            'net_amount': float(self.net_amount),
            'processor_fee_percentage': self.processor_fee_percentage,
            'net_percentage': self.net_percentage,
            'currency': self.currency.code,
            'converted_amount': float(self.converted_amount) if self.converted_amount else None,
            'converted_currency': self.converted_currency.code if self.converted_currency else None,
            'exchange_rate': float(self.exchange_rate) if self.exchange_rate else None
        }
    
    def save(self, *args, **kwargs):
        # Generate receipt number if eligible
        if (self.status == 'completed' and 
            self.is_tax_receipt_eligible and 
            not self.receipt_number):
            self.generate_receipt_number()
        
        # Set processed date when status changes to completed
        if self.status == 'completed' and not self.processed_date:
            self.processed_date = timezone.now()
        
        # Clean transaction_id
        if self.transaction_id == '':
            self.transaction_id = None
            
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.donor_name_display} - {self.formatted_amount} ({self.get_status_display()})"


class RecurringDonation(models.Model):
    """Enhanced recurring donation subscriptions"""
    
    FREQUENCY_CHOICES = [
        ('weekly', 'Weekly'),
        ('biweekly', 'Bi-weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('biannually', 'Bi-annually'),
        ('annually', 'Annually'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
        ('failed', 'Failed'),
        ('completed', 'Completed'),
    ]
    
    # Donor Information
    donor = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='recurring_donations'
    )
    is_anonymous = models.BooleanField(default=False)
    
    # Donation Targets
    campaign = models.ForeignKey(
        'DonationCampaign', 
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
    
    # Financial Details
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
        blank=False
    )
    
    # Subscription Details
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    next_payment_date = models.DateField(null=True, blank=True)
    last_payment_date = models.DateField(blank=True, null=True)
    
    # Payment Information
    payment_method = models.CharField(max_length=100)
    subscription_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    payment_processor = models.CharField(max_length=50, blank=True, null=True)
    
    # Status and Tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    payment_count = models.PositiveIntegerField(default=0)
    failed_payment_count = models.PositiveIntegerField(default=0)
    max_failed_payments = models.PositiveIntegerField(default=3)
    
    # Administrative
    notes = models.TextField(blank=True, null=True)
    receipt_image = models.ImageField(
        upload_to='recurring_donation_receipts/',
        blank=True,
        null=True,
        help_text="Upload receipt or proof of recurring donation setup"
    )
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'next_payment_date']),
            models.Index(fields=['donor', 'status']),
            models.Index(fields=['currency', 'status']),
            models.Index(fields=['frequency', 'status']),
        ]
        verbose_name = "Recurring Donation"
        verbose_name_plural = "Recurring Donations"
    
    # ============================================================================
    # FINANCIAL CALCULATIONS
    # ============================================================================
    
    @property
    def total_donated(self):
        """Total amount donated through this recurring subscription"""
        return self.related_donations.filter(status='completed').aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
    
    @property
    def total_net_donated(self):
        """Total net amount (after fees) donated"""
        total = Decimal('0.00')
        for donation in self.related_donations.filter(status='completed'):
            total += donation.net_amount
        return total
    
    @property
    def average_donation_amount(self):
        """Average amount per successful donation"""
        if self.payment_count > 0:
            return self.total_donated / self.payment_count
        return Decimal('0.00')
    
    @property
    def projected_annual_amount(self):
        """Projected annual donation amount"""
        frequency_multipliers = {
            'weekly': 52,
            'biweekly': 26,
            'monthly': 12,
            'quarterly': 4,
            'biannually': 2,
            'annually': 1,
        }
        multiplier = frequency_multipliers.get(self.frequency, 12)
        return self.amount * multiplier
    
    @property
    def lifetime_value(self):
        """Estimated lifetime value of this recurring donation"""
        if self.end_date:
            # Calculate based on end date
            from dateutil.relativedelta import relativedelta
            
            frequency_deltas = {
                'weekly': relativedelta(weeks=1),
                'biweekly': relativedelta(weeks=2),
                'monthly': relativedelta(months=1),
                'quarterly': relativedelta(months=3),
                'biannually': relativedelta(months=6),
                'annually': relativedelta(years=1),
            }
            
            delta = frequency_deltas.get(self.frequency, relativedelta(months=1))
            current_date = self.start_date
            total_payments = 0
            
            while current_date <= self.end_date:
                total_payments += 1
                current_date += delta
            
            return self.amount * total_payments
        else:
            # Estimate based on average recurring donation lifespan (assume 2 years)
            return self.projected_annual_amount * 2
    
    # ============================================================================
    # STATUS AND HEALTH CALCULATIONS
    # ============================================================================
    
    @property
    def success_rate(self):
        """Success rate of payments"""
        total_attempts = self.payment_count + self.failed_payment_count
        if total_attempts > 0:
            return (self.payment_count / total_attempts) * 100
        return 0
    
    @property
    def is_healthy(self):
        """Check if recurring donation is healthy"""
        return (self.status == 'active' and 
                self.failed_payment_count < self.max_failed_payments and
                self.success_rate >= 80)
    
    @property
    def is_at_risk(self):
        """Check if recurring donation is at risk of cancellation"""
        return (self.status == 'active' and 
                (self.failed_payment_count >= (self.max_failed_payments - 1) or
                 self.success_rate < 50))
    
    @property
    def days_until_next_payment(self):
        """Days until next payment"""
        if self.next_payment_date and self.status == 'active':
            today = timezone.now().date()
            if self.next_payment_date >= today:
                return (self.next_payment_date - today).days
        return None
    
    @property
    def is_payment_due(self):
        """Check if payment is due"""
        if self.next_payment_date and self.status == 'active':
            return timezone.now().date() >= self.next_payment_date
        return False
    
    @property
    def is_overdue(self):
        """Check if payment is overdue"""
        if self.next_payment_date and self.status == 'active':
            return timezone.now().date() > self.next_payment_date
        return False
    
    @property
    def subscription_age_days(self):
        """Age of subscription in days"""
        return (timezone.now().date() - self.start_date).days
    
    @property
    def subscription_age_months(self):
        """Age of subscription in months"""
        return self.subscription_age_days / 30.44  # Average days per month
    
    # ============================================================================
    # CURRENCY CONVERSION METHODS
    # ============================================================================
    
    def get_amount_in_currency(self, target_currency):
        """Convert recurring amount to specified currency"""
        if not target_currency or not self.currency:
            return self.amount
            
        if self.currency == target_currency:
            return self.amount
        
        try:
            # Import here to avoid circular imports
            
            exchange_rate = ExchangeRate.objects.filter(
                from_currency=self.currency,
                to_currency=target_currency
            ).order_by('-effective_date').first()
            
            if exchange_rate:
                return self.amount * exchange_rate.rate
        except Exception:
            pass
        
        return self.amount
    
    def get_total_donated_in_currency(self, target_currency):
        """Get total donated amount in specified currency"""
        total = Decimal('0.00')
        for donation in self.related_donations.filter(status='completed'):
            total += donation.get_amount_in_currency(target_currency)
        return total
    
    # ============================================================================
    # FORMATTING PROPERTIES
    # ============================================================================
    
    @property
    def formatted_amount(self):
        """Formatted amount with currency"""
        return f"{self.currency.code} {self.amount:,.2f}"
    
    @property
    def formatted_total_donated(self):
        """Formatted total donated with currency"""
        return f"{self.currency.code} {self.total_donated:,.2f}"
    
    @property
    def formatted_projected_annual(self):
        """Formatted projected annual amount"""
        return f"{self.currency.code} {self.projected_annual_amount:,.2f}"
    
    @property
    def formatted_lifetime_value(self):
        """Formatted lifetime value"""
        return f"{self.currency.code} {self.lifetime_value:,.2f}"
    
    # ============================================================================
    # BUSINESS LOGIC METHODS
    # ============================================================================
    
    def calculate_next_payment_date(self):
        """Calculate next payment date based on frequency"""
        from dateutil.relativedelta import relativedelta
        
        frequency_deltas = {
            'weekly': relativedelta(weeks=1),
            'biweekly': relativedelta(weeks=2),
            'monthly': relativedelta(months=1),
            'quarterly': relativedelta(months=3),
            'biannually': relativedelta(months=6),
            'annually': relativedelta(years=1),
        }
        
        delta = frequency_deltas.get(self.frequency, relativedelta(months=1))
        
        if self.last_payment_date:
            next_date = self.last_payment_date + delta
        else:
            next_date = self.start_date + delta
        
        # Don't schedule beyond end date
        if self.end_date and next_date > self.end_date:
            return None
            
        return next_date
    
    def record_successful_payment(self, donation):
        """Record a successful payment"""
        self.payment_count += 1
        self.last_payment_date = donation.donation_date.date()
        self.next_payment_date = self.calculate_next_payment_date()
        self.failed_payment_count = 0  # Reset failed count on success
        
        # Check if subscription should be completed
        if self.end_date and self.next_payment_date and self.next_payment_date > self.end_date:
            self.status = 'completed'
            self.next_payment_date = None
        
        self.save()
    
    def record_failed_payment(self):
        """Record a failed payment"""
        self.failed_payment_count += 1
        
        # Cancel if too many failures
        if self.failed_payment_count >= self.max_failed_payments:
            self.status = 'failed'
            self.next_payment_date = None
        else:
            # Retry in a few days
            from datetime import timedelta
            self.next_payment_date = timezone.now().date() + timedelta(days=3)
        
        self.save()
    
    def pause_subscription(self, reason=None):
        """Pause the subscription"""
        self.status = 'paused'
        if reason:
            self.notes = f"{self.notes or ''}\nPaused: {reason}".strip()
        self.save()
    
    def resume_subscription(self):
        """Resume a paused subscription"""
        if self.status == 'paused':
            self.status = 'active'
            # Recalculate next payment date
            self.next_payment_date = self.calculate_next_payment_date()
            self.save()
    
    def cancel_subscription(self, reason=None):
        """Cancel the subscription"""
        self.status = 'cancelled'
        self.next_payment_date = None
        if reason:
            self.notes = f"{self.notes or ''}\nCancelled: {reason}".strip()
        self.save()
    
    def update_monetary_calculations(self):
        """Recalculate monetary fields - useful for data migrations"""
        # This method can be called to refresh calculated values
        pass
    
    def get_performance_summary(self):
        """Get comprehensive performance summary"""
        return {
            'total_donated': float(self.total_donated),
            'payment_count': self.payment_count,
            'failed_payment_count': self.failed_payment_count,
            'success_rate': round(self.success_rate, 2),
            'average_donation': float(self.average_donation_amount),
            'projected_annual': float(self.projected_annual_amount),
            'lifetime_value': float(self.lifetime_value),
            'subscription_age_months': round(self.subscription_age_months, 1),
            'is_healthy': self.is_healthy,
            'is_at_risk': self.is_at_risk,
            'days_until_next_payment': self.days_until_next_payment,
            'currency': self.currency.code
        }
    
    def __str__(self):
        donor_name = self.donor.get_full_name() or self.donor.username
        return f"{donor_name} - {self.formatted_amount} {self.frequency} ({self.get_status_display()})"


class InKindDonation(models.Model):
    """Enhanced non-monetary donations with comprehensive valuation"""
    
    STATUS_CHOICES = [
        ('pledged', 'Pledged'),
        ('confirmed', 'Confirmed'),
        ('received', 'Received'),
        ('declined', 'Declined'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]
    
    CATEGORY_CHOICES = [
        ('equipment', 'Equipment'),
        ('supplies', 'Supplies'),
        ('services', 'Professional Services'),
        ('food', 'Food & Beverages'),
        ('clothing', 'Clothing'),
        ('books', 'Books & Educational Materials'),
        ('technology', 'Technology'),
        ('vehicles', 'Vehicles'),
        ('real_estate', 'Real Estate'),
        ('artwork', 'Artwork'),
        ('other', 'Other'),
    ]
    
    # Donor Information
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
    donor_phone = models.CharField(max_length=20, blank=True, null=True)
    donor_organization = models.CharField(max_length=200, blank=True, null=True)
    
    # Donation Targets
    campaign = models.ForeignKey(
        'DonationCampaign', 
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
    
    # Item Details
    item_description = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    brand_model = models.CharField(max_length=200, blank=True, null=True)
    condition = models.CharField(max_length=100, blank=True, null=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_of_measure = models.CharField(max_length=50, blank=True, null=True)
    
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
        blank=False
    )
    valuation_method = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="How the value was determined"
    )
    market_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Current market value if different from estimated"
    )
    
    # Dates and Status
    pledge_date = models.DateField(default=timezone.now)
    expected_delivery_date = models.DateField(null=True, blank=True)
    received_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pledged')
    
    # Logistics
    pickup_required = models.BooleanField(default=False)
    delivery_address = models.TextField(blank=True, null=True)
    special_handling_requirements = models.TextField(blank=True, null=True)
    storage_requirements = models.TextField(blank=True, null=True)
    
    # Processing
    received_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='received_in_kind_donations'
    )
    condition_on_receipt = models.TextField(blank=True, null=True)
    actual_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Actual value assessed upon receipt"
    )
    
    # Tax and Receipt
    receipt_sent = models.BooleanField(default=False)
    receipt_number = models.CharField(max_length=100, blank=True, null=True, unique=True)
    receipt_sent_date = models.DateTimeField(null=True, blank=True)
    tax_deductible = models.BooleanField(default=True)
    receipt_image = models.ImageField(
        upload_to='in_kind_donation_receipts/', 
        blank=True, 
        null=True,
        help_text="Upload receipt or photo of in-kind donation"
    )
    
    # Documentation
    photos = models.FileField(
        upload_to='in_kind_donation_photos/',
        blank=True,
        null=True,
        help_text="Photos of the donated items"
    )
    documentation = models.FileField(
        upload_to='in_kind_donation_docs/',
        blank=True,
        null=True,
        help_text="Additional documentation (certificates, warranties, etc.)"
    )
    donation_date = models.DateTimeField(default=timezone.now)
    
    # Administrative
    notes = models.TextField(blank=True, null=True)
    internal_notes = models.TextField(blank=True, null=True)
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-pledge_date']
        indexes = [
            models.Index(fields=['status', 'pledge_date']),
            models.Index(fields=['donor', 'status']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['valuation_currency']),
        ]
        verbose_name = "In-Kind Donation"
        verbose_name_plural = "In-Kind Donations"
    
    # ============================================================================
    # VALUATION CALCULATIONS
    # ============================================================================
    @property
    def formatted_value(self):
        """Legacy property for admin compatibility"""
        return self.formatted_estimated_value
    
    @property
    def total_estimated_value(self):
        """Total estimated value (quantity × unit value)"""
        return (self.estimated_value or Decimal('0.00')) * self.quantity
    
    @property
    def total_actual_value(self):
        """Total actual value if assessed"""
        if self.actual_value:
            return self.actual_value * self.quantity
        return self.total_estimated_value
    
    @property
    def total_market_value(self):
        """Total market value if provided"""
        if self.market_value:
            return self.market_value * self.quantity
        return self.total_estimated_value
    
    @property
    def value_variance(self):
        """Difference between estimated and actual value"""
        if self.actual_value:
            return self.total_actual_value - self.total_estimated_value
        return Decimal('0.00')
    
    @property
    def value_variance_percentage(self):
        """Value variance as percentage"""
        if self.total_estimated_value > 0 and self.actual_value:
            return float((self.value_variance / self.total_estimated_value) * 100)
        return 0
    
    @property
    def effective_value(self):
        """The value that should be used for reporting"""
        if self.status == 'received' and self.actual_value:
            return self.total_actual_value
        return self.total_estimated_value
    
    # ============================================================================
    # CURRENCY CONVERSION METHODS
    # ============================================================================
    
    def get_value_in_currency(self, target_currency, use_actual_value=False):
        """Convert donation value to specified currency"""
        if not target_currency or not self.valuation_currency:
            return self.effective_value
            
        if self.valuation_currency == target_currency:
            return self.effective_value
        
        value_to_convert = self.total_actual_value if use_actual_value and self.actual_value else self.total_estimated_value
        
        try:
            # Import here to avoid circular imports
            
            conversion_date = self.received_date or self.pledge_date
            exchange_rate = ExchangeRate.objects.filter(
                from_currency=self.valuation_currency,
                to_currency=target_currency,
                effective_date__lte=conversion_date
            ).order_by('-effective_date').first()
            
            if exchange_rate:
                return value_to_convert * exchange_rate.rate
        except Exception:
            pass
        
        return value_to_convert
    
    # ============================================================================
    # STATUS AND VALIDATION PROPERTIES
    # ============================================================================
    
    @property
    def is_received(self):
        """Check if donation has been received"""
        return self.status == 'received'
    
    @property
    def is_pending_receipt(self):
        """Check if donation is confirmed but not yet received"""
        return self.status in ['pledged', 'confirmed']
    
    @property
    def is_overdue(self):
        """Check if expected delivery date has passed"""
        if self.expected_delivery_date and self.status in ['pledged', 'confirmed']:
            return timezone.now().date() > self.expected_delivery_date
        return False
    
    @property
    def days_since_pledge(self):
        """Days since pledge was made"""
        if self.pledge_date:
            return (timezone.now().date() - self.pledge_date).days
        return 0
    
    @property
    def days_until_expected_delivery(self):
        """Days until expected delivery"""
        if self.expected_delivery_date and self.status in ['pledged', 'confirmed']:
            today = timezone.now().date()
            if self.expected_delivery_date >= today:
                return (self.expected_delivery_date - today).days
        return None
    
    @property
    def processing_time_days(self):
        """Days from pledge to receipt"""
        if self.received_date and self.pledge_date:
            return (self.received_date - self.pledge_date).days
        return None
    
    @property
    def is_tax_receipt_eligible(self):
        """Check if eligible for tax receipt"""
        return (self.tax_deductible and 
                self.status == 'received' and 
                not self.is_anonymous)
    
    @property
    def requires_receipt(self):
        """Check if receipt is required but not sent"""
        return (self.is_tax_receipt_eligible and 
                not self.receipt_sent)
    
    # ============================================================================
    # DONOR INFORMATION PROPERTIES
    # ============================================================================
    
    @property
    def donor_name_display(self):
        """Display name for donor"""
        if self.is_anonymous:
            return "Anonymous"
        if self.donor:
            return self.donor.get_full_name() or self.donor.username
        return self.donor_name or "Unknown"
    
    @property
    def donor_contact_display(self):
        """Display contact for donor"""
        if self.is_anonymous:
            return None
        if self.donor:
            return self.donor.email
        return self.donor_email
    
    @property
    def has_complete_donor_info(self):
        """Check if donor information is complete"""
        if self.is_anonymous:
            return True
        return bool(self.donor_name_display and self.donor_contact_display)
    
    # ============================================================================
    # FORMATTING PROPERTIES
    # ============================================================================
    
    @property
    def formatted_estimated_value(self):
        """Formatted estimated value with currency"""
        return f"{self.valuation_currency.code} {self.total_estimated_value:,.2f}"
    
    @property
    def formatted_actual_value(self):
        """Formatted actual value with currency"""
        if self.actual_value:
            return f"{self.valuation_currency.code} {self.total_actual_value:,.2f}"
        return None
    
    @property
    def formatted_effective_value(self):
        """Formatted effective value with currency"""
        return f"{self.valuation_currency.code} {self.effective_value:,.2f}"
    
    @property
    def formatted_market_value(self):
        """Formatted market value with currency"""
        if self.market_value:
            return f"{self.valuation_currency.code} {self.total_market_value:,.2f}"
        return None
    
    @property
    def formatted_value_variance(self):
        """Formatted value variance with currency and sign"""
        if self.actual_value:
            variance = self.value_variance
            sign = "+" if variance >= 0 else ""
            return f"{sign}{self.valuation_currency.code} {variance:,.2f}"
        return None
    
    @property
    def item_summary(self):
        """Summary description of the item"""
        summary = f"{self.quantity} × {self.item_description}"
        if self.brand_model:
            summary += f" ({self.brand_model})"
        if self.condition:
            summary += f" - {self.condition}"
        return summary
    
    # ============================================================================
    # BUSINESS LOGIC METHODS
    # ============================================================================
    
    def update_monetary_calculations(self):
        """Recalculate all monetary fields - useful for data migrations"""
        # This method can be called to refresh calculated values
        # Useful when exchange rates change or when migrating data
        pass
    
    def generate_receipt_number(self):
        """Generate unique receipt number"""
        if not self.receipt_number and self.is_tax_receipt_eligible:
            import uuid
            year = self.pledge_date.year
            self.receipt_number = f"IKD-{year}-{str(uuid.uuid4())[:8].upper()}"
    
    def mark_as_received(self, received_by_user, condition_notes=None, actual_value=None):
        """Mark donation as received"""
        self.status = 'received'
        self.received_date = timezone.now().date()
        self.received_by = received_by_user
        if condition_notes:
            self.condition_on_receipt = condition_notes
        if actual_value:
            self.actual_value = actual_value
        self.save()
    
    def mark_receipt_sent(self):
        """Mark receipt as sent"""
        self.receipt_sent = True
        self.receipt_sent_date = timezone.now()
        self.save(update_fields=['receipt_sent', 'receipt_sent_date'])
    
    def get_logistics_summary(self):
        """Get logistics and handling summary"""
        return {
            'pickup_required': self.pickup_required,
            'delivery_address': self.delivery_address,
            'special_handling': bool(self.special_handling_requirements),
            'storage_requirements': bool(self.storage_requirements),
            'expected_delivery_date': self.expected_delivery_date.isoformat() if self.expected_delivery_date else None,
            'days_until_delivery': self.days_until_expected_delivery,
            'is_overdue': self.is_overdue
        }
    
    def get_valuation_summary(self):
        """Get comprehensive valuation summary"""
        return {
            'estimated_value': float(self.total_estimated_value),
            'actual_value': float(self.total_actual_value) if self.actual_value else None,
            'market_value': float(self.total_market_value) if self.market_value else None,
            'effective_value': float(self.effective_value),
            'value_variance': float(self.value_variance) if self.actual_value else None,
            'value_variance_percentage': self.value_variance_percentage if self.actual_value else None,
            'valuation_method': self.valuation_method,
            'currency': self.valuation_currency.code,
            'quantity': self.quantity,
            'unit_value': float(self.estimated_value)
        }
    
    def save(self, *args, **kwargs):
        # Generate receipt number if eligible
        if (self.status == 'received' and 
            self.is_tax_receipt_eligible and 
            not self.receipt_number):
            self.generate_receipt_number()
            
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.donor_name_display} - {self.item_summary} ({self.formatted_effective_value})"


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
    """Enhanced Budget model with comprehensive financial tracking"""
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

    # ============================================================================
    # CORE AMOUNT CALCULATIONS (from budget items)
    # ============================================================================
    
    @property
    def spent_amount(self):
        """Calculate total spent from all budget items (paid expenses only)"""
        try:
            total = Decimal('0.00')
            for item in self.items.all():
                total += item.spent_amount
            return total
        except Exception:
            return Decimal('0.00')
    
    @property
    def pending_amount(self):
        """Calculate total pending from all budget items"""
        try:
            total = Decimal('0.00')
            for item in self.items.all():
                total += item.pending_amount
            return total
        except Exception:
            return Decimal('0.00')
    
    @property
    def committed_amount(self):
        """Calculate total committed from all budget items (approved + paid)"""
        try:
            total = Decimal('0.00')
            for item in self.items.all():
                total += item.committed_amount
            return total
        except Exception:
            return Decimal('0.00')
    
    @property
    def approved_amount(self):
        """Calculate total approved but not paid from all budget items"""
        try:
            total = Decimal('0.00')
            for item in self.items.all():
                total += item.approved_amount
            return total
        except Exception:
            return Decimal('0.00')
    
    @property
    def rejected_amount(self):
        """Calculate total rejected from all budget items"""
        try:
            total = Decimal('0.00')
            for item in self.items.all():
                total += item.rejected_amount
            return total
        except Exception:
            return Decimal('0.00')
    
    @property
    def total_requested_amount(self):
        """Calculate total requested from all budget items"""
        try:
            total = Decimal('0.00')
            for item in self.items.all():
                total += item.total_requested_amount
            return total
        except Exception:
            return Decimal('0.00')

    # ============================================================================
    # BUDGET ALLOCATION CALCULATIONS
    # ============================================================================
    
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
    def unallocated_amount(self):
        """Amount not yet allocated to budget items"""
        total = self.total_amount or Decimal('0.00')
        allocated = self.allocated_amount
        return total - allocated
    
    @property
    def remaining_amount(self):
        """Amount remaining after actual spending (paid expenses only)"""
        total = self.total_amount or Decimal('0.00')
        spent = self.spent_amount
        return total - spent
    
    @property
    def available_amount(self):
        """Amount available considering committed expenses"""
        total = self.total_amount or Decimal('0.00')
        committed = self.committed_amount
        return total - committed
    
    @property
    def encumbered_amount(self):
        """Amount encumbered by pending and approved expenses"""
        return self.pending_amount + self.approved_amount
    
    @property
    def truly_available_amount(self):
        """Amount truly available after all commitments and pending requests"""
        total = self.total_amount or Decimal('0.00')
        total_obligations = self.committed_amount + self.pending_amount
        return total - total_obligations

    # ============================================================================
    # PERCENTAGE CALCULATIONS
    # ============================================================================
    
    @property
    def spent_percentage(self):
        """Percentage of budget actually spent (paid expenses only)"""
        total = self.total_amount or Decimal('0.00')
        if total > 0:
            spent = self.spent_amount
            return float((spent / total) * 100)
        return 0
    
    @property
    def committed_percentage(self):
        """Percentage of budget committed (approved + paid)"""
        total = self.total_amount or Decimal('0.00')
        if total > 0:
            committed = self.committed_amount
            return float((committed / total) * 100)
        return 0
    
    @property
    def utilization_percentage(self):
        """Total utilization including all pending requests"""
        total = self.total_amount or Decimal('0.00')
        if total > 0:
            total_obligations = self.committed_amount + self.pending_amount
            return float((total_obligations / total) * 100)
        return 0
    
    @property
    def allocation_percentage(self):
        """Percentage of total budget allocated to items"""
        total = self.total_amount or Decimal('0.00')
        if total > 0:
            allocated = self.allocated_amount
            return float((allocated / total) * 100)
        return 0

    # ============================================================================
    # VARIANCE CALCULATIONS
    # ============================================================================
    
    @property
    def variance(self):
        """Budget variance based on actual spending (positive = under budget)"""
        total = self.total_amount or Decimal('0.00')
        spent = self.spent_amount
        return total - spent
    
    @property
    def variance_percentage(self):
        """Variance as percentage of budget"""
        total = self.total_amount or Decimal('0.00')
        if total > 0:
            variance = self.variance
            return float((variance / total) * 100)
        return 0
    
    @property
    def committed_variance(self):
        """Variance considering committed expenses"""
        total = self.total_amount or Decimal('0.00')
        committed = self.committed_amount
        return total - committed
    
    @property
    def allocation_variance(self):
        """Variance in allocation vs total budget"""
        total = self.total_amount or Decimal('0.00')
        allocated = self.allocated_amount
        return total - allocated

    # ============================================================================
    # FUNDING CALCULATIONS
    # ============================================================================
    
    @property
    def total_funding_allocated(self):
        """Total funding allocated from all sources"""
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
    def funding_surplus(self):
        """Amount over-funded (if any)"""
        funded = self.total_funding_allocated
        total = self.total_amount or Decimal('0.00')
        surplus = funded - total
        return max(Decimal('0.00'), surplus)
    
    @property
    def funding_utilization_percentage(self):
        """Percentage of funding actually utilized"""
        funded = self.total_funding_allocated
        if funded > 0:
            spent = self.spent_amount
            return float((spent / funded) * 100)
        return 0

    # ============================================================================
    # ENHANCED FUNDING CALCULATIONS (Including Fund Allocations)
    # ============================================================================

    @property
    def total_fund_allocations(self):
        """Total amount actually allocated from bank accounts"""
        try:
            return self.fund_allocations.filter(is_active=True).aggregate(
                total=Sum('amount_allocated')
            )['total'] or Decimal('0.00')
        except Exception:
            return Decimal('0.00')

    @property
    def active_fund_allocations(self):
        """Total from active fund allocations only"""
        try:
            return self.fund_allocations.filter(
                is_active=True,
                allocation_date__lte=timezone.now()
            ).aggregate(
                total=Sum('amount_allocated')
            )['total'] or Decimal('0.00')
        except Exception:
            return Decimal('0.00')

    @property
    def funding_vs_allocation_gap(self):
        """Gap between planned funding and actual allocations"""
        planned_funding = self.total_funding_allocated
        actual_allocations = self.total_fund_allocations
        return planned_funding - actual_allocations

    @property
    def allocation_coverage_percentage(self):
        """Percentage of budget covered by actual allocations"""
        total = self.total_amount or Decimal('0.00')
        if total > 0:
            allocations = self.total_fund_allocations
            return float((allocations / total) * 100)
        return 0

    @property
    def funding_realization_percentage(self):
        """Percentage of planned funding that has been actually allocated"""
        planned = self.total_funding_allocated
        if planned > 0:
            actual = self.total_fund_allocations
            return float((actual / planned) * 100)
        return 0

    @property
    def allocation_utilization_percentage(self):
        """Percentage of allocated funds that have been spent"""
        allocated = self.total_fund_allocations
        if allocated > 0:
            spent = self.spent_amount
            return float((spent / allocated) * 100)
        return 0

    @property
    def allocation_gap(self):
        """Amount still needed from allocations to cover budget"""
        total = self.total_amount or Decimal('0.00')
        allocated = self.total_fund_allocations
        gap = total - allocated
        return max(Decimal('0.00'), gap)

    @property
    def allocation_surplus(self):
        """Amount over-allocated (if any)"""
        allocated = self.total_fund_allocations
        total = self.total_amount or Decimal('0.00')
        surplus = allocated - total
        return max(Decimal('0.00'), surplus)

    @property
    def is_fully_allocated_from_accounts(self):
        """Check if budget is fully covered by account allocations"""
        return self.total_fund_allocations >= (self.total_amount or Decimal('0.00'))

    @property
    def allocation_status(self):
        """Status based on actual fund allocations"""
        if self.allocation_gap > 0:
            gap_percentage = float((self.allocation_gap / self.total_amount) * 100)
            if gap_percentage > 50:
                return 'SEVERELY_UNDER_ALLOCATED'
            elif gap_percentage > 25:
                return 'UNDER_ALLOCATED'
            else:
                return 'PARTIALLY_ALLOCATED'
        elif self.allocation_surplus > 0:
            return 'OVER_ALLOCATED'
        else:
            return 'FULLY_ALLOCATED'

    @property
    def comprehensive_funding_status(self):
        """Enhanced funding status considering both sources and allocations"""
        funding_status = self.funding_status
        allocation_status = self.allocation_status
        
        if funding_status in ['SEVERELY_UNDERFUNDED', 'UNDERFUNDED'] and allocation_status in ['SEVERELY_UNDER_ALLOCATED', 'UNDER_ALLOCATED']:
            return 'CRITICALLY_UNDERFUNDED'
        elif funding_status == 'FULLY_FUNDED' and allocation_status == 'FULLY_ALLOCATED':
            return 'FULLY_FUNDED_AND_ALLOCATED'
        elif funding_status == 'FULLY_FUNDED' and allocation_status in ['UNDER_ALLOCATED', 'SEVERELY_UNDER_ALLOCATED']:
            return 'FUNDED_BUT_NOT_ALLOCATED'
        elif funding_status in ['UNDERFUNDED', 'PARTIALLY_FUNDED'] and allocation_status == 'FULLY_ALLOCATED':
            return 'ALLOCATED_BEYOND_FUNDING'
        else:
            return f"{funding_status}_{allocation_status}"

    @property
    def available_from_allocations(self):
        """Amount available for spending from actual allocations"""
        allocated = self.total_fund_allocations
        spent = self.spent_amount
        return allocated - spent

    @property
    def truly_available_from_allocations(self):
        """Amount truly available considering allocations and commitments"""
        allocated = self.total_fund_allocations
        total_obligations = self.committed_amount + self.pending_amount
        return allocated - total_obligations

    @property
    def formatted_total_fund_allocations(self):
        """Formatted total fund allocations with currency"""
        if self.currency:
            return f"{self.currency.code} {self.total_fund_allocations:,.2f}"
        return f"{self.total_fund_allocations:,.2f}"

    @property
    def formatted_allocation_gap(self):
        """Formatted allocation gap with currency"""
        if self.currency:
            return f"{self.currency.code} {self.allocation_gap:,.2f}"
        return f"{self.allocation_gap:,.2f}"

    @property
    def formatted_funding_vs_allocation_gap(self):
        """Formatted gap between funding and allocations with currency and sign"""
        gap = self.funding_vs_allocation_gap
        sign = "+" if gap >= 0 else ""
        if self.currency:
            return f"{sign}{self.currency.code} {gap:,.2f}"
        return f"{sign}{gap:,.2f}"

    # ============================================================================
    # STATUS AND HEALTH CALCULATIONS
    # ============================================================================
    
    @property
    def budget_health(self):
        """Overall budget health considering all factors"""
        utilization = self.utilization_percentage
        if utilization > 100:
            return 'OVERCOMMITTED'
        elif utilization > 95:
            return 'AT_RISK'
        elif utilization > 80:
            return 'CAUTION'
        elif utilization > 50:
            return 'HEALTHY'
        else:
            return 'UNDERUTILIZED'
    
    @property
    def utilization_status(self):
        """Budget utilization status based on committed percentage"""
        percentage = self.committed_percentage
        if percentage >= 100:
            return 'OVER_BUDGET'
        elif percentage >= 90:
            return 'CRITICAL'
        elif percentage >= 75:
            return 'WARNING'
        elif percentage >= 50:
            return 'MODERATE'
        else:
            return 'NORMAL'
    
    @property
    def funding_status(self):
        """Funding status assessment (legacy - use comprehensive_funding_status for enhanced view)"""
        if self.funding_gap > 0:
            gap_percentage = float((self.funding_gap / self.total_amount) * 100)
            if gap_percentage > 50:
                return 'SEVERELY_UNDERFUNDED'
            elif gap_percentage > 25:
                return 'UNDERFUNDED'
            else:
                return 'PARTIALLY_FUNDED'
        elif self.funding_surplus > 0:
            return 'OVERFUNDED'
        else:
            return 'FULLY_FUNDED'

    # ============================================================================
    # BOOLEAN STATUS CHECKS
    # ============================================================================
    
    @property
    def is_over_budget(self):
        """Check if actual spending exceeds budget"""
        return self.spent_amount > (self.total_amount or Decimal('0.00'))
    
    @property
    def is_overcommitted(self):
        """Check if committed expenses exceed budget"""
        return self.committed_amount > (self.total_amount or Decimal('0.00'))
    
    @property
    def is_fully_allocated(self):
        """Check if all budget is allocated to items"""
        return self.allocated_amount >= (self.total_amount or Decimal('0.00'))
    
    @property
    def is_fully_funded(self):
        """Check if budget is fully funded"""
        return self.total_funding_allocated >= (self.total_amount or Decimal('0.00'))
    
    @property
    def has_pending_requests(self):
        """Check if there are pending expense requests"""
        return self.pending_amount > Decimal('0.00')
    
    @property
    def is_expired(self):
        """Check if budget period has ended"""
        return timezone.now().date() > self.end_date
    
    @property
    def is_active_period(self):
        """Check if budget is in active period"""
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date
    
    @property
    def can_allocate_more(self):
        """Check if more budget can be allocated"""
        return self.unallocated_amount > 0 and not self.is_locked_for_allocation
    
    @property
    def is_locked_for_allocation(self):
        """Check if budget is locked for new allocations"""
        return self.status in ['completed', 'cancelled'] or self.is_expired

    # ============================================================================
    # TIME-BASED CALCULATIONS
    # ============================================================================
    
    @property
    def days_remaining(self):
        """Days remaining in budget period"""
        if self.end_date:
            today = timezone.now().date()
            if today <= self.end_date:
                return (self.end_date - today).days
        return 0
    
    @property
    def days_elapsed(self):
        """Days elapsed since budget start"""
        if self.start_date:
            today = timezone.now().date()
            if today >= self.start_date:
                return (today - self.start_date).days
        return 0
    
    @property
    def total_budget_days(self):
        """Total days in budget period"""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days
        return 0
    
    @property
    def progress_percentage(self):
        """Time progress percentage"""
        total_days = self.total_budget_days
        if total_days > 0:
            elapsed_days = self.days_elapsed
            return min(max(float((elapsed_days / total_days) * 100), 0), 100)
        return 0
    
    @property
    def burn_rate(self):
        """Daily spending rate"""
        days_elapsed = self.days_elapsed
        if days_elapsed > 0:
            return self.spent_amount / days_elapsed
        return Decimal('0.00')
    
    @property
    def projected_total_spend(self):
        """Projected total spend based on current burn rate"""
        burn_rate = self.burn_rate
        total_days = self.total_budget_days
        if burn_rate > 0 and total_days > 0:
            return burn_rate * total_days
        return self.spent_amount
    
    @property
    def projected_variance(self):
        """Projected variance at budget end"""
        total = self.total_amount or Decimal('0.00')
        projected = self.projected_total_spend
        return total - projected

    # ============================================================================
    # EFFICIENCY AND PERFORMANCE METRICS
    # ============================================================================
    
    @property
    def spending_efficiency(self):
        """Spending efficiency score (0-100)"""
        if self.total_amount > 0:
            # Ideal spending should match time progress
            time_progress = self.progress_percentage / 100
            spending_progress = self.spent_percentage / 100
            
            if time_progress > 0:
                efficiency = min(spending_progress / time_progress, 2.0)  # Cap at 200%
                return max(0, 100 - abs(100 - (efficiency * 100)))
        return 0
    
    @property
    def allocation_efficiency(self):
        """How efficiently budget is allocated"""
        if self.total_amount > 0:
            return min(float((self.allocated_amount / self.total_amount) * 100), 100)
        return 0
    
    @property
    def funding_efficiency(self):
        """How efficiently funding is utilized"""
        if self.total_funding_allocated > 0:
            return float((self.spent_amount / self.total_funding_allocated) * 100)
        return 0

    # ============================================================================
    # ITEM-LEVEL AGGREGATIONS
    # ============================================================================
    
    @property
    def total_budget_items_count(self):
        """Total number of budget items"""
        return self.items.count()
    
    @property
    def active_budget_items_count(self):
        """Number of active (not locked) budget items"""
        return self.items.filter(is_locked=False).count()
    
    @property
    def over_budget_items_count(self):
        """Number of budget items that are over budget"""
        count = 0
        for item in self.items.all():
            if item.is_over_budget:
                count += 1
        return count
    
    @property
    def critical_items_count(self):
        """Number of budget items in critical status"""
        count = 0
        for item in self.items.all():
            if item.utilization_status in ['CRITICAL', 'OVER_BUDGET']:
                count += 1
        return count

    # ============================================================================
    # FORMATTING PROPERTIES
    # ============================================================================
    
    @property
    def formatted_amount(self):
        """Formatted total amount with currency"""
        if self.currency:
            return f"{self.currency.code} {self.total_amount:,.2f}"
        return f"{self.total_amount:,.2f}"
    
    @property
    def formatted_spent_amount(self):
        """Formatted spent amount with currency"""
        if self.currency:
            return f"{self.currency.code} {self.spent_amount:,.2f}"
        return f"{self.spent_amount:,.2f}"
    
    @property
    def formatted_committed_amount(self):
        """Formatted committed amount with currency"""
        if self.currency:
            return f"{self.currency.code} {self.committed_amount:,.2f}"
        return f"{self.committed_amount:,.2f}"
    
    @property
    def formatted_pending_amount(self):
        """Formatted pending amount with currency"""
        if self.currency:
            return f"{self.currency.code} {self.pending_amount:,.2f}"
        return f"{self.pending_amount:,.2f}"
    
    @property
    def formatted_remaining_amount(self):
        """Formatted remaining amount with currency"""
        if self.currency:
            return f"{self.currency.code} {self.remaining_amount:,.2f}"
        return f"{self.remaining_amount:,.2f}"
    
    @property
    def formatted_available_amount(self):
        """Formatted available amount with currency"""
        if self.currency:
            return f"{self.currency.code} {self.truly_available_amount:,.2f}"
        return f"{self.truly_available_amount:,.2f}"
    
    @property
    def formatted_variance(self):
        """Formatted variance with currency and sign"""
        variance = self.variance
        sign = "+" if variance >= 0 else ""
        if self.currency:
            return f"{sign}{self.currency.code} {variance:,.2f}"
        return f"{sign}{variance:,.2f}"
    
    @property
    def formatted_funding_gap(self):
        """Formatted funding gap with currency"""
        if self.currency:
            return f"{self.currency.code} {self.funding_gap:,.2f}"
        return f"{self.funding_gap:,.2f}"

    # ============================================================================
    # COMPREHENSIVE SUMMARY PROPERTIES
    # ============================================================================
    
    @property
    def financial_summary(self):
        """Comprehensive financial summary"""
        return {
            'total_budget': self.total_amount,
            'allocated': self.allocated_amount,
            'unallocated': self.unallocated_amount,
            'spent': self.spent_amount,
            'committed': self.committed_amount,
            'pending': self.pending_amount,
            'remaining': self.remaining_amount,
            'truly_available': self.truly_available_amount,
            'currency': self.currency.code if self.currency else None
        }
    
    @property
    def performance_metrics(self):
        """Performance and efficiency metrics"""
        return {
            'spent_percentage': self.spent_percentage,
            'committed_percentage': self.committed_percentage,
            'utilization_percentage': self.utilization_percentage,
            'allocation_percentage': self.allocation_percentage,
            'spending_efficiency': self.spending_efficiency,
            'allocation_efficiency': self.allocation_efficiency,
            'funding_efficiency': self.funding_efficiency,
            'burn_rate': float(self.burn_rate),
            'projected_variance': float(self.projected_variance)
        }
    
    @property
    def status_summary(self):
        """Status and health summary"""
        return {
            'budget_health': self.budget_health,
            'utilization_status': self.utilization_status,
            'funding_status': self.funding_status,
            'is_over_budget': self.is_over_budget,
            'is_overcommitted': self.is_overcommitted,
            'is_fully_funded': self.is_fully_funded,
            'has_pending_requests': self.has_pending_requests,
            'is_expired': self.is_expired,
            'days_remaining': self.days_remaining,
            'progress_percentage': self.progress_percentage
        }

    @property
    def allocation_summary(self):
        """Comprehensive allocation summary"""
        return {
            'total_budget': self.total_amount,
            'total_fund_allocations': self.total_fund_allocations,
            'active_fund_allocations': self.active_fund_allocations,
            'allocation_gap': self.allocation_gap,
            'allocation_surplus': self.allocation_surplus,
            'allocation_coverage_percentage': self.allocation_coverage_percentage,
            'allocation_utilization_percentage': self.allocation_utilization_percentage,
            'available_from_allocations': self.available_from_allocations,
            'truly_available_from_allocations': self.truly_available_from_allocations,
            'allocation_status': self.allocation_status,
            'currency': self.currency.code if self.currency else None
        }

    @property
    def funding_vs_allocation_analysis(self):
        """Analysis comparing planned funding vs actual allocations"""
        return {
            'planned_funding': self.total_funding_allocated,
            'actual_allocations': self.total_fund_allocations,
            'funding_vs_allocation_gap': self.funding_vs_allocation_gap,
            'funding_realization_percentage': self.funding_realization_percentage,
            'allocation_coverage_percentage': self.allocation_coverage_percentage,
            'comprehensive_funding_status': self.comprehensive_funding_status,
            'is_funding_realized': self.funding_realization_percentage >= 100,
            'is_budget_covered': self.allocation_coverage_percentage >= 100,
            'currency': self.currency.code if self.currency else None
        }

    @property
    def enhanced_financial_summary(self):
        """Enhanced financial summary including allocations"""
        base_summary = self.financial_summary
        base_summary.update({
            'total_fund_allocations': self.total_fund_allocations,
            'allocation_gap': self.allocation_gap,
            'allocation_coverage_percentage': self.allocation_coverage_percentage,
            'funding_realization_percentage': self.funding_realization_percentage,
            'comprehensive_funding_status': self.comprehensive_funding_status,
            'available_from_allocations': self.available_from_allocations,
            'truly_available_from_allocations': self.truly_available_from_allocations
        })
        return base_summary

    # ============================================================================
    # EXISTING METHODS (Enhanced)
    # ============================================================================
    
    def get_budget_alerts(self):
        """Get comprehensive budget alerts and warnings including allocation alerts"""
        alerts = []
        
        try:
            # Critical alerts
            if self.is_over_budget:
                alerts.append({
                    'type': 'error',
                    'message': f'Budget is over spent by {self.formatted_variance}',
                    'severity': 'critical',
                    'category': 'spending'
                })
            
            if self.is_overcommitted:
                alerts.append({
                    'type': 'error',
                    'message': f'Budget is overcommitted by {self.currency.code if self.currency else ""} {abs(self.committed_variance):,.2f}',
                    'severity': 'critical',
                    'category': 'commitment'
                })
            
            # High priority warnings
            if self.utilization_percentage >= 95:
                alerts.append({
                    'type': 'warning',
                    'message': f'Budget utilization is {self.utilization_percentage:.1f}% - critically high',
                    'severity': 'high',
                    'category': 'utilization'
                })
            elif self.committed_percentage >= 90:
                alerts.append({
                    'type': 'warning',
                    'message': f'Budget is {self.committed_percentage:.1f}% committed - approaching limit',
                    'severity': 'medium',
                    'category': 'commitment'
                })
            
            # Funding alerts
            if self.funding_gap > 0:
                gap_percentage = float((self.funding_gap / self.total_amount) * 100)
                severity = 'high' if gap_percentage > 25 else 'medium'
                alerts.append({
                    'type': 'warning',
                    'message': f'Funding gap of {self.formatted_funding_gap} ({gap_percentage:.1f}%)',
                    'severity': severity,
                    'category': 'funding'
                })

            # Allocation-specific alerts
            if self.allocation_gap > 0:
                gap_percentage = float((self.allocation_gap / self.total_amount) * 100)
                severity = 'high' if gap_percentage > 25 else 'medium'
                alerts.append({
                    'type': 'warning',
                    'message': f'Allocation gap of {self.formatted_allocation_gap} ({gap_percentage:.1f}%)',
                    'severity': severity,
                    'category': 'allocation'
                })
        
            # Funding vs allocation mismatch
            if abs(self.funding_vs_allocation_gap) > (self.total_amount * Decimal('0.1')):  # 10% threshold
                gap = self.funding_vs_allocation_gap
                if gap > 0:
                    alerts.append({
                        'type': 'warning',
                        'message': f'Planned funding exceeds allocations by {self.formatted_funding_vs_allocation_gap}',
                        'severity': 'medium',
                        'category': 'funding_allocation_mismatch'
                    })
                else:
                    alerts.append({
                        'type': 'warning',
                        'message': f'Allocations exceed planned funding by {self.formatted_funding_vs_allocation_gap}',
                        'severity': 'medium',
                        'category': 'funding_allocation_mismatch'
                    })
        
            # Low funding realization
            if self.funding_realization_percentage < 50 and self.total_funding_allocated > 0:
                alerts.append({
                    'type': 'warning',
                    'message': f'Only {self.funding_realization_percentage:.1f}% of planned funding has been allocated',
                    'severity': 'medium',
                    'category': 'funding_realization'
                })
        
            # Over-allocation warning
            if self.allocation_surplus > 0:
                alerts.append({
                    'type': 'info',
                    'message': f'Budget is over-allocated by {self.currency.code if self.currency else ""} {self.allocation_surplus:,.2f}',
                    'severity': 'low',
                    'category': 'over_allocation'
                })
            
            # Time-based alerts
            if self.days_remaining <= 7 and self.days_remaining > 0:
                alerts.append({
                    'type': 'warning',
                    'message': f'Budget expires in {self.days_remaining} days',
                    'severity': 'medium',
                    'category': 'timeline'
                })
            elif self.is_expired:
                alerts.append({
                    'type': 'error',
                    'message': 'Budget period has expired',
                    'severity': 'high',
                    'category': 'timeline'
                })
            
            # Performance alerts
            if self.spending_efficiency < 50:
                alerts.append({
                    'type': 'info',
                    'message': f'Spending efficiency is low ({self.spending_efficiency:.1f}%)',
                    'severity': 'low',
                    'category': 'performance'
                })
            
            # Item-level alerts
            if self.critical_items_count > 0:
                alerts.append({
                    'type': 'warning',
                    'message': f'{self.critical_items_count} budget items in critical status',
                    'severity': 'medium',
                    'category': 'items'
                })
            
        except Exception:
            pass
        
        return alerts
    
    def get_fund_allocations_breakdown(self):
        """Get detailed breakdown of fund allocations by account"""
        try:
            allocations_data = []
            total_allocated = self.total_fund_allocations
            
            for allocation in self.fund_allocations.filter(is_active=True).select_related(
                'source_account', 'source_account__currency', 'allocated_by'
            ).order_by('-allocation_date'):
                
                amount = float(allocation.amount_allocated)
                percentage = (amount / float(total_allocated)) * 100 if total_allocated > 0 else 0
                
                allocations_data.append({
                    'id': allocation.id,
                    'account_name': allocation.source_account.name,
                    'account_type': allocation.source_account.get_account_type_display(),
                    'amount_allocated': amount,
                    'percentage_of_total': round(percentage, 2),
                    'currency_code': allocation.source_account.currency.code if allocation.source_account.currency else None,
                    'formatted_amount': allocation.formatted_amount,
                    'allocation_date': allocation.allocation_date.isoformat(),
                    'allocated_by': allocation.allocated_by.get_full_name() if allocation.allocated_by else 'Unknown',
                    'approved_by': allocation.approved_by.get_full_name() if allocation.approved_by else None,
                    'purpose': allocation.purpose,
                    'is_active': allocation.is_active,
                    'days_since_allocation': (timezone.now().date() - allocation.allocation_date.date()).days
                })
            
            return allocations_data
        except Exception as e:
            print(f"Error in get_fund_allocations_breakdown: {e}")
            return []

    def get_funding_vs_allocation_timeline(self):
        """Get timeline comparing funding sources vs actual allocations"""
        try:
            timeline_data = []
            
            # Add funding source events
            for funding in self.budget_funding.select_related('funding_source'):
                timeline_data.append({
                    'date': funding.allocation_date.isoformat() if funding.allocation_date else None,
                    'type': 'funding_source',
                    'description': f"Funding from {funding.funding_source.name}",
                    'amount': float(funding.amount_allocated),
                    'currency': funding.funding_source.currency.code if funding.funding_source.currency else None,
                    'status': 'planned',
                    'source': funding.funding_source.name
                })
            
            # Add allocation events
            for allocation in self.fund_allocations.filter(is_active=True).select_related('source_account'):
                timeline_data.append({
                    'date': allocation.allocation_date.isoformat(),
                    'type': 'fund_allocation',
                    'description': f"Allocation from {allocation.source_account.name}",
                    'amount': float(allocation.amount_allocated),
                    'currency': allocation.source_account.currency.code if allocation.source_account.currency else None,
                    'status': 'allocated',
                    'source': allocation.source_account.name,
                    'purpose': allocation.purpose
                })
            
            # Sort by date
            timeline_data.sort(key=lambda x: x['date'] or '1900-01-01')
            
            return timeline_data
        except Exception as e:
            print(f"Error in get_funding_vs_allocation_timeline: {e}")
            return []

    def get_allocation_utilization_analysis(self):
        """Analyze how allocated funds are being utilized"""
        try:
            total_allocated = self.total_fund_allocations
            total_spent = self.spent_amount
            total_committed = self.committed_amount
            total_pending = self.pending_amount
            
            return {
                'total_allocated': float(total_allocated),
                'total_spent': float(total_spent),
                'total_committed': float(total_committed),
                'total_pending': float(total_pending),
                'spent_percentage': float((total_spent / total_allocated) * 100) if total_allocated > 0 else 0,
                'committed_percentage': float((total_committed / total_allocated) * 100) if total_allocated > 0 else 0,
                'utilization_percentage': float(((total_committed + total_pending) / total_allocated) * 100) if total_allocated > 0 else 0,
                'remaining_allocated': float(total_allocated - total_spent),
                'available_allocated': float(total_allocated - total_committed),
                'truly_available_allocated': float(total_allocated - total_committed - total_pending),
                'allocation_efficiency': self.allocation_utilization_percentage,
                'is_over_allocated': total_committed > total_allocated,
                'is_allocation_exhausted': total_allocated <= total_committed,
                'currency': self.currency.code if self.currency else None
            }
        except Exception as e:
            print(f"Error in get_allocation_utilization_analysis: {e}")
            return {}
     
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
                    'percentage_of_budget': float((funding.amount_allocated / self.total_amount) * 100) if self.total_amount > 0 else 0,
                    'is_active': funding.funding_source.is_active,
                    'notes': funding.notes if hasattr(funding, 'notes') else ''
                })
            return funding_data
        except Exception as e:
            print(f"Error in get_funding_breakdown: {e}")
            return []
    
    def get_spending_by_category(self):
        """Get spending breakdown by budget item category"""
        try:
            from django.db.models import Sum
            from collections import defaultdict
            
            # Get all budget items grouped by category
            categories = self.items.values('category').annotate(
                total_budgeted=Sum('budgeted_amount')
            ).order_by('category')
            
            category_data = []
            for category in categories:
                category_name = category['category']
                budgeted = category['total_budgeted'] or Decimal('0.00')
                
                # Get all items in this category
                category_items = self.items.filter(category=category_name)
                
                # Calculate totals by iterating through items and using their properties
                total_spent = Decimal('0.00')
                total_committed = Decimal('0.00')
                total_pending = Decimal('0.00')
                
                for item in category_items:
                    total_spent += item.spent_amount
                    total_committed += item.committed_amount
                    total_pending += item.pending_amount
                
                remaining = budgeted - total_spent
                
                category_data.append({
                    'category': category_name,
                    'budgeted_amount': str(budgeted),
                    'spent_amount': str(total_spent),
                    'committed_amount': str(total_committed),
                    'pending_amount': str(total_pending),
                    'remaining_amount': str(remaining),
                    'spent_percentage': float((total_spent / budgeted) * 100) if budgeted > 0 else 0,
                    'committed_percentage': float((total_committed / budgeted) * 100) if budgeted > 0 else 0,
                    'utilization_percentage': float(((total_committed + total_pending) / budgeted) * 100) if budgeted > 0 else 0
                })
            return category_data
        except Exception as e:
            print(f"Error in get_spending_by_category: {e}")
            return []
    
    def get_monthly_spending_trend(self):
        """Get monthly spending trend for this budget"""
        try:
            from django.db.models import Sum
            from django.db.models.functions import TruncMonth
        
            # Get spending data for the budget period
            start_date = self.start_date
            end_date = min(self.end_date, timezone.now().date())
        
            # Get monthly data from organizational expenses through budget items
            monthly_data = OrganizationalExpense.objects.filter(
                budget_item__budget=self,
                expense_date__gte=start_date,
                expense_date__lte=end_date,
                status='paid'
            ).annotate(
                month=TruncMonth('expense_date')
            ).values('month').annotate(
                total_spent=Sum('amount')
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
        except Exception as e:
            print(f"Error in get_monthly_spending_trend: {e}")
            return []
    
    def get_budget_utilization_by_item(self):
        """Get utilization percentage for each budget item"""
        try:
            items_data = []
            for item in self.items.all():
                spent_utilization = 0
                committed_utilization = 0
                total_utilization = 0
                
                if item.budgeted_amount and item.budgeted_amount > 0:
                    spent_utilization = float((item.spent_amount / item.budgeted_amount) * 100)
                    committed_utilization = float((item.committed_amount / item.budgeted_amount) * 100)
                    total_utilization = float((item.utilization_percentage))
                
                items_data.append({
                    'id': item.id,
                    'category': item.category,
                    'subcategory': item.subcategory or '',
                    'description': item.description,
                    'budgeted_amount': str(item.budgeted_amount),
                    'spent_amount': str(item.spent_amount),
                    'committed_amount': str(item.committed_amount),
                    'pending_amount': str(item.pending_amount),
                    'remaining_amount': str(item.remaining_amount),
                    'truly_available_amount': str(item.truly_available_amount),
                    'spent_percentage': spent_utilization,
                    'committed_percentage': committed_utilization,
                    'utilization_percentage': total_utilization,
                    'status': item.utilization_status,
                    'budget_health': item.budget_health,
                    'is_locked': item.is_locked,
                    'is_over_budget': item.is_over_budget,
                    'is_overcommitted': item.is_overcommitted,
                    'has_pending_requests': item.has_pending_requests,
                    'responsible_person': item.responsible_person.get_full_name() if item.responsible_person else None
                })
            return items_data
        except Exception as e:
            print(f"Error in get_budget_utilization_by_item: {e}")
            return []
    
    def get_funding_vs_spending_analysis(self):
        """Compare funding received vs actual spending"""
        try:
            total_budget = self.total_amount or Decimal('0.00')
            total_funded = self.total_funding_allocated
            total_spent = self.spent_amount
            total_committed = self.committed_amount
            total_pending = self.pending_amount
            funding_gap = self.funding_gap
            
            return {
                'total_budget': str(total_budget),
                'total_funded': str(total_funded),
                'total_spent': str(total_spent),
                'total_committed': str(total_committed),
                'total_pending': str(total_pending),
                'funding_gap': str(funding_gap),
                'funding_surplus': str(self.funding_surplus),
                'spending_vs_funding_ratio': float((total_spent / total_funded) * 100) if total_funded > 0 else 0,
                'committed_vs_funding_ratio': float((total_committed / total_funded) * 100) if total_funded > 0 else 0,
                'budget_utilization': self.spent_percentage,
                'committed_utilization': self.committed_percentage,
                'total_utilization': self.utilization_percentage,
                'funding_utilization': float((total_funded / total_budget) * 100) if total_budget > 0 else 0,
                'funding_efficiency': self.funding_efficiency,
                'spending_efficiency': self.spending_efficiency,
                'is_overspent': self.is_over_budget,
                'is_overcommitted': self.is_overcommitted,
                'is_underfunded': not self.is_fully_funded,
                'has_pending_requests': self.has_pending_requests,
                'currency': self.currency.code if self.currency else None
            }
        except Exception as e:
            print(f"Error in get_funding_vs_spending_analysis: {e}")
            return {}
    
       
    def __str__(self):
        return f"{self.title} - {self.get_budget_type_display()} ({self.formatted_amount})"

    def __str__(self):
        return f"{self.title} - {self.get_budget_type_display()} ({self.formatted_amount})"


class BudgetFunding(models.Model):
    """Through model for budget funding sources"""
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name='budget_funding')
    funding_source = models.ForeignKey(FundingSource, on_delete=models.CASCADE, related_name='allocations')
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
        """Calculate total spent from paid expenses only"""
        try:
            return self.organizational_expenses.filter(status='paid').aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0.00')
        except Exception:
            return Decimal('0.00')
    
    @property
    def pending_amount(self):
        """Calculate total pending from draft and pending expenses"""
        try:
            return self.organizational_expenses.filter(status__in=['pending', 'draft']).aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0.00')
        except Exception:
            return Decimal('0.00')
        
    @property
    def committed_amount(self):
        """Calculate total committed (approved + paid) expenses"""
        try:
            return self.organizational_expenses.filter(status__in=['approved', 'paid']).aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0.00')
        except Exception:
            return Decimal('0.00')

    @property
    def approved_amount(self):
        """Calculate total approved but not yet paid expenses"""
        try:
            return self.organizational_expenses.filter(status='approved').aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0.00')
        except Exception:
            return Decimal('0.00')

    @property
    def rejected_amount(self):
        """Calculate total rejected expenses"""
        try:
            return self.organizational_expenses.filter(status='rejected').aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0.00')
        except Exception:
            return Decimal('0.00')

    @property
    def total_requested_amount(self):
        """Calculate total of all expenses regardless of status"""
        try:
            return self.organizational_expenses.aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0.00')
        except Exception:
            return Decimal('0.00')

    @property
    def remaining_amount(self):
        """Amount remaining after actual spending (paid expenses only)"""
        budgeted = self.budgeted_amount or Decimal('0.00')
        spent = self.spent_amount
        return budgeted - spent

    @property
    def available_amount(self):
        """Amount available considering committed expenses (approved + paid)"""
        budgeted = self.budgeted_amount or Decimal('0.00')
        committed = self.committed_amount
        return budgeted - committed

    @property
    def encumbered_amount(self):
        """Amount encumbered by pending and approved expenses"""
        return self.pending_amount + self.approved_amount

    @property
    def truly_available_amount(self):
        """Amount truly available after all commitments and pending requests"""
        budgeted = self.budgeted_amount or Decimal('0.00')
        total_obligations = self.committed_amount + self.pending_amount
        return budgeted - total_obligations

    @property
    def spent_percentage(self):
        """Percentage of budget actually spent (paid expenses only)"""
        budgeted = self.budgeted_amount or Decimal('0.00')
        if budgeted > 0:
            spent = self.spent_amount
            return float((spent / budgeted) * 100)
        return 0

    @property
    def committed_percentage(self):
        """Percentage of budget committed (approved + paid)"""
        budgeted = self.budgeted_amount or Decimal('0.00')
        if budgeted > 0:
            committed = self.committed_amount
            return float((committed / budgeted) * 100)
        return 0

    @property
    def utilization_percentage(self):
        """Total utilization including all pending requests"""
        budgeted = self.budgeted_amount or Decimal('0.00')
        if budgeted > 0:
            total_obligations = self.committed_amount + self.pending_amount
            return float((total_obligations / budgeted) * 100)
        return 0

    @property
    def variance(self):
        """Budget variance based on actual spending (positive = under budget)"""
        budgeted = self.budgeted_amount or Decimal('0.00')
        spent = self.spent_amount
        return budgeted - spent

    @property
    def variance_percentage(self):
        """Variance as percentage of budget"""
        budgeted = self.budgeted_amount or Decimal('0.00')
        if budgeted > 0:
            variance = self.variance
            return float((variance / budgeted) * 100)
        return 0

    @property
    def committed_variance(self):
        """Variance considering committed expenses"""
        budgeted = self.budgeted_amount or Decimal('0.00')
        committed = self.committed_amount
        return budgeted - committed

    @property
    def utilization_status(self):
        """Returns budget utilization status based on committed percentage"""
        percentage = self.committed_percentage
        if percentage >= 100:
            return 'OVER_BUDGET'
        elif percentage >= 90:
            return 'CRITICAL'
        elif percentage >= 75:
            return 'WARNING'
        elif percentage >= 50:
            return 'MODERATE'
        else:
            return 'NORMAL'

    @property
    def budget_health(self):
        """Overall budget health considering all factors"""
        utilization = self.utilization_percentage
        if utilization > 100:
            return 'OVERCOMMITTED'
        elif utilization > 95:
            return 'AT_RISK'
        elif utilization > 80:
            return 'CAUTION'
        elif utilization > 50:
            return 'HEALTHY'
        else:
            return 'UNDERUTILIZED'

    @property
    def is_over_budget(self):
        """Check if actual spending exceeds budget"""
        return self.spent_amount > (self.budgeted_amount or Decimal('0.00'))

    @property
    def is_overcommitted(self):
        """Check if committed expenses exceed budget"""
        return self.committed_amount > (self.budgeted_amount or Decimal('0.00'))

    @property
    def has_pending_requests(self):
        """Check if there are pending expense requests"""
        return self.pending_amount > Decimal('0.00')

    @property
    def can_spend(self):
        """Check if item allows spending (not locked and has available budget)"""
        return not self.is_locked and self.truly_available_amount > 0

    @property
    def requires_approval_for_remaining(self):
        """Check if remaining expenses require approval"""
        if not self.approval_required_threshold:
            return False
        return self.truly_available_amount > (self.approval_required_threshold or Decimal('0.00'))

    @property
    def available_without_approval(self):
        """Maximum amount that can be spent without approval"""
        if not self.approval_required_threshold:
            return self.truly_available_amount
        return min(self.truly_available_amount, self.approval_required_threshold or Decimal('0.00'))


    @property
    def formatted_amount(self):
        """Formatted budgeted amount with currency"""
        if self.budget and self.budget.currency:
            return f"{self.budget.currency.code} {self.budgeted_amount:,.2f}"
        return f"{self.budgeted_amount:,.2f}"

    @property
    def formatted_spent_amount(self):
        """Formatted spent amount with currency"""
        if self.budget and self.budget.currency:
            return f"{self.budget.currency.code} {self.spent_amount:,.2f}"
        return f"{self.spent_amount:,.2f}"

    @property
    def formatted_remaining_amount(self):
        """Formatted remaining amount with currency"""
        if self.budget and self.budget.currency:
            return f"{self.budget.currency.code} {self.remaining_amount:,.2f}"
        return f"{self.remaining_amount:,.2f}"

    @property
    def formatted_committed_amount(self):
        """Formatted committed amount with currency"""
        if self.budget and self.budget.currency:
            return f"{self.budget.currency.code} {self.committed_amount:,.2f}"
        return f"{self.committed_amount:,.2f}"

    @property
    def formatted_pending_amount(self):
        """Formatted pending amount with currency"""
        if self.budget and self.budget.currency:
            return f"{self.budget.currency.code} {self.pending_amount:,.2f}"
        return f"{self.pending_amount:,.2f}"

    @property
    def formatted_available_amount(self):
        """Formatted available amount with currency"""
        if self.budget and self.budget.currency:
            return f"{self.budget.currency.code} {self.truly_available_amount:,.2f}"
        return f"{self.truly_available_amount:,.2f}"

    @property
    def total_expenses_count(self):
        """Total number of expenses"""
        return self.organizational_expenses.count()

    @property
    def paid_expenses_count(self):
        """Number of paid expenses"""
        return self.organizational_expenses.filter(status='paid').count()

    @property
    def pending_expenses_count(self):
        """Number of pending expenses"""
        return self.organizational_expenses.filter(status__in=['pending', 'draft']).count()

    @property
    def approved_expenses_count(self):
        """Number of approved expenses"""
        return self.organizational_expenses.filter(status='approved').count()

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
    title = models.CharField(max_length=256)
    description = models.TextField()
    expense_type = models.CharField(max_length=20, choices=EXPENSE_TYPE_CHOICES)
    
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
        related_name='fund_allocations',
        null=True,
        blank=True
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


