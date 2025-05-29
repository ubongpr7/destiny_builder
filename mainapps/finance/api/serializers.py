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
        extra_kwargs = {
            'api_key': {'write_only': True},
        }
    
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

class DonationSerializer(serializers.ModelSerializer):
    donor = UserBasicSerializer(read_only=True)
    donor_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    campaign = serializers.StringRelatedField(read_only=True)
    campaign_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    project = serializers.StringRelatedField(read_only=True)
    project_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    currency = CurrencySerializer(read_only=True)
    currency_id = serializers.IntegerField(write_only=True)
    converted_currency = CurrencySerializer(read_only=True)
    converted_currency_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    processor_fee_currency = CurrencySerializer(read_only=True)
    processor_fee_currency_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    deposited_to_account = serializers.StringRelatedField(read_only=True)
    deposited_to_account_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    processed_by = UserBasicSerializer(read_only=True)
    donor_name_display = serializers.CharField(read_only=True)
    formatted_amount = serializers.CharField(read_only=True)
    
    class Meta:
        model = Donation
        fields = [
            'id', 'donor', 'donor_id', 'is_anonymous', 'donor_name', 'donor_email',
            'campaign', 'campaign_id', 'project', 'project_id', 'amount', 'currency',
            'currency_id', 'exchange_rate', 'converted_amount', 'converted_currency',
            'converted_currency_id', 'donation_date', 'payment_method', 'transaction_id',
            'reference_number', 'status', 'processor_fee', 'processor_fee_currency',
            'processor_fee_currency_id', 'net_amount', 'deposited_to_account',
            'deposited_to_account_id', 'deposit_date', 'bank_reference', 'receipt_image',
            'notes', 'receipt_sent', 'receipt_number', 'tax_deductible', 'processed_by',
            'created_at', 'updated_at', 'donor_name_display', 'formatted_amount'
        ]
        read_only_fields = ['id', 'processed_by', 'created_at', 'updated_at']

