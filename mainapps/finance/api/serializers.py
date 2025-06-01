from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db.models import Sum, Count, Avg
from decimal import Decimal
from ..models import (
    FinancialInstitution, BankAccount, ExchangeRate, DonationCampaign,
    Donation, RecurringDonation, InKindDonation, Grant, GrantReport,
    FundingSource, Budget, BudgetFunding, BudgetItem, OrganizationalExpense,
    AccountTransaction, FundAllocation, CampaignBankAccount
)
from mainapps.common.models import Currency
from mainapps.accounts.models import Department
from mainapps.project.models import Project
from mainapps.project.api.serializers import ProjectMinimalSerializer

User = get_user_model()

class UserBasicSerializer(serializers.ModelSerializer):
    """Basic user info for nested serialization"""
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'full_name']
        read_only_fields = ['id', 'username', 'email', 'full_name']

class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = ['id', 'code', 'name',]

class FinancialInstitutionSerializer(serializers.ModelSerializer):
    accounts_count = serializers.SerializerMethodField()
    
    class Meta:
        model = FinancialInstitution
        fields = [
            'id', 'name', 'code', 'branch_name', 'branch_code', 'address',
            'contact_person', 'contact_phone', 'contact_email', 'is_active',
            'created_at', 'accounts_count'
        ]
        read_only_fields = ['id', 'created_at', 'accounts_count']
    
    def get_accounts_count(self, obj):
        return obj.accounts.filter(is_active=True).count()

class BankAccountMinimalSerializer(serializers.ModelSerializer):
    """Minimal bank account info for campaign bank accounts"""
    financial_institution = serializers.StringRelatedField(read_only=True)
    currency = CurrencySerializer(read_only=True)
    formatted_balance = serializers.CharField(read_only=True)
    
    class Meta:
        model = BankAccount
        fields = [
            'id', 'name', 'account_number', 'account_type', 'financial_institution',
            'currency', 'purpose', 'is_active', 'accepts_donations', 'formatted_balance'
        ]
class MinimalAccountTransactionSerializer(serializers.ModelSerializer):
    """Minimal account transaction info for campaign bank accounts"""
    class Meta:
        model = AccountTransaction
        fields = '__all__'