class RecurringDonationSerializer(serializers.ModelSerializer):
    donor = UserBasicSerializer(read_only=True)
    donor_id = serializers.IntegerField(write_only=True)
    campaign = serializers.StringRelatedField(read_only=True)
    campaign_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    project = serializers.StringRelatedField(read_only=True)
    project_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    currency = CurrencySerializer(read_only=True)
    currency_id = serializers.IntegerField(write_only=True)
    formatted_amount = serializers.CharField(read_only=True)
    
    class Meta:
        model = RecurringDonation
        fields = [
            'id', 'donor', 'donor_id', 'is_anonymous', 'campaign', 'campaign_id', 'project',
            'project_id', 'amount', 'currency', 'currency_id', 'frequency',
            'start_date', 'end_date', 'next_payment_date', 'payment_method',
            'subscription_id', 'status', 'total_donated', 'payment_count',
            'notes', 'receipt_image', 'created_at', 'updated_at', 'formatted_amount'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

class InKindDonationSerializer(serializers.ModelSerializer):
    donor = UserBasicSerializer(read_only=True)
    donor_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    campaign = serializers.StringRelatedField(read_only=True)
    campaign_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    project = serializers.StringRelatedField(read_only=True)
    project_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    valuation_currency = CurrencySerializer(read_only=True)
    valuation_currency_id = serializers.IntegerField(write_only=True)
    received_by = UserBasicSerializer(read_only=True)
    received_by_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    donor_name_display = serializers.CharField(read_only=True)
    formatted_value = serializers.CharField(read_only=True)
    
    class Meta:
        model = InKindDonation
        fields = [
            'id', 'donor', 'donor_id', 'is_anonymous', 'donor_name', 'donor_email',
            'campaign', 'campaign_id', 'project', 'project_id', 'item_description',
            'category', 'quantity', 'estimated_value', 'valuation_currency',
            'valuation_currency_id', 'donation_date', 'received_date', 'received_by',
            'received_by_id', 'status', 'notes', 'receipt_sent', 'receipt_number',
            'receipt_image', 'created_at', 'updated_at', 'donor_name_display', 'formatted_value'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

class DonationCampaignSerializer(serializers.ModelSerializer):
    target_currency = CurrencySerializer(read_only=True)
    target_currency_id = serializers.IntegerField(write_only=True)
    project = ProjectMinimalSerializer(read_only=True)
    project_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    created_by = UserBasicSerializer(read_only=True)
    current_amount_in_target_currency = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    progress_percentage = serializers.DecimalField(
        max_digits=5, decimal_places=2, read_only=True
    )
    is_completed = serializers.BooleanField(read_only=True)
    donations_count = serializers.SerializerMethodField()
    donors_count = serializers.SerializerMethodField()
    
    class Meta:
        model = DonationCampaign
        fields = [
            'id', 'title', 'description', 'target_amount', 'target_currency',
            'target_currency_id', 'start_date', 'end_date', 'project', 'project_id',
            'is_active', 'is_featured', 'image', 'created_by', 'created_at',
            'updated_at', 'current_amount_in_target_currency', 'progress_percentage',
            'is_completed', 'donations_count', 'donors_count'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']
    
    def get_donations_count(self, obj):
        return obj.donations.filter(status='completed').count()
    
    def get_donors_count(self, obj):
        """Get unique donors across all donation types"""
        regular_donors = set(obj.donations.filter(status='completed').values_list('donor', flat=True))
        recurring_donors = set(obj.recurring_donations.filter(status__in=['active', 'completed']).values_list('donor', flat=True))
        in_kind_donors = set(obj.in_kind_donations.filter(status='received').values_list('donor', flat=True))
        
        # Remove None values and combine
        all_donors = (regular_donors | recurring_donors | in_kind_donors) - {None}
        return len(all_donors)

class DonationDetailCampaignSerializer(serializers.ModelSerializer):
    target_currency = CurrencySerializer(read_only=True)
    target_currency_id = serializers.IntegerField(write_only=True)
    project = ProjectMinimalSerializer(read_only=True)
    project_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    created_by = UserBasicSerializer(read_only=True)
    current_amount_in_target_currency = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    progress_percentage = serializers.DecimalField(
        max_digits=5, decimal_places=2, read_only=True
    )
    is_completed = serializers.BooleanField(read_only=True)
    
    # Bank accounts for donations
    campaign_bank_accounts = CampaignBankAccountSerializer(many=True, read_only=True)
    available_bank_accounts = serializers.SerializerMethodField()
    bank_accounts_by_currency = serializers.SerializerMethodField()
    
    # Enhanced counts and statistics including all donation types
    donations_count = serializers.SerializerMethodField()
    donors_count = serializers.SerializerMethodField()
    recurring_donors_count = serializers.SerializerMethodField()
    in_kind_donors_count = serializers.SerializerMethodField()
    total_estimated_in_kind_value = serializers.SerializerMethodField()
    total_recurring_donated = serializers.SerializerMethodField()
    average_donation_amount = serializers.SerializerMethodField()
    days_remaining = serializers.SerializerMethodField()
    days_active = serializers.SerializerMethodField()
    
    # Related data
    in_kind_donations = serializers.SerializerMethodField()
    recurring_donations = serializers.SerializerMethodField()
    donations = serializers.SerializerMethodField()
    
    # Analytics data
    donation_trends = serializers.SerializerMethodField()
    donor_segments = serializers.SerializerMethodField()
    payment_method_breakdown = serializers.SerializerMethodField()
    geographic_distribution = serializers.SerializerMethodField()
    
    # Comprehensive donation breakdown
    donation_breakdown = serializers.SerializerMethodField()
    
    class Meta:
        model = DonationCampaign
        fields = [
            'id', 'title', 'description', 'target_amount', 'target_currency',
            'target_currency_id', 'start_date', 'end_date', 'project', 'project_id',
            'is_active', 'is_featured', 'image', 'created_by', 'created_at',
            'updated_at', 'current_amount_in_target_currency', 'progress_percentage',
            'is_completed', 'campaign_bank_accounts', 'available_bank_accounts',
            'bank_accounts_by_currency', 'donations_count', 'donors_count', 'recurring_donors_count',
            'in_kind_donors_count', 'total_estimated_in_kind_value', 'total_recurring_donated', 
            'average_donation_amount', 'days_remaining', 'days_active', 'in_kind_donations', 
            'recurring_donations', 'donations', 'donation_trends', 'donor_segments', 
            'payment_method_breakdown', 'geographic_distribution', 'donation_breakdown'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']
    
    def get_available_bank_accounts(self, obj):
        """Get available bank accounts for donations"""
        accounts = obj.get_available_bank_accounts()
        return BankAccountMinimalSerializer(accounts, many=True).data
    
    def get_bank_accounts_by_currency(self, obj):
        """Get bank accounts grouped by currency"""
        return obj.get_bank_accounts_by_currency()
    
    def get_donations_count(self, obj):
        return obj.donations.filter(status='completed').count()
    
    def get_donors_count(self, obj):
        """Get unique donors across all donation types"""
        regular_donors = set(obj.donations.filter(status='completed').values_list('donor', flat=True))
        recurring_donors = set(obj.recurring_donations.filter(status__in=['active', 'completed']).values_list('donor', flat=True))
        in_kind_donors = set(obj.in_kind_donations.filter(status='received').values_list('donor', flat=True))
        
        # Remove None values and combine
        all_donors = (regular_donors | recurring_donors | in_kind_donors) - {None}
        return len(all_donors)
    
    def get_recurring_donors_count(self, obj):
        return obj.recurring_donations.filter(status__in=['active', 'completed']).values('donor').distinct().count()
    
    def get_in_kind_donors_count(self, obj):
        return obj.in_kind_donations.filter(status='received').values('donor').distinct().count()
    
    def get_total_estimated_in_kind_value(self, obj):
        """Get total in-kind value in target currency"""
        total = 0
        for in_kind in obj.in_kind_donations.filter(status='received'):
            if in_kind.valuation_currency == obj.target_currency:
                total += in_kind.estimated_value
            else:
                # Convert using exchange rate (simplified)
                total += in_kind.estimated_value  # Would need proper conversion
        return total
    
    def get_total_recurring_donated(self, obj):
        """Get total from recurring donations in target currency"""
        total = 0
        for recurring in obj.recurring_donations.filter(status__in=['active', 'completed']):
            if recurring.currency == obj.target_currency:
                total += recurring.total_donated
            else:
                # Convert using exchange rate (simplified)
                total += recurring.total_donated  # Would need proper conversion
        return total
    
    def get_average_donation_amount(self, obj):
        return obj.donations.filter(status='completed').aggregate(
            avg=Avg('amount')
        )['avg'] or 0
    
    def get_days_remaining(self, obj):
        from django.utils import timezone
        if obj.end_date:
            remaining = (obj.end_date - timezone.now().date()).days
            return max(0, remaining)
        return 0
    
    def get_days_active(self, obj):
        from django.utils import timezone
        return (timezone.now().date() - obj.start_date).days + 1
    
    def get_in_kind_donations(self, obj):
        in_kind = obj.in_kind_donations.select_related(
            'donor', 'valuation_currency'
        ).order_by('-donation_date')[:10]  # Latest 10
        return InKindDonationSerializer(in_kind, many=True).data
    
    def get_recurring_donations(self, obj):
        recurring = obj.recurring_donations.select_related(
            'donor', 'currency'
        ).filter(status__in=['active', 'completed']).order_by('-created_at')[:10]  # Latest 10
        return RecurringDonationSerializer(recurring, many=True).data
    
    def get_donations(self, obj):
        donations = obj.donations.select_related(
            'donor', 'currency'
        ).filter(status='completed').order_by('-donation_date')[:20]  # Latest 20
        return DonationSerializer(donations, many=True).data
    
    def get_donation_trends(self, obj):
        """Get daily donation trends for the last 30 days"""
        from django.utils import timezone
        from datetime import timedelta
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        
        donations = obj.donations.filter(
            status='completed',
            donation_date__gte=start_date,
            donation_date__lte=end_date
        ).extra(
            select={'day': 'date(donation_date)'}
        ).values('day').annotate(
            count=Count('id'),
            total=Sum('amount')
        ).order_by('day')
        
        return list(donations)
    
    def get_donor_segments(self, obj):
        """Segment donors by donation amount"""
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
            total=Sum('amount')
        ).order_by('-total'))
    
    def get_geographic_distribution(self, obj):
        """Get geographic distribution of donors (if available)"""
        # This would require additional user profile fields
        # For now, return empty list
        return []
    
    def get_donation_breakdown(self, obj):
        """Get comprehensive breakdown of all donation types"""
        # Regular donations
        regular_total = obj.donations.filter(status='completed').aggregate(
            total=Sum('amount'), count=Count('id')
        )
        
        # In-kind donations
        in_kind_total = obj.in_kind_donations.filter(status='received').aggregate(
            total=Sum('estimated_value'), count=Count('id')
        )
        
        # Recurring donations
        recurring_total = obj.recurring_donations.filter(
            status__in=['active', 'completed']
        ).aggregate(
            total=Sum('total_donated'), count=Count('id')
        )
        
        return {
            'regular_donations': {
                'count': regular_total['count'] or 0,
                'total': float(regular_total['total'] or 0),
                'percentage': 0  # Will be calculated on frontend
            },
            'in_kind_donations': {
                'count': in_kind_total['count'] or 0,
                'total': float(in_kind_total['total'] or 0),
                'percentage': 0  # Will be calculated on frontend
            },
            'recurring_donations': {
                'count': recurring_total['count'] or 0,
                'total': float(recurring_total['total'] or 0),
                'percentage': 0  
            }
        }

class GrantSerializer(serializers.ModelSerializer):
    currency = CurrencySerializer(read_only=True)
    currency_id = serializers.IntegerField(write_only=True)
    project = serializers.StringRelatedField(read_only=True)
    project_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    designated_account = serializers.StringRelatedField(read_only=True)
    designated_account_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    created_by = UserBasicSerializer(read_only=True)
    managed_by = UserBasicSerializer(read_only=True)
    managed_by_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    remaining_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    formatted_amount = serializers.CharField(read_only=True)
    reports_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Grant
        fields = [
            'id', 'title', 'description', 'grantor', 'grantor_type', 'amount',
            'currency', 'currency_id', 'amount_received', 'submission_date',
            'approval_date', 'start_date', 'end_date', 'application_deadline',
            'project', 'project_id', 'designated_account', 'designated_account_id',
            'status', 'requirements', 'reporting_frequency', 'disbursement_schedule',
            'contact_person', 'contact_email', 'contact_phone', 'notes',
            'created_by', 'managed_by', 'managed_by_id', 'created_at', 'updated_at',
            'remaining_amount', 'formatted_amount', 'reports_count'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']
    
    def get_reports_count(self, obj):
        return obj.reports.count()

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
    donation = DonationSerializer(read_only=True)
    donation_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    campaign = DonationCampaignSerializer(read_only=True)
    campaign_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    grant = GrantSerializer(read_only=True)
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
    class Meta:
        model = Budget
        fields = ['id', 'title', 'total_amount', 'currency', 'start_date', 'end_date']
        read_only_fields = ['id', 'title', 'total_amount', 'currency', 'start_date', 'end_date']

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
    """Enhanced budget item serializer for detail view"""
    remaining_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    spent_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    formatted_amount = serializers.CharField(read_only=True)
    responsible_person = UserBasicSerializer(read_only=True)
    organizational_expenses = OrganizationalExpenseMinimalSerializer(many=True, read_only=True)
    expenses_count = serializers.SerializerMethodField()
    
    class Meta:
        model = BudgetItem
        fields = [
            'id', 'category', 'subcategory', 'description', 'budgeted_amount',
            'spent_amount', 'remaining_amount', 'spent_percentage', 'formatted_amount',
            'is_locked', 'approval_required_threshold', 'responsible_person',
            'notes', 'created_at', 'updated_at', 'organizational_expenses', 'expenses_count'
        ]
    
    def get_expenses_count(self, obj):
        return obj.organizational_expenses.count()

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
        fields = ['id', 'name', 'description', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

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
    """Enhanced Budget serializer for detail view with all relationships"""
    
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
    
    # Computed properties
    remaining_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    spent_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    formatted_amount = serializers.CharField(read_only=True)
    total_funding_allocated = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    
    # Enhanced relationships
    items = BudgetItemDetailSerializer(many=True, read_only=True)
    budget_funding = BudgetFundingDetailSerializer(many=True, read_only=True)
    fund_allocations = FundAllocationDetailSerializer(many=True, read_only=True)
    
    # Summary data
    funding_breakdown = serializers.SerializerMethodField()
    expense_summary = serializers.SerializerMethodField()
    budget_health = serializers.SerializerMethodField()
    recent_expenses = serializers.SerializerMethodField()
    funding_sources_summary = serializers.SerializerMethodField()
    allocation_summary = serializers.SerializerMethodField()
    
    # Statistics
    items_count = serializers.SerializerMethodField()
    expenses_count = serializers.SerializerMethodField()
    funding_sources_count = serializers.SerializerMethodField()
    allocations_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Budget
        fields = [
            # Basic fields
            'id', 'title', 'budget_type', 'project', 'project_id', 'department',
            'department_id', 'total_amount', 'currency', 'currency_id', 'spent_amount',
            'fiscal_year', 'start_date', 'end_date', 'status', 'notes', 'created_by',
            'approved_by', 'approved_by_id', 'approved_at', 'created_at', 'updated_at',
            
            # Computed properties
            'remaining_amount', 'spent_percentage', 'formatted_amount', 'total_funding_allocated',
            
            # Relationships
            'items', 'budget_funding', 'fund_allocations',
            
            # Summary data
            'funding_breakdown', 'expense_summary', 'budget_health', 'recent_expenses',
            'funding_sources_summary', 'allocation_summary',
            
            # Statistics
            'items_count', 'expenses_count', 'funding_sources_count', 'allocations_count'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']
    
    def get_funding_breakdown(self, obj):
        """Get detailed funding breakdown"""
        return obj.get_funding_breakdown()
    
    def get_expense_summary(self, obj):
        """Get expense summary by category"""
        from django.db.models import Sum
        
        expenses = OrganizationalExpense.objects.filter(
            budget_item__budget=obj,
            status='paid'
        ).values('expense_type').annotate(
            total_amount=Sum('amount'),
            count=Count('id')
        ).order_by('-total_amount')
        
        return [
            {
                'expense_type': exp['expense_type'],
                'expense_type_display': dict(OrganizationalExpense.EXPENSE_TYPE_CHOICES).get(exp['expense_type'], exp['expense_type']),
                'total_amount': float(exp['total_amount']) if exp['total_amount'] else 0.0,
                'count': exp['count'],
                'formatted_amount': f"{obj.currency.code} {exp['total_amount']:,.2f}" if exp['total_amount'] else f"{obj.currency.code} 0.00"
            }
            for exp in expenses
        ]
    
    def get_budget_health(self, obj):
        """Calculate budget health indicators"""
        spent_pct = float(obj.spent_percentage) if obj.spent_percentage else 0.0
        
        # Determine health status
        if spent_pct > 100:
            health_status = 'critical'
            health_color = 'red'
        elif spent_pct > 90:
            health_status = 'warning'
            health_color = 'orange'
        elif spent_pct < 50:
            health_status = 'underutilized'
            health_color = 'blue'
        else:
            health_status = 'healthy'
            health_color = 'green'
        
        # Calculate days remaining
        from django.utils import timezone
        days_remaining = None
        if obj.end_date:
            days_remaining = (obj.end_date - timezone.now().date()).days
        
        return {
            'health_status': health_status,
            'health_color': health_color,
            'spent_percentage': spent_pct,
            'days_remaining': days_remaining,
            'is_overbudget': spent_pct > 100,
            'is_near_limit': 90 <= spent_pct <= 100,
            'is_underutilized': spent_pct < 50,
            'funding_gap': float(obj.total_amount - obj.total_funding_allocated) if obj.total_funding_allocated else float(obj.total_amount)
        }
    
    def get_recent_expenses(self, obj):
        """Get recent expenses for this budget"""
        recent_expenses = OrganizationalExpense.objects.filter(
            budget_item__budget=obj
        ).select_related(
            'budget_item', 'currency', 'submitted_by'
        ).order_by('-expense_date')[:10]
        
        return OrganizationalExpenseMinimalSerializer(recent_expenses, many=True).data
    
    def get_funding_sources_summary(self, obj):
        """Get summary of funding sources"""
        funding_sources = []
        for budget_funding in obj.budget_funding.select_related('funding_source', 'funding_source__currency'):
            source = budget_funding.funding_source
            funding_sources.append({
                'id': source.id,
                'name': source.name,
                'funding_type': source.funding_type,
                'funding_type_display': source.get_funding_type_display(),
                'amount_allocated': float(budget_funding.amount_allocated),
                'currency_code': source.currency.code,
                'formatted_amount': f"{source.currency.code} {budget_funding.amount_allocated:,.2f}",
                'is_active': source.is_active,
                'allocation_date': budget_funding.allocation_date.isoformat() if budget_funding.allocation_date else None
            })
        
        return funding_sources
    
    def get_allocation_summary(self, obj):
        """Get summary of fund allocations"""
        allocations_qs = obj.fund_allocations.select_related(
            'source_account', 'source_account__currency', 'allocated_by'
        )

        total_allocated = sum(allocation.amount_allocated for allocation in allocations_qs) or 1  # avoid division by zero

        allocations = []
        for allocation in allocations_qs:
            amount = float(allocation.amount_allocated)
            percentage = (amount / float(total_allocated)) * 100 if total_allocated else 0.0

            allocations.append({
                'id': allocation.id,
                'account_name': allocation.source_account.name,
                'account_type': allocation.source_account.account_type,
                'amount_allocated': amount,
                'currency_code': allocation.source_account.currency.code,
                'formatted_amount': f"{allocation.source_account.currency.code} {allocation.amount_allocated:,.2f}",
                'allocation_date': allocation.allocation_date.isoformat(),
                'allocated_by': allocation.allocated_by.get_full_name if allocation.allocated_by else 'Unknown',
                'purpose': allocation.purpose,
                'is_active': allocation.is_active,
                'percentage': round(percentage, 2)
            })

        return allocations

    def get_items_count(self, obj):
        return obj.items.count()
    
    def get_expenses_count(self, obj):
        return OrganizationalExpense.objects.filter(budget_item__budget=obj).count()
    
    def get_funding_sources_count(self, obj):
        return obj.budget_funding.count()
    
    def get_allocations_count(self, obj):
        return obj.fund_allocations.count()


class OrganizationalExpenseSerializer(serializers.ModelSerializer):
    budget_item = BudgetItemSerializer
    budget_item_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    currency = CurrencySerializer(read_only=True)
    currency_id = serializers.IntegerField(write_only=True)
    submitted_by = UserBasicSerializer(read_only=True)
    approved_by = UserBasicSerializer(read_only=True)
    approved_by_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    formatted_amount = serializers.CharField(read_only=True)
    
    class Meta:
        model = OrganizationalExpense
        fields = [
            'id', 'budget_item', 'budget_item_id', 'title', 'description',
            'expense_type', 'amount', 'currency', 'currency_id', 'expense_date',
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