class BankAccountSerializer(serializers.ModelSerializer):
    financial_institution = FinancialInstitutionSerializer(read_only=True)
    financial_institution_id = serializers.IntegerField(write_only=True)
    currency = CurrencySerializer(read_only=True)
    currency_id = serializers.IntegerField(write_only=True)
    primary_signatory = UserBasicSerializer(read_only=True)
    primary_signatory_id = serializers.IntegerField(write_only=True)
    secondary_signatories = UserBasicSerializer(many=True, read_only=True)
    secondary_signatory_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )
    created_by = UserBasicSerializer(read_only=True)
    # transactions=MinimalAccountTransactionSerializer(many=True, read_only=True)
    # Existing computed fields
    current_balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    formatted_balance = serializers.CharField(read_only=True)
    transactions_count = serializers.SerializerMethodField()
    
    # New computed properties
    is_overdrawn = serializers.BooleanField(read_only=True)
    available_balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    is_low_balance = serializers.BooleanField(read_only=True)
    days_since_last_reconciliation = serializers.IntegerField(read_only=True)
    needs_reconciliation = serializers.BooleanField(read_only=True)
    monthly_fee_due_date = serializers.DateField(read_only=True)
    transaction_volume_30_days = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    average_monthly_balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    
    class Meta:
        model = BankAccount
        fields = [
            # Basic Information
            'id', 'name', 'account_number', 'account_type', 'financial_institution',
            'financial_institution_id', 'currency', 'currency_id', 'purpose',
            
            # Restrictions and Management
            'is_restricted', 'restrictions', 'primary_signatory', 'primary_signatory_id',
            'secondary_signatories', 'secondary_signatory_ids',
            
            # Status and Dates
            'is_active', 'account_status', 'accepts_donations', 'opening_date', 
            'closing_date', 'minimum_balance',
            
            # Enhanced Banking Features
            'online_banking_enabled', 'mobile_banking_enabled', 'debit_card_enabled',
            
            # Account Identifiers
            'routing_number', 'swift_code', 'iban', 'branch_address',
            
            # Financial Features
            'overdraft_protection', 'overdraft_limit', 'interest_rate', 
            'monthly_maintenance_fee',
            
            # Risk and Compliance
            'risk_level', 'compliance_status',
            
            # Reconciliation and Tracking
            'last_reconciled_date', 'auto_reconciliation_enabled', 'last_transaction_date',
            
            # Digital Platform Details
            'api_key', 'webhook_url',
            
            # Additional Information
            'notes',
            
            # Tracking
            'created_by', 'created_at', 'updated_at',
            
            # Computed Properties
            'current_balance', 'formatted_balance', 'is_overdrawn', 'available_balance',
            'is_low_balance', 'days_since_last_reconciliation', 'needs_reconciliation',
            'monthly_fee_due_date', 'transaction_volume_30_days', 'average_monthly_balance',
            'transactions_count'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']
        # extra_kwargs = {
        #     'api_key': {'write_only': True},
        # }
    
    def get_transactions_count(self, obj):
        return obj.transactions.count()
    
    def validate(self, attrs):
        # Validate overdraft settings
        if attrs.get('overdraft_protection') and not attrs.get('overdraft_limit'):
            raise serializers.ValidationError(
                "Overdraft limit is required when overdraft protection is enabled"
            )
        
        # Validate closing date
        if attrs.get('closing_date') and attrs.get('opening_date'):
            if attrs['closing_date'] <= attrs['opening_date']:
                raise serializers.ValidationError(
                    "Closing date must be after opening date"
                )
        
        # Validate SWIFT code
        swift_code = attrs.get('swift_code')
        if swift_code and len(swift_code) not in [8, 11]:
            raise serializers.ValidationError(
                "SWIFT code must be 8 or 11 characters long"
            )
        
        # Validate IBAN
        iban = attrs.get('iban')
        if iban and len(iban) < 15:
            raise serializers.ValidationError(
                "IBAN must be at least 15 characters long"
            )
        
        return attrs
    
    def create(self, validated_data):
        secondary_signatory_ids = validated_data.pop('secondary_signatory_ids', [])
        account = super().create(validated_data)
        if secondary_signatory_ids:
            account.secondary_signatories.set(secondary_signatory_ids)
        return account
    
    def update(self, instance, validated_data):
        secondary_signatory_ids = validated_data.pop('secondary_signatory_ids', None)
        account = super().update(instance, validated_data)
        if secondary_signatory_ids is not None:
            account.secondary_signatories.set(secondary_signatory_ids)
        return account

class CampaignBankAccountSerializer(serializers.ModelSerializer):
    """Serializer for campaign-bank account relationship"""
    bank_account = BankAccountMinimalSerializer(read_only=True)
    bank_account_id = serializers.IntegerField(write_only=True)
    added_by = UserBasicSerializer(read_only=True)
    
    class Meta:
        model = CampaignBankAccount
        fields = [
            'id', 'bank_account', 'bank_account_id', 'is_primary', 'is_active',
            'priority_order', 'notes', 'added_by', 'added_at'
        ]
        read_only_fields = ['id', 'added_by', 'added_at']

class ExchangeRateSerializer(serializers.ModelSerializer):
    from_currency = CurrencySerializer(read_only=True)
    from_currency_id = serializers.IntegerField(write_only=True)
    to_currency = CurrencySerializer(read_only=True)
    to_currency_id = serializers.IntegerField(write_only=True)
    created_by = UserBasicSerializer(read_only=True)
    
    class Meta:
        model = ExchangeRate
        fields = [
            'id', 'from_currency', 'from_currency_id', 'to_currency', 'to_currency_id',
            'rate', 'effective_date', 'source', 'created_by', 'created_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_at']

class DonationCampaignListSerializer(serializers.ModelSerializer):
    """List serializer for donation campaigns - optimized for performance"""
    target_currency = CurrencySerializer(read_only=True)
    target_currency_id = serializers.IntegerField(write_only=True)
    project = ProjectMinimalSerializer(read_only=True)
    project_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    created_by = UserBasicSerializer(read_only=True)
    
    # Core financial metrics (properties from enhanced model)
    current_amount = serializers.ReadOnlyField()
    progress_percentage = serializers.ReadOnlyField()
    amount_remaining = serializers.ReadOnlyField()
    formatted_target_amount = serializers.ReadOnlyField()
    formatted_current_amount = serializers.ReadOnlyField()
    
    # Status and health
    campaign_status = serializers.ReadOnlyField()
    fundraising_health = serializers.ReadOnlyField()
    is_target_reached = serializers.ReadOnlyField()
    can_receive_donations = serializers.ReadOnlyField()
    
    # Time-based metrics
    days_remaining = serializers.ReadOnlyField()
    days_elapsed = serializers.ReadOnlyField()
    time_progress_percentage = serializers.ReadOnlyField()
    
    # Basic statistics
    total_donors_count = serializers.ReadOnlyField()
    total_donations_count = serializers.ReadOnlyField()
    
    class Meta:
        model = DonationCampaign
        fields = [
            'id', 'title', 'slug', 'description', 'campaign_type', 'target_amount', 
            'target_currency', 'target_currency_id', 'minimum_goal', 'start_date', 
            'end_date', 'project', 'project_id', 'status', 'is_active', 'is_featured',
            'image','video', 'created_by', 'created_at', 'updated_at',
            # Enhanced properties
            'current_amount', 'progress_percentage', 'amount_remaining',
            'formatted_target_amount', 'formatted_current_amount', 'campaign_status',
            'fundraising_health', 'is_target_reached', 'can_receive_donations',
            'days_remaining', 'days_elapsed', 'time_progress_percentage',
            'total_donors_count', 'total_donations_count'
        ]
        read_only_fields = ['id', 'slug', 'created_by', 'created_at', 'updated_at']

class DonationCampaignDetailSerializer(serializers.ModelSerializer):
    """Comprehensive detail serializer for donation campaigns"""
    target_currency = CurrencySerializer(read_only=True)
    target_currency_id = serializers.IntegerField(write_only=True)
    project = ProjectMinimalSerializer(read_only=True)
    project_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    created_by = UserBasicSerializer(read_only=True)
    managed_by = UserBasicSerializer(many=True, read_only=True)
    
    # Core financial metrics
    current_amount = serializers.ReadOnlyField()
    total_donations_amount = serializers.ReadOnlyField()
    total_recurring_amount = serializers.ReadOnlyField()
    total_in_kind_amount = serializers.ReadOnlyField()
    net_donations_amount = serializers.ReadOnlyField()
    
    # Progress and goals
    progress_percentage = serializers.ReadOnlyField()
    minimum_goal_percentage = serializers.ReadOnlyField()
    amount_remaining = serializers.ReadOnlyField()
    amount_over_target = serializers.ReadOnlyField()
    is_target_reached = serializers.ReadOnlyField()
    is_minimum_reached = serializers.ReadOnlyField()
    
    # Donation statistics
    total_donors_count = serializers.ReadOnlyField()
    total_donations_count = serializers.ReadOnlyField()
    average_donation_amount = serializers.ReadOnlyField()
    largest_donation_amount = serializers.ReadOnlyField()
    
    # Time-based calculations
    days_remaining = serializers.ReadOnlyField()
    days_elapsed = serializers.ReadOnlyField()
    total_campaign_days = serializers.ReadOnlyField()
    time_progress_percentage = serializers.ReadOnlyField()
    daily_fundraising_rate = serializers.ReadOnlyField()
    projected_final_amount = serializers.ReadOnlyField()
    
    # Status and health
    campaign_status = serializers.ReadOnlyField()
    fundraising_health = serializers.ReadOnlyField()
    is_active_period = serializers.ReadOnlyField()
    is_expired = serializers.ReadOnlyField()
    can_receive_donations = serializers.ReadOnlyField()
    
    # Formatted properties
    formatted_target_amount = serializers.ReadOnlyField()
    formatted_current_amount = serializers.ReadOnlyField()
    formatted_amount_remaining = serializers.ReadOnlyField()
    formatted_minimum_goal = serializers.ReadOnlyField()
    
    # Comprehensive data methods
    donation_breakdown = serializers.ReadOnlyField()
    performance_metrics = serializers.ReadOnlyField()
    
    # Recent donations (limited for performance)
    recent_donations = serializers.SerializerMethodField()
    recent_recurring_donations = serializers.SerializerMethodField()
    recent_in_kind_donations = serializers.SerializerMethodField()
    
    # Analytics data
    donation_trends = serializers.SerializerMethodField()
    donor_segments = serializers.SerializerMethodField()
    payment_method_breakdown = serializers.SerializerMethodField()
    
    class Meta:
        model = DonationCampaign
        fields = [
            'id', 'title', 'slug', 'description', 'campaign_type', 'target_amount',
            'target_currency', 'target_currency_id', 'minimum_goal', 'start_date',
            'end_date', 'launch_date', 'project', 'project_id', 'status', 'is_active',
            'is_featured', 'allow_anonymous_donations', 'allow_recurring_donations',
            'allow_in_kind_donations', 'image', 'video', 'created_by', 'managed_by',
            'created_at', 'updated_at',
            # Enhanced financial metrics
            'current_amount', 'total_donations_amount', 'total_recurring_amount',
            'total_in_kind_amount', 'net_donations_amount',
            # Progress and goals
            'progress_percentage', 'minimum_goal_percentage', 'amount_remaining',
            'amount_over_target', 'is_target_reached', 'is_minimum_reached',
            # Statistics
            'total_donors_count', 'total_donations_count', 'average_donation_amount',
            'largest_donation_amount',
            # Time-based
            'days_remaining', 'days_elapsed', 'total_campaign_days',
            'time_progress_percentage', 'daily_fundraising_rate', 'projected_final_amount',
            # Status and health
            'campaign_status', 'fundraising_health', 'is_active_period', 'is_expired',
            'can_receive_donations',
            # Formatted
            'formatted_target_amount', 'formatted_current_amount', 'formatted_amount_remaining',
            'formatted_minimum_goal',
            # Comprehensive data
            'donation_breakdown', 'performance_metrics',
            # Related data
            'recent_donations', 'recent_recurring_donations', 'recent_in_kind_donations',
            # Analytics
            'donation_trends', 'donor_segments', 'payment_method_breakdown'
        ]
        read_only_fields = ['id', 'slug', 'created_by', 'created_at', 'updated_at']
    
    def get_recent_donations(self, obj):
        """Get recent completed donations"""
        donations = obj.donations.filter(status='completed').select_related(
            'donor', 'currency'
        ).order_by('-donation_date')[:10]
        return DonationListSerializer(donations, many=True).data
    
    def get_recent_recurring_donations(self, obj):
        """Get recent active recurring donations"""
        recurring = obj.recurring_donations.filter(
            status__in=['active', 'completed']
        ).select_related('donor', 'currency').order_by('-created_at')[:10]
        return RecurringDonationListSerializer(recurring, many=True).data
    
    def get_recent_in_kind_donations(self, obj):
        """Get recent received in-kind donations"""
        in_kind = obj.in_kind_donations.filter(status='received').select_related(
            'donor', 'valuation_currency'
        ).order_by('-donation_date')[:10]
        return InKindDonationListSerializer(in_kind, many=True).data
    
    def get_donation_trends(self, obj):
        """Get donation trends over time"""
        from django.utils import timezone
        from datetime import timedelta
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        
        # Daily donation totals for the last 30 days
        donations = obj.donations.filter(
            status='completed',
            donation_date__date__gte=start_date,
            donation_date__date__lte=end_date
        ).extra(
            select={'day': 'DATE(donation_date)'}
        ).values('day').annotate(
            count=Count('id'),
            total=Sum('amount')
        ).order_by('day')
        
        return list(donations)
    
    def get_donor_segments(self, obj):
        """Segment donors by donation amount ranges"""
        donations = obj.donations.filter(status='completed')
        
        segments = {
            'micro': donations.filter(amount__lt=50).values('donor').distinct().count(),
            'small': donations.filter(amount__gte=50, amount__lt=250).values('donor').distinct().count(),
            'medium': donations.filter(amount__gte=250, amount__lt=1000).values('donor').distinct().count(),
            'large': donations.filter(amount__gte=1000, amount__lt=5000).values('donor').distinct().count(),
            'major': donations.filter(amount__gte=5000).values('donor').distinct().count(),
        }
        
        return segments
    
    def get_payment_method_breakdown(self, obj):
        """Get breakdown by payment method"""
        return list(obj.donations.filter(status='completed').values('payment_method').annotate(
            count=Count('id'),
            total=Sum('amount'),
            avg=Avg('amount')
        ).order_by('-total'))

# ============================================================================
# DONATION SERIALIZERS
# ============================================================================

class DonationListSerializer(serializers.ModelSerializer):
    """List serializer for donations - optimized for performance"""
    donor = UserBasicSerializer(read_only=True)
    donor_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    campaign = serializers.StringRelatedField(read_only=True)
    campaign_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    project = serializers.StringRelatedField(read_only=True)
    project_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    currency = CurrencySerializer(read_only=True)
    currency_id = serializers.IntegerField(write_only=True)
    
    # Enhanced properties from model
    donor_name_display = serializers.ReadOnlyField()
    formatted_amount = serializers.ReadOnlyField()
    formatted_net_amount = serializers.ReadOnlyField()
    net_amount = serializers.ReadOnlyField()
    processor_fee_percentage = serializers.ReadOnlyField()
    is_completed = serializers.ReadOnlyField()
    is_recent = serializers.ReadOnlyField()
    days_since_donation = serializers.ReadOnlyField()
    
    class Meta:
        model = Donation
        fields = [
            'id', 'donor', 'donor_id', 'is_anonymous', 'donor_name', 'donor_email',
            'campaign', 'campaign_id', 'project', 'project_id', 'amount', 'currency',
            'currency_id', 'payment_method', 'donation_date', 'status',
            'processor_fee', 'tax_deductible', 'receipt_sent', 'created_at',
            # Enhanced properties
            'donor_name_display', 'formatted_amount', 'formatted_net_amount',
            'net_amount', 'processor_fee_percentage', 'is_completed', 'is_recent',
            'days_since_donation'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

class DonationDetailSerializer(serializers.ModelSerializer):
    """Comprehensive detail serializer for donations"""
    donor = UserBasicSerializer(read_only=True)
    donor_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    campaign = DonationCampaignListSerializer(read_only=True)
    campaign_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    project = ProjectMinimalSerializer(read_only=True)
    project_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    currency = CurrencySerializer(read_only=True)
    currency_id = serializers.IntegerField(write_only=True)
    converted_currency = CurrencySerializer(read_only=True)
    processor_fee_currency = CurrencySerializer(read_only=True)
    processed_by = UserBasicSerializer(read_only=True)
    
    net_amount = serializers.ReadOnlyField()
    effective_amount = serializers.ReadOnlyField()
    processor_fee_percentage = serializers.ReadOnlyField()
    net_percentage = serializers.ReadOnlyField()
    
    # Status and validation
    is_completed = serializers.ReadOnlyField()
    is_refundable = serializers.ReadOnlyField()
    is_tax_receipt_eligible = serializers.ReadOnlyField()
    requires_receipt = serializers.ReadOnlyField()
    days_since_donation = serializers.ReadOnlyField()
    is_recent = serializers.ReadOnlyField()
    
    # Donor information
    donor_name_display = serializers.ReadOnlyField()
    donor_email_display = serializers.ReadOnlyField()
    has_complete_donor_info = serializers.ReadOnlyField()
    
    # Formatted properties
    formatted_amount = serializers.ReadOnlyField()
    formatted_net_amount = serializers.ReadOnlyField()
    formatted_processor_fee = serializers.ReadOnlyField()
    formatted_converted_amount = serializers.ReadOnlyField()
    
    # Comprehensive data
    attribution_data = serializers.ReadOnlyField()
    financial_summary = serializers.ReadOnlyField()
    d_type=serializers.SerializerMethodField()
    class Meta:
        model = Donation
        fields = [
            'id', 'donor', 'donor_id', 'is_anonymous', 'donor_name', 'donor_email',
            'donor_phone', 'campaign', 'campaign_id', 'project', 'project_id',
            'amount', 'currency', 'currency_id', 'exchange_rate', 'converted_amount',
            'converted_currency', 'payment_method', 'processor_fee', 'processor_fee_currency',
            'transaction_id', 'reference_number', 'bank_reference', 'donation_date',
            'processed_date', 'status', 'donation_source', 'referral_source',
            'utm_source', 'utm_medium', 'utm_campaign', 'is_recurring_eligible',
            'marketing_opt_in', 'newsletter_opt_in', 'receipt_sent', 'receipt_number',
            'receipt_sent_date', 'tax_deductible', 'receipt_image', 'notes',
            'internal_notes', 'processed_by', 'created_at', 'updated_at',
            # Enhanced properties
            'net_amount', 'effective_amount', 'processor_fee_percentage', 'net_percentage',
            'is_completed', 'is_refundable', 'is_tax_receipt_eligible', 'requires_receipt',
            'days_since_donation', 'is_recent', 'donor_name_display', 'donor_email_display',
            'has_complete_donor_info', 'formatted_amount', 'formatted_net_amount',
            'formatted_processor_fee', 'formatted_converted_amount', 'attribution_data',
            'financial_summary','d_type'
        ]
        read_only_fields = ['id', 'processed_by', 'created_at', 'updated_at']
    def get_d_type(self,obj):
        return 'one-time'
# ============================================================================
# RECURRING DONATION SERIALIZERS
# ============================================================================

class RecurringDonationListSerializer(serializers.ModelSerializer):
    """List serializer for recurring donations"""
    donor = UserBasicSerializer(read_only=True)
    donor_id = serializers.IntegerField(write_only=True)
    campaign = serializers.StringRelatedField(read_only=True)
    campaign_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    project = serializers.StringRelatedField(read_only=True)
    project_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    currency = CurrencySerializer(read_only=True)
    currency_id = serializers.IntegerField(write_only=True)
    
    # Enhanced properties
    formatted_amount = serializers.ReadOnlyField()
    total_donated = serializers.ReadOnlyField()
    formatted_total_donated = serializers.ReadOnlyField()
    success_rate = serializers.ReadOnlyField()
    is_healthy = serializers.ReadOnlyField()
    is_at_risk = serializers.ReadOnlyField()
    days_until_next_payment = serializers.ReadOnlyField()
    subscription_age_months = serializers.ReadOnlyField()
    
    class Meta:
        model = RecurringDonation
        fields = [
            'id', 'donor', 'donor_id', 'is_anonymous', 'campaign', 'campaign_id',
            'project', 'project_id', 'amount', 'currency', 'currency_id',
            'frequency', 'start_date', 'end_date', 'next_payment_date',
            'status', 'payment_count', 'failed_payment_count', 'created_at',
            # Enhanced properties
            'formatted_amount', 'total_donated', 'formatted_total_donated',
            'success_rate', 'is_healthy', 'is_at_risk', 'days_until_next_payment',
            'subscription_age_months'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

class RecurringDonationDetailSerializer(serializers.ModelSerializer):
    """Comprehensive detail serializer for recurring donations"""
    donor = UserBasicSerializer(read_only=True)
    donor_id = serializers.IntegerField(write_only=True)
    campaign = DonationCampaignListSerializer(read_only=True)
    campaign_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    project = ProjectMinimalSerializer(read_only=True)
    project_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    currency = CurrencySerializer(read_only=True)
    currency_id = serializers.IntegerField(write_only=True)
    
    # Financial calculations
    total_donated = serializers.ReadOnlyField()
    total_net_donated = serializers.ReadOnlyField()
    average_donation_amount = serializers.ReadOnlyField()
    projected_annual_amount = serializers.ReadOnlyField()
    lifetime_value = serializers.ReadOnlyField()
    
    # Status and health
    success_rate = serializers.ReadOnlyField()
    is_healthy = serializers.ReadOnlyField()
    is_at_risk = serializers.ReadOnlyField()
    days_until_next_payment = serializers.ReadOnlyField()
    is_payment_due = serializers.ReadOnlyField()
    is_overdue = serializers.ReadOnlyField()
    subscription_age_days = serializers.ReadOnlyField()
    subscription_age_months = serializers.ReadOnlyField()
    
    # Formatted properties
    formatted_amount = serializers.ReadOnlyField()
    formatted_total_donated = serializers.ReadOnlyField()
    formatted_projected_annual = serializers.ReadOnlyField()
    formatted_lifetime_value = serializers.ReadOnlyField()
    d_type=serializers.SerializerMethodField()
    
    # Comprehensive data
    performance_summary = serializers.ReadOnlyField()
    
    class Meta:
        model = RecurringDonation
        fields = [
            'id', 'donor', 'donor_id', 'is_anonymous', 'campaign', 'campaign_id',
            'project', 'project_id', 'amount', 'currency', 'currency_id',
            'frequency', 'start_date', 'end_date', 'next_payment_date',
            'last_payment_date', 'payment_method', 'subscription_id',
            'payment_processor', 'status', 'payment_count', 'failed_payment_count',
            'max_failed_payments', 'notes', 'receipt_image', 'created_at', 'updated_at',
            # Enhanced properties
            'total_donated', 'total_net_donated', 'average_donation_amount',
            'projected_annual_amount', 'lifetime_value', 'success_rate', 'is_healthy',
            'is_at_risk', 'days_until_next_payment', 'is_payment_due', 'is_overdue',
            'subscription_age_days', 'subscription_age_months', 'formatted_amount',
            'formatted_total_donated', 'formatted_projected_annual', 'formatted_lifetime_value',
            'performance_summary','d_type'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    def get_d_type(self,obj):
        return 'recurring'

# ============================================================================
# IN-KIND DONATION SERIALIZERS
# ============================================================================

class InKindDonationListSerializer(serializers.ModelSerializer):
    """List serializer for in-kind donations"""
    donor = UserBasicSerializer(read_only=True)
    donor_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    campaign = serializers.StringRelatedField(read_only=True)
    campaign_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    project = serializers.StringRelatedField(read_only=True)
    project_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    valuation_currency = CurrencySerializer(read_only=True)
    valuation_currency_id = serializers.IntegerField(write_only=True)
    
    # Enhanced properties
    donor_name_display = serializers.ReadOnlyField()
    formatted_estimated_value = serializers.ReadOnlyField()
    formatted_effective_value = serializers.ReadOnlyField()
    effective_value = serializers.ReadOnlyField()
    item_summary = serializers.ReadOnlyField()
    is_received = serializers.ReadOnlyField()
    is_overdue = serializers.ReadOnlyField()
    days_since_pledge = serializers.ReadOnlyField()
    
    class Meta:
        model = InKindDonation
        fields = [
            'id', 'donor', 'donor_id', 'is_anonymous', 'donor_name', 'donor_email',
            'campaign', 'campaign_id', 'project', 'project_id', 'item_description',
            'category', 'quantity', 'estimated_value', 'valuation_currency',
            'valuation_currency_id', 'donation_date', 'received_date', 'status',
            'created_at',
            # Enhanced properties
            'donor_name_display', 'formatted_estimated_value', 'formatted_effective_value',
            'effective_value', 'item_summary', 'is_received', 'is_overdue',
            'days_since_pledge'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

class InKindDonationDetailSerializer(serializers.ModelSerializer):
    """Comprehensive detail serializer for in-kind donations"""
    donor = UserBasicSerializer(read_only=True)
    donor_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    campaign = DonationCampaignListSerializer(read_only=True)
    campaign_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    project = ProjectMinimalSerializer(read_only=True)
    project_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    valuation_currency = CurrencySerializer(read_only=True)
    valuation_currency_id = serializers.IntegerField(write_only=True)
    received_by = UserBasicSerializer(read_only=True)
    
    # Valuation calculations
    total_estimated_value = serializers.ReadOnlyField()
    total_actual_value = serializers.ReadOnlyField()
    total_market_value = serializers.ReadOnlyField()
    value_variance = serializers.ReadOnlyField()
    value_variance_percentage = serializers.ReadOnlyField()
    effective_value = serializers.ReadOnlyField()
    
    # Status and validation
    is_received = serializers.ReadOnlyField()
    is_pending_receipt = serializers.ReadOnlyField()
    is_overdue = serializers.ReadOnlyField()
    days_since_pledge = serializers.ReadOnlyField()
    days_until_expected_delivery = serializers.ReadOnlyField()
    processing_time_days = serializers.ReadOnlyField()
    is_tax_receipt_eligible = serializers.ReadOnlyField()
    requires_receipt = serializers.ReadOnlyField()
    
    # Donor information
    donor_name_display = serializers.ReadOnlyField()
    donor_contact_display = serializers.ReadOnlyField()
    has_complete_donor_info = serializers.ReadOnlyField()
    
    # Formatted properties
    formatted_estimated_value = serializers.ReadOnlyField()
    formatted_actual_value = serializers.ReadOnlyField()
    formatted_effective_value = serializers.ReadOnlyField()
    formatted_market_value = serializers.ReadOnlyField()
    formatted_value_variance = serializers.ReadOnlyField()
    item_summary = serializers.ReadOnlyField()
    
    # Comprehensive data
    logistics_summary = serializers.ReadOnlyField()
    valuation_summary = serializers.ReadOnlyField()
    
    class Meta:
        model = InKindDonation
        fields = [
            'id', 'donor', 'donor_id', 'is_anonymous', 'donor_name', 'donor_email',
            'donor_phone', 'donor_organization', 'campaign', 'campaign_id', 'project',
            'project_id', 'item_description', 'category', 'brand_model', 'condition',
            'quantity', 'unit_of_measure', 'estimated_value', 'valuation_currency',
            'valuation_currency_id', 'valuation_method', 'market_value', 'donation_date',
            'pledge_date', 'expected_delivery_date', 'received_date', 'status',
            'pickup_required', 'delivery_address', 'special_handling_requirements',
            'storage_requirements', 'received_by', 'condition_on_receipt', 'actual_value',
            'receipt_sent', 'receipt_number', 'receipt_sent_date', 'tax_deductible',
            'receipt_image', 'photos', 'documentation', 'notes', 'internal_notes',
            'created_at', 'updated_at',
            # Enhanced properties
            'total_estimated_value', 'total_actual_value', 'total_market_value',
            'value_variance', 'value_variance_percentage', 'effective_value',
            'is_received', 'is_pending_receipt', 'is_overdue', 'days_since_pledge',
            'days_until_expected_delivery', 'processing_time_days', 'is_tax_receipt_eligible',
            'requires_receipt', 'donor_name_display', 'donor_contact_display',
            'has_complete_donor_info', 'formatted_estimated_value', 'formatted_actual_value',
            'formatted_effective_value', 'formatted_market_value', 'formatted_value_variance',
            'item_summary', 'logistics_summary', 'valuation_summary'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

# ============================================================================
# GRANT SERIALIZERS
# ============================================================================

class GrantListSerializer(serializers.ModelSerializer):
    """List serializer for grants"""
    currency = CurrencySerializer(read_only=True)
    currency_id = serializers.IntegerField(write_only=True)
    project = serializers.StringRelatedField(read_only=True)
    project_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    created_by = UserBasicSerializer(read_only=True)
    managed_by = UserBasicSerializer(read_only=True)
    
    # Enhanced properties
    remaining_amount = serializers.ReadOnlyField()
    formatted_amount = serializers.ReadOnlyField()
    
    # Basic counts
    reports_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Grant
        fields = [
            'id', 'title', 'grantor', 'grantor_type', 'amount', 'currency',
            'currency_id', 'amount_received', 'start_date', 'end_date',
            'project', 'project_id', 'status', 'created_by', 'managed_by',
            'created_at', 'updated_at',
            # Enhanced properties
            'remaining_amount', 'formatted_amount', 'reports_count'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']
    
    def get_reports_count(self, obj):
        return obj.reports.count()

class GrantDetailSerializer(serializers.ModelSerializer):
    """Comprehensive detail serializer for grants"""
    currency = CurrencySerializer(read_only=True)
    currency_id = serializers.IntegerField(write_only=True)
    project = ProjectMinimalSerializer(read_only=True)
    project_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    created_by = UserBasicSerializer(read_only=True)
    managed_by = UserBasicSerializer(read_only=True)
    managed_by_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    # Enhanced properties
    remaining_amount = serializers.ReadOnlyField()
    formatted_amount = serializers.ReadOnlyField()
    
    # Related data
    reports = serializers.SerializerMethodField()
    reports_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Grant
        fields = [
            'id', 'title', 'description', 'grantor', 'grantor_type', 'amount',
            'currency', 'currency_id', 'amount_received', 'submission_date',
            'approval_date', 'start_date', 'end_date', 'application_deadline',
            'project', 'project_id', 'status', 'requirements', 'reporting_frequency',
            'disbursement_schedule', 'contact_person', 'contact_email', 'contact_phone',
            'notes', 'created_by', 'managed_by', 'managed_by_id', 'created_at',
            'updated_at',
            # Enhanced properties
            'remaining_amount', 'formatted_amount', 'reports', 'reports_count'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']
    
    def get_reports(self, obj):
        """Get recent grant reports"""
        reports = obj.reports.order_by('-created_at')[:5]
        return GrantReportListSerializer(reports, many=True).data
    
    def get_reports_count(self, obj):
        return obj.reports.count()

# ============================================================================
# GRANT REPORT SERIALIZERS
# ============================================================================

class GrantReportListSerializer(serializers.ModelSerializer):
    """List serializer for grant reports"""
    grant = serializers.StringRelatedField(read_only=True)
    grant_id = serializers.IntegerField(write_only=True)
    submitted_by = UserBasicSerializer(read_only=True)
    
    class Meta:
        model = GrantReport
        fields = [
            'id', 'grant', 'grant_id', 'title', 'report_type', 'reporting_period_start',
            'reporting_period_end', 'due_date', 'submission_date', 'submitted_by',
            'status', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'submitted_by', 'created_at', 'updated_at']

class GrantReportDetailSerializer(serializers.ModelSerializer):
    """Comprehensive detail serializer for grant reports"""
    grant = GrantListSerializer(read_only=True)
    grant_id = serializers.IntegerField(write_only=True)
    submitted_by = UserBasicSerializer(read_only=True)
    
    class Meta:
        model = GrantReport
        fields = [
            'id', 'grant', 'grant_id', 'title', 'report_type', 'reporting_period_start',
            'reporting_period_end', 'due_date', 'submission_date', 'submitted_by',
            'status', 'narrative', 'financial_report', 'outcomes', 'challenges',
            'next_steps', 'feedback', 'attachments', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'submitted_by', 'created_at', 'updated_at']

# ============================================================================
# UTILITY SERIALIZERS FOR CURRENCY CONVERSION
# ============================================================================

class CurrencyConversionSerializer(serializers.Serializer):
    """Serializer for currency conversion requests"""
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    from_currency_id = serializers.IntegerField()
    to_currency_id = serializers.IntegerField()
    conversion_date = serializers.DateField(required=False)

class DonationStatsSerializer(serializers.Serializer):
    """Serializer for donation statistics"""
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_count = serializers.IntegerField()
    average_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency_code = serializers.CharField()
    period_start = serializers.DateField()
    period_end = serializers.DateField()

class GrantReportSerializer(serializers.ModelSerializer):
    grant = serializers.StringRelatedField(read_only=True)
    grant_id = serializers.IntegerField(write_only=True)
    submitted_by = UserBasicSerializer(read_only=True)
    
    class Meta:
        model = GrantReport
        fields = [
            'id', 'grant', 'grant_id', 'title', 'report_type', 'reporting_period_start',
            'reporting_period_end', 'due_date', 'submission_date', 'submitted_by',
            'status', 'narrative', 'financial_report', 'outcomes', 'challenges',
            'next_steps', 'feedback', 'attachments', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'submitted_by', 'created_at', 'updated_at']
class MiniBudgetFundingSerializer(serializers.ModelSerializer):
    class Meta:
        model = BudgetFunding
        fields = [
            'id', 'amount_allocated', 'allocation_date', 'notes'
        ]

class FundingSourceSerializer(serializers.ModelSerializer):
    currency = CurrencySerializer(read_only=True)
    currency_id = serializers.IntegerField(write_only=True)
    donation = DonationListSerializer(read_only=True)
    donation_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    campaign = DonationCampaignListSerializer(read_only=True)
    campaign_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    grant = GrantListSerializer(read_only=True)
    grant_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    created_by = UserBasicSerializer(read_only=True)
    amount_remaining = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    formatted_amount = serializers.CharField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    is_available_now = serializers.BooleanField(read_only=True)
    allocations=MiniBudgetFundingSerializer(read_only=True,many=True)
    
    class Meta:
        model = FundingSource
        fields = [
            'id', 'name', 'funding_type', 'description', 'donation', 'donation_id', 'campaign',
            'campaign_id', 'grant', 'grant_id', 'amount_available', 'currency',
            'currency_id', 'amount_allocated', 'available_from', 'available_until', 
            'restrictions', 'is_active', 'created_by', 'created_at', 'updated_at',
            'amount_remaining', 'formatted_amount', 'is_expired', 'is_available_now',
            'allocations'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

class MinimalBudgetSerializer(serializers.ModelSerializer): 
    """Minimal budget info for dropdowns and simple listings"""
    remaining_amount=serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    currency=CurrencySerializer(read_only=True)
    
    
    class Meta:
        model = Budget
        fields = ['id', 'title','remaining_amount', 'total_amount', 'currency', 'start_date', 'end_date']
        read_only_fields = ['id', 'remaining_amount','title', 'total_amount', 'currency', 'start_date', 'end_date']

class BudgetItemSerializer(serializers.ModelSerializer):
    budget = MinimalBudgetSerializer(read_only=True)
    responsible_person = UserBasicSerializer(read_only=True)
    responsible_person_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    remaining_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    spent_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    formatted_amount = serializers.CharField(read_only=True)
    budget_id=serializers.IntegerField(write_only=True)
    
    class Meta:
        model = BudgetItem
        fields = [
            'id', 'budget', 'category', 'subcategory', 'description', 'budgeted_amount',
            'spent_amount', 'is_locked', 'approval_required_threshold', 'responsible_person',
            'responsible_person_id', 'notes', 'created_at', 'updated_at',
            'remaining_amount', 'spent_percentage', 'formatted_amount', 'budget_id'
        ]
        read_only_fields = ['id', 'budget', 'created_at', 'updated_at']



class OrganizationalExpenseMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for organizational expenses in budget detail"""
    formatted_amount = serializers.CharField(read_only=True)
    submitted_by = UserBasicSerializer(read_only=True)
    approved_by = UserBasicSerializer(read_only=True)
    
    class Meta:
        model = OrganizationalExpense
        fields = [
            'id', 'title', 'description', 'expense_type', 'amount', 
            'currency', 'expense_date', 'vendor', 'status', 
            'formatted_amount', 'submitted_by', 'approved_by', 'approved_at'
        ]

class BudgetItemDetailSerializer(serializers.ModelSerializer):
    """Enhanced budget item serializer for detail view with comprehensive financial data"""
    
    # Core amounts
    spent_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    pending_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    committed_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    approved_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    rejected_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_requested_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    
    # Budget calculations
    remaining_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    available_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    encumbered_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    truly_available_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    
    # Percentages
    spent_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    committed_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    utilization_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    
    # Variance
    variance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    variance_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    committed_variance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    
    # Status and control
    utilization_status = serializers.CharField(read_only=True)
    budget_health = serializers.CharField(read_only=True)
    is_over_budget = serializers.BooleanField(read_only=True)
    is_overcommitted = serializers.BooleanField(read_only=True)
    has_pending_requests = serializers.BooleanField(read_only=True)
    can_spend = serializers.BooleanField(read_only=True)
    requires_approval_for_remaining = serializers.BooleanField(read_only=True)
    available_without_approval = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    
    # Formatted amounts
    formatted_amount = serializers.CharField(read_only=True)
    formatted_spent_amount = serializers.CharField(read_only=True)
    formatted_remaining_amount = serializers.CharField(read_only=True)
    formatted_committed_amount = serializers.CharField(read_only=True)
    formatted_pending_amount = serializers.CharField(read_only=True)
    formatted_available_amount = serializers.CharField(read_only=True)
    
    # Counts
    total_expenses_count = serializers.IntegerField(read_only=True)
    paid_expenses_count = serializers.IntegerField(read_only=True)
    pending_expenses_count = serializers.IntegerField(read_only=True)
    approved_expenses_count = serializers.IntegerField(read_only=True)
    
    # Related objects
    responsible_person = UserBasicSerializer(read_only=True)
    organizational_expenses = OrganizationalExpenseMinimalSerializer(many=True, read_only=True)
    budget = MinimalBudgetSerializer(read_only=True)
    
    class Meta:
        model = BudgetItem
        fields = [
            # Basic fields
            'id', 'category', 'subcategory', 'description', 'budgeted_amount',
            'is_locked', 'approval_required_threshold', 'responsible_person',
            'notes', 'created_at', 'updated_at', 'budget',
            
            # Core amounts
            'spent_amount', 'pending_amount', 'committed_amount', 'approved_amount',
            'rejected_amount', 'total_requested_amount',
            
            # Budget calculations
            'remaining_amount', 'available_amount', 'encumbered_amount', 'truly_available_amount',
            
            # Percentages
            'spent_percentage', 'committed_percentage', 'utilization_percentage',
            
            # Variance
            'variance', 'variance_percentage', 'committed_variance',
            
            # Status and control
            'utilization_status', 'budget_health', 'is_over_budget', 'is_overcommitted',
            'has_pending_requests', 'can_spend', 'requires_approval_for_remaining',
            'available_without_approval',
            
            # Formatted amounts
            'formatted_amount', 'formatted_spent_amount', 'formatted_remaining_amount',
            'formatted_committed_amount', 'formatted_pending_amount', 'formatted_available_amount',
            
            # Counts
            'total_expenses_count', 'paid_expenses_count', 'pending_expenses_count',
            'approved_expenses_count',
            
            # Related objects
            'organizational_expenses',
        ]

class BudgetFundingSerializer(serializers.ModelSerializer):
    funding_source = FundingSourceSerializer(read_only=True)
    funding_source_id = serializers.IntegerField(write_only=True)
    budget_id=serializers.IntegerField(write_only=True)
    
    class Meta:
        model = BudgetFunding
        fields = [
            'id', 'funding_source', 'funding_source_id', 'amount_allocated',
            'allocation_date', 'notes','budget_id'
        ]
        read_only_fields = ['id', 'allocation_date']

class DepartmentSerializer(serializers.ModelSerializer):
    """Serializer for Department model"""
    class Meta:
        model = Department
        fields = ['id', 'name', 'description', 'created_at',]
        read_only_fields = ['id', 'created_at', ]

class FundingSourceMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for funding sources"""
    currency = CurrencySerializer(read_only=True)
    formatted_amount = serializers.CharField(read_only=True)
    amount_remaining = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    is_available_now = serializers.BooleanField(read_only=True)
    created_by = UserBasicSerializer(read_only=True)
    
    class Meta:
        model = FundingSource
        fields = [
            'id', 'name', 'funding_type', 'description', 'amount_available',
            'currency', 'amount_allocated', 'amount_remaining', 'formatted_amount',
            'available_from', 'available_until', 'restrictions', 'is_active',
            'is_available_now', 'created_by'
        ]

class BudgetFundingDetailSerializer(serializers.ModelSerializer):
    """Enhanced budget funding serializer for detail view"""
    funding_source = FundingSourceMinimalSerializer(read_only=True)
    
    class Meta:
        model = BudgetFunding
        fields = [
            'id', 'funding_source', 'amount_allocated', 'allocation_date', 'notes'
        ]

class BudgetSerializer(serializers.ModelSerializer):
    project = ProjectMinimalSerializer(read_only=True)
    project_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    department = DepartmentSerializer(read_only=True)
    department_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    currency = CurrencySerializer(read_only=True)
    currency_id = serializers.IntegerField(write_only=True)
    created_by = UserBasicSerializer(read_only=True)
    approved_by = UserBasicSerializer(read_only=True)
    approved_by_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    remaining_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    spent_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    formatted_amount = serializers.CharField(read_only=True)
    total_funding_allocated = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    items = BudgetItemSerializer(many=True, read_only=True)
    budget_funding = BudgetFundingSerializer(many=True, read_only=True)
    funding_breakdown = serializers.SerializerMethodField()
    
    class Meta:
        model = Budget
        fields = [
            'id', 'title', 'budget_type', 'project', 'project_id', 'department',
            'department_id', 'total_amount', 'currency', 'currency_id', 'spent_amount',
            'fiscal_year', 'start_date', 'end_date', 'status', 'notes', 'created_by',
            'approved_by', 'approved_by_id', 'approved_at', 'created_at', 'updated_at',
            'remaining_amount', 'spent_percentage', 'formatted_amount',
            'total_funding_allocated', 'items', 'budget_funding', 'funding_breakdown'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']
    
    def get_funding_breakdown(self, obj):
        return obj.get_funding_breakdown()

class FundAllocationDetailSerializer(serializers.ModelSerializer):
    """Enhanced fund allocation serializer for detail view"""
    source_account = BankAccountMinimalSerializer(read_only=True)
    allocated_by = UserBasicSerializer(read_only=True)
    approved_by = UserBasicSerializer(read_only=True)
    formatted_amount = serializers.CharField(read_only=True)
    
    class Meta:
        model = FundAllocation
        fields = [
            'id', 'source_account', 'amount_allocated', 'formatted_amount',
            'allocation_date', 'purpose', 'allocated_by', 'approved_by',
            'is_active', 'created_at'
        ]
class BudgetDetailSerializer(serializers.ModelSerializer):
    """Enhanced Budget serializer with comprehensive financial tracking including fund allocations"""
    
    # Basic relationships
    project = ProjectMinimalSerializer(read_only=True)
    project_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    department = DepartmentSerializer(read_only=True)
    department_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    currency = CurrencySerializer(read_only=True)
    currency_id = serializers.IntegerField(write_only=True)
    created_by = UserBasicSerializer(read_only=True)
    approved_by = UserBasicSerializer(read_only=True)
    approved_by_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    # ============================================================================
    # CORE AMOUNT CALCULATIONS
    # ============================================================================
    spent_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    pending_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    committed_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    approved_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    rejected_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_requested_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    
    # ============================================================================
    # BUDGET ALLOCATION CALCULATIONS
    # ============================================================================
    allocated_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    unallocated_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    remaining_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    available_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    encumbered_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    truly_available_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    
    # ============================================================================
    # PERCENTAGE CALCULATIONS
    # ============================================================================
    spent_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    committed_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    utilization_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    allocation_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    
    # ============================================================================
    # VARIANCE CALCULATIONS
    # ============================================================================
    variance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    variance_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    committed_variance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    allocation_variance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    
    # ============================================================================
    # FUNDING CALCULATIONS (ORIGINAL)
    # ============================================================================
    total_funding_allocated = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    funding_gap = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    funding_surplus = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    funding_utilization_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    
    # ============================================================================
    # FUND ALLOCATION CALCULATIONS (NEW)
    # ============================================================================
    total_fund_allocations = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    active_fund_allocations = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    allocation_gap = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    allocation_surplus = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    allocation_coverage_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    funding_realization_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    allocation_utilization_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    available_from_allocations = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    truly_available_from_allocations = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    
    # ============================================================================
    # STATUS AND HEALTH
    # ============================================================================
    budget_health = serializers.CharField(read_only=True)
    utilization_status = serializers.CharField(read_only=True)
    funding_status = serializers.CharField(read_only=True)
    allocation_status = serializers.CharField(read_only=True)
    comprehensive_funding_status = serializers.CharField(read_only=True)
    
    # ============================================================================
    # BOOLEAN STATUS CHECKS
    # ============================================================================
    is_over_budget = serializers.BooleanField(read_only=True)
    is_overcommitted = serializers.BooleanField(read_only=True)
    is_fully_allocated = serializers.BooleanField(read_only=True)
    is_fully_funded = serializers.BooleanField(read_only=True)
    is_fully_allocated_from_accounts = serializers.BooleanField(read_only=True)
    has_pending_requests = serializers.BooleanField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    is_active_period = serializers.BooleanField(read_only=True)
    can_allocate_more = serializers.BooleanField(read_only=True)
    is_locked_for_allocation = serializers.BooleanField(read_only=True)
    
    # ============================================================================
    # TIME-BASED CALCULATIONS
    # ============================================================================
    days_remaining = serializers.IntegerField(read_only=True)
    days_elapsed = serializers.IntegerField(read_only=True)
    total_budget_days = serializers.IntegerField(read_only=True)
    progress_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    burn_rate = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    projected_total_spend = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    projected_variance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    
    # ============================================================================
    # EFFICIENCY METRICS
    # ============================================================================
    spending_efficiency = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    allocation_efficiency = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    funding_efficiency = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    
    # ============================================================================
    # ITEM-LEVEL AGGREGATIONS
    # ============================================================================
    total_budget_items_count = serializers.IntegerField(read_only=True)
    active_budget_items_count = serializers.IntegerField(read_only=True)
    over_budget_items_count = serializers.IntegerField(read_only=True)
    critical_items_count = serializers.IntegerField(read_only=True)
    
    # ============================================================================
    # FORMATTING PROPERTIES
    # ============================================================================
    formatted_amount = serializers.CharField(read_only=True)
    formatted_spent_amount = serializers.CharField(read_only=True)
    formatted_committed_amount = serializers.CharField(read_only=True)
    formatted_pending_amount = serializers.CharField(read_only=True)
    formatted_remaining_amount = serializers.CharField(read_only=True)
    formatted_available_amount = serializers.CharField(read_only=True)
    formatted_variance = serializers.CharField(read_only=True)
    formatted_funding_gap = serializers.CharField(read_only=True)
    formatted_allocation_gap = serializers.CharField(read_only=True)
    formatted_total_fund_allocations = serializers.CharField(read_only=True)
    formatted_available_from_allocations = serializers.CharField(read_only=True)
    
    # ============================================================================
    # COMPREHENSIVE SUMMARIES
    # ============================================================================
    financial_summary = serializers.SerializerMethodField()
    performance_metrics = serializers.SerializerMethodField()
    status_summary = serializers.SerializerMethodField()
    allocation_summary = serializers.SerializerMethodField()
    enhanced_financial_summary = serializers.SerializerMethodField()
    funding_vs_allocation_analysis = serializers.SerializerMethodField()
    
    # ============================================================================
    # ENHANCED RELATIONSHIPS
    # ============================================================================
    items = BudgetItemDetailSerializer(many=True, read_only=True)
    budget_funding = BudgetFundingDetailSerializer(many=True, read_only=True)
    fund_allocations = FundAllocationDetailSerializer(many=True, read_only=True)
    
    # ============================================================================
    # DETAILED ANALYSIS METHODS
    # ============================================================================
    funding_breakdown = serializers.SerializerMethodField()
    fund_allocations_breakdown = serializers.SerializerMethodField()
    expense_summary = serializers.SerializerMethodField()
    category_breakdown = serializers.SerializerMethodField()
    monthly_spending_trend = serializers.SerializerMethodField()
    budget_utilization_by_item = serializers.SerializerMethodField()
    funding_vs_spending_analysis = serializers.SerializerMethodField()
    allocation_utilization_analysis = serializers.SerializerMethodField()
    funding_vs_allocation_timeline = serializers.SerializerMethodField()
    budget_alerts = serializers.SerializerMethodField()
    recent_expenses = serializers.SerializerMethodField()
    funding_sources_summary = serializers.SerializerMethodField()
    
    # ============================================================================
    # STATISTICS
    # ============================================================================
    items_count = serializers.SerializerMethodField()
    expenses_count = serializers.SerializerMethodField()
    funding_sources_count = serializers.SerializerMethodField()
    allocations_count = serializers.SerializerMethodField()
    active_allocations_count = serializers.SerializerMethodField()
    paid_expenses_count = serializers.SerializerMethodField()
    pending_expenses_count = serializers.SerializerMethodField()
    approved_expenses_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Budget
        fields = [
            # Basic fields
            'id', 'title', 'budget_type', 'project', 'project_id', 'department',
            'department_id', 'total_amount', 'currency', 'currency_id',
            'fiscal_year', 'start_date', 'end_date', 'status', 'notes', 'created_by',
            'approved_by', 'approved_by_id', 'approved_at', 'created_at', 'updated_at',
            
            # Core amount calculations
            'spent_amount', 'pending_amount', 'committed_amount', 'approved_amount',
            'rejected_amount', 'total_requested_amount',
            
            # Budget allocation calculations
            'allocated_amount', 'unallocated_amount', 'remaining_amount', 'available_amount',
            'encumbered_amount', 'truly_available_amount',
            
            # Percentage calculations
            'spent_percentage', 'committed_percentage', 'utilization_percentage', 'allocation_percentage',
            
            # Variance calculations
            'variance', 'variance_percentage', 'committed_variance', 'allocation_variance',
            
            # Funding calculations (original)
            'total_funding_allocated', 'funding_gap', 'funding_surplus', 'funding_utilization_percentage',
            
            # Fund allocation calculations (new)
            'total_fund_allocations', 'active_fund_allocations', 'allocation_gap', 'allocation_surplus',
            'allocation_coverage_percentage', 'funding_realization_percentage', 'allocation_utilization_percentage',
            'available_from_allocations', 'truly_available_from_allocations',
            
            # Status and health
            'budget_health', 'utilization_status', 'funding_status', 'allocation_status', 'comprehensive_funding_status',
            
            # Boolean status checks
            'is_over_budget', 'is_overcommitted', 'is_fully_allocated', 'is_fully_funded', 'is_fully_allocated_from_accounts',
            'has_pending_requests', 'is_expired', 'is_active_period', 'can_allocate_more', 'is_locked_for_allocation',
            
            # Time-based calculations
            'days_remaining', 'days_elapsed', 'total_budget_days', 'progress_percentage',
            'burn_rate', 'projected_total_spend', 'projected_variance',
            
            # Efficiency metrics
            'spending_efficiency', 'allocation_efficiency', 'funding_efficiency',
            
            # Item-level aggregations
            'total_budget_items_count', 'active_budget_items_count', 'over_budget_items_count',
            'critical_items_count',
            
            # Formatting properties
            'formatted_amount', 'formatted_spent_amount', 'formatted_committed_amount',
            'formatted_pending_amount', 'formatted_remaining_amount', 'formatted_available_amount',
            'formatted_variance', 'formatted_funding_gap', 'formatted_allocation_gap',
            'formatted_total_fund_allocations', 'formatted_available_from_allocations',
            
            # Comprehensive summaries
            'financial_summary', 'performance_metrics', 'status_summary', 'allocation_summary',
            'enhanced_financial_summary', 'funding_vs_allocation_analysis',
            
            # Relationships
            'items', 'budget_funding', 'fund_allocations',
            
            # Detailed analysis
            'funding_breakdown', 'fund_allocations_breakdown', 'expense_summary', 'category_breakdown', 
            'monthly_spending_trend', 'budget_utilization_by_item', 'funding_vs_spending_analysis',
            'allocation_utilization_analysis', 'funding_vs_allocation_timeline', 'budget_alerts',
            'recent_expenses', 'funding_sources_summary',
            
            # Statistics
            'items_count', 'expenses_count', 'funding_sources_count', 'allocations_count',
            'active_allocations_count', 'paid_expenses_count', 'pending_expenses_count', 'approved_expenses_count'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']
    
    # ============================================================================
    # COMPREHENSIVE SUMMARY METHODS
    # ============================================================================
    
    def get_financial_summary(self, obj):
        """Get comprehensive financial summary"""
        return obj.financial_summary
    
    def get_enhanced_financial_summary(self, obj):
        """Get enhanced financial summary including allocations"""
        return obj.enhanced_financial_summary
    
    def get_performance_metrics(self, obj):
        """Get performance and efficiency metrics"""
        return obj.performance_metrics
    
    def get_status_summary(self, obj):
        """Get status and health summary"""
        return obj.status_summary
    
    def get_allocation_summary(self, obj):
        """Get allocation summary"""
        return obj.allocation_summary
    
    def get_funding_vs_allocation_analysis(self, obj):
        """Get funding vs allocation analysis"""
        return obj.funding_vs_allocation_analysis
    
    # ============================================================================
    # DETAILED ANALYSIS METHODS
    # ============================================================================
    
    def get_funding_breakdown(self, obj):
        """Get detailed funding breakdown"""
        return obj.get_funding_breakdown()
    
    def get_fund_allocations_breakdown(self, obj):
        """Get detailed fund allocations breakdown"""
        return obj.get_fund_allocations_breakdown()
    
    def get_allocation_utilization_analysis(self, obj):
        """Get allocation utilization analysis"""
        return obj.get_allocation_utilization_analysis()
    
    def get_funding_vs_allocation_timeline(self, obj):
        """Get funding vs allocation timeline"""
        return obj.get_funding_vs_allocation_timeline()
    
    def get_category_breakdown(self, obj):
        """Get spending breakdown by category"""
        return obj.get_spending_by_category()
    
    def get_monthly_spending_trend(self, obj):
        """Get monthly spending trend"""
        return obj.get_monthly_spending_trend()
    
    def get_budget_utilization_by_item(self, obj):
        """Get utilization by budget item"""
        return obj.get_budget_utilization_by_item()
    
    def get_funding_vs_spending_analysis(self, obj):
        """Get funding vs spending analysis"""
        return obj.get_funding_vs_spending_analysis()
    
    def get_budget_alerts(self, obj):
        """Get budget alerts and warnings"""
        return obj.get_budget_alerts()
    
    def get_expense_summary(self, obj):
        """Get enhanced expense summary by type and status"""
        from django.db.models import Sum, Count
        
        # Summary by expense type
        type_summary = OrganizationalExpense.objects.filter(
            budget_item__budget=obj
        ).values('expense_type', 'status').annotate(
            total_amount=Sum('amount'),
            count=Count('id')
        ).order_by('expense_type', 'status')
        
        # Group by expense type
        expense_types = {}
        for exp in type_summary:
            exp_type = exp['expense_type']
            if exp_type not in expense_types:
                expense_types[exp_type] = {
                    'expense_type': exp_type,
                    'expense_type_display': dict(OrganizationalExpense.EXPENSE_TYPE_CHOICES).get(exp_type, exp_type),
                    'total_amount': 0,
                    'total_count': 0,
                    'by_status': {}
                }
            
            status = exp['status']
            amount = float(exp['total_amount']) if exp['total_amount'] else 0.0
            count = exp['count']
            
            expense_types[exp_type]['total_amount'] += amount
            expense_types[exp_type]['total_count'] += count
            expense_types[exp_type]['by_status'][status] = {
                'amount': amount,
                'count': count,
                'formatted_amount': f"{obj.currency.code} {amount:,.2f}" if obj.currency else f"{amount:,.2f}"
            }
        
        # Format final results
        result = []
        for exp_type, data in expense_types.items():
            data['formatted_total_amount'] = f"{obj.currency.code} {data['total_amount']:,.2f}" if obj.currency else f"{data['total_amount']:,.2f}"
            result.append(data)
        
        return sorted(result, key=lambda x: x['total_amount'], reverse=True)
    
    def get_recent_expenses(self, obj):
        """Get recent expenses with enhanced details"""
        recent_expenses = OrganizationalExpense.objects.filter(
            budget_item__budget=obj
        ).select_related(
            'budget_item', 'currency', 'submitted_by', 'approved_by'
        ).order_by('-expense_date', '-created_at')[:15]
        
        return OrganizationalExpenseMinimalSerializer(recent_expenses, many=True).data
    
    def get_funding_sources_summary(self, obj):
        """Get enhanced funding sources summary"""
        funding_sources = []
        total_funding = obj.total_funding_allocated
        
        for budget_funding in obj.budget_funding.select_related('funding_source', 'funding_source__currency'):
            source = budget_funding.funding_source
            amount = float(budget_funding.amount_allocated)
            percentage = (amount / float(total_funding)) * 100 if total_funding > 0 else 0
            
            funding_sources.append({
                'id': source.id,
                'name': source.name,
                'funding_type': source.funding_type,
                'funding_type_display': source.get_funding_type_display(),
                'amount_allocated': amount,
                'percentage': round(percentage, 2),
                'currency_code': source.currency.code if source.currency else None,
                'formatted_amount': f"{source.currency.code} {budget_funding.amount_allocated:,.2f}" if source.currency else f"{budget_funding.amount_allocated:,.2f}",
                'is_active': source.is_active,
                'allocation_date': budget_funding.allocation_date.isoformat() if budget_funding.allocation_date else None,
                'notes': budget_funding.notes or ''
            })
        
        return sorted(funding_sources, key=lambda x: x['amount_allocated'], reverse=True)
    
    # ============================================================================
    # STATISTICS METHODS
    # ============================================================================
    
    def get_items_count(self, obj):
        return obj.total_budget_items_count
    
    def get_expenses_count(self, obj):
        return OrganizationalExpense.objects.filter(budget_item__budget=obj).count()
    
    def get_paid_expenses_count(self, obj):
        return OrganizationalExpense.objects.filter(budget_item__budget=obj, status='paid').count()
    
    def get_pending_expenses_count(self, obj):
        return OrganizationalExpense.objects.filter(budget_item__budget=obj, status__in=['pending', 'draft']).count()
    
    def get_approved_expenses_count(self, obj):
        return OrganizationalExpense.objects.filter(budget_item__budget=obj, status='approved').count()
    
    def get_funding_sources_count(self, obj):
        return obj.budget_funding.count()
    
    def get_allocations_count(self, obj):
        return obj.fund_allocations.count()
    
    def get_active_allocations_count(self, obj):
        return obj.fund_allocations.filter(is_active=True).count()



class OrganizationalExpenseSerializer(serializers.ModelSerializer):
    budget_item = BudgetItemSerializer
    budget_item_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    currency = CurrencySerializer(read_only=True)
    submitted_by = UserBasicSerializer(read_only=True)
    approved_by = UserBasicSerializer(read_only=True)
    approved_by_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    formatted_amount = serializers.CharField(read_only=True)
    
    class Meta:
        model = OrganizationalExpense
        fields = [
            'id', 'budget_item', 'budget_item_id', 'title', 'description',
            'expense_type', 'amount', 'currency', 'expense_date',
            'vendor', 'receipt', 'status', 'submitted_by', 'approved_by',
            'approved_by_id', 'approved_at', 'notes', 'created_at', 'updated_at',
            'formatted_amount'
        ]
        read_only_fields = ['id', 'submitted_by', 'created_at', 'updated_at']

class AccountTransactionSerializer(serializers.ModelSerializer):
    account = BankAccountMinimalSerializer(read_only=True)
    account_id = serializers.IntegerField(write_only=True)
    original_currency = CurrencySerializer(read_only=True)
    original_currency_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    donation = serializers.StringRelatedField(read_only=True)
    donation_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    grant = serializers.StringRelatedField(read_only=True)
    grant_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    expense = serializers.StringRelatedField(read_only=True)
    expense_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    transfer_to_account = serializers.StringRelatedField(read_only=True)
    transfer_to_account_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    authorized_by = UserBasicSerializer(read_only=True)
    reconciled_by = UserBasicSerializer(read_only=True)
    reconciled_by_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    formatted_amount = serializers.CharField(read_only=True)
    
    class Meta:
        model = AccountTransaction
        fields = [
            'id', 'account', 'account_id', 'transaction_type', 'amount',
            'original_amount', 'original_currency', 'original_currency_id',
            'exchange_rate_used', 'donation', 'donation_id', 'grant', 'grant_id',
            'expense', 'expense_id', 'transfer_to_account', 'transfer_to_account_id',
            'reference_number', 'bank_reference', 'transaction_date', 'description',
            'status', 'processor_fee', 'net_amount', 'authorized_by',
            'is_reconciled', 'reconciled_date', 'reconciled_by', 'reconciled_by_id',
            'created_at', 'updated_at', 'formatted_amount'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

class FundAllocationSerializer(serializers.ModelSerializer):
    source_account = serializers.StringRelatedField(read_only=True)
    source_account_id = serializers.IntegerField(write_only=True)
    budget = serializers.StringRelatedField(read_only=True)
    budget_id = serializers.IntegerField(write_only=True)
    allocated_by = UserBasicSerializer(read_only=True)
    approved_by = UserBasicSerializer(read_only=True)
    formatted_amount = serializers.CharField(read_only=True)
    

    class Meta:
        model = FundAllocation
        fields = [
            'id', 'source_account', 'source_account_id', 'budget', 'budget_id',
            'amount_allocated', 'allocation_date', 'purpose', 'allocated_by',
            'approved_by', 'is_active', 'created_at',
            'formatted_amount'
        ]
        read_only_fields = ['id', 'allocated_by', 'created_at']

# Statistical Serializers for Dashboard
class FinancialSummarySerializer(serializers.Serializer):
    total_donations = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_grants = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_expenses = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_budget_allocated = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_account_balance = serializers.DecimalField(max_digits=15, decimal_places=2)
    active_campaigns_count = serializers.IntegerField()
    active_grants_count = serializers.IntegerField()
    pending_expenses_count = serializers.IntegerField()

class DonationStatsSerializer(serializers.Serializer):
    period = serializers.CharField()
    total_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    donation_count = serializers.IntegerField()
    average_donation = serializers.DecimalField(max_digits=10, decimal_places=2)
    unique_donors = serializers.IntegerField()

class CampaignPerformanceSerializer(serializers.Serializer):
    campaign_id = serializers.IntegerField()
    campaign_title = serializers.CharField()
    target_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    raised_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    progress_percentage = serializers.DecimalField(max_digits=5, decimal_places=2)
    donors_count = serializers.IntegerField()
    days_remaining = serializers.IntegerField()

class BudgetUtilizationSerializer(serializers.Serializer):
    budget_id = serializers.IntegerField()
    budget_title = serializers.CharField()
    budget_type = serializers.CharField()
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    spent_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    remaining_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    utilization_percentage = serializers.DecimalField(max_digits=5, decimal_places=2)
    currency_code = serializers.CharField()



class PaymentStatusUpdateSerializer(serializers.Serializer):
    """Serializer for payment status updates"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]
    
    status = serializers.ChoiceField(choices=STATUS_CHOICES)
    transaction_data = serializers.JSONField(required=False, default=dict)
    
    def validate_transaction_data(self, value):
        """Validate transaction data structure"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Transaction data must be a dictionary")
        
        # Optional: Add specific validation for expected fields
        allowed_fields = [
            'flutterwave_ref', 'transaction_id', 'tx_ref', 'amount', 
            'currency', 'payment_method', 'processed_at', 'error_message', 
            'failed_at'
        ]
        
        # You can add validation logic here if needed
        return value