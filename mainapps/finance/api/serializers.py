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

class BankAccountCreateUpdateSerializer(serializers.ModelSerializer):
    """Lightweight serializer for creating and updating bank accounts"""
    financial_institution_id = serializers.IntegerField()
    currency_id = serializers.IntegerField()
    primary_signatory_id = serializers.IntegerField()
    secondary_signatory_ids = serializers.ListField(
        child=serializers.IntegerField(), 
        required=False, 
        allow_empty=True,
        default=list
    )
    
    class Meta:
        model = BankAccount
        fields = [
            'name', 'account_number', 'account_type', 'financial_institution_id',
            'currency_id', 'purpose', 'is_restricted', 'restrictions',
            'primary_signatory_id', 'secondary_signatory_ids', 'is_active',
            'account_status', 'accepts_donations', 'opening_date', 'closing_date',
            'minimum_balance', 'online_banking_enabled', 'mobile_banking_enabled',
            'debit_card_enabled', 'routing_number', 'swift_code', 'iban',
            'branch_address', 'overdraft_protection', 'overdraft_limit',
            'interest_rate', 'monthly_maintenance_fee', 'risk_level',
            'compliance_status', 'auto_reconciliation_enabled', 'webhook_url', 'notes'
        ]
        extra_kwargs = {
            'restrictions': {'required': False, 'allow_blank': True, 'allow_null': True},
            'closing_date': {'required': False, 'allow_null': True},
            'notes': {'required': False, 'allow_blank': True, 'allow_null': True},
            'minimum_balance': {'required': False},
            'routing_number': {'required': False, 'allow_blank': True, 'allow_null': True},
            'swift_code': {'required': False, 'allow_blank': True, 'allow_null': True},
            'iban': {'required': False, 'allow_blank': True, 'allow_null': True},
            'branch_address': {'required': False, 'allow_blank': True, 'allow_null': True},
            'overdraft_limit': {'required': False, 'allow_null': True},
            'interest_rate': {'required': False, 'allow_null': True},
            'monthly_maintenance_fee': {'required': False, 'allow_null': True},
            'webhook_url': {'required': False, 'allow_blank': True, 'allow_null': True},
        }
    
    def validate_financial_institution_id(self, value):
        """Validate financial institution exists and is active"""
        try:
            from .models import FinancialInstitution
            FinancialInstitution.objects.get(id=value, is_active=True)
            return value
        except FinancialInstitution.DoesNotExist:
            raise serializers.ValidationError("Invalid or inactive financial institution")
    
    def validate_currency_id(self, value):
        """Validate currency exists"""
        try:
            from mainapps.common.models import Currency
            Currency.objects.get(id=value)
            return value
        except Currency.DoesNotExist:
            raise serializers.ValidationError("Invalid currency")
    
    def validate_primary_signatory_id(self, value):
        """Validate primary signatory exists and is active"""
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            User.objects.get(id=value, is_active=True)
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid or inactive primary signatory")
    
    def validate_secondary_signatory_ids(self, value):
        """Validate secondary signatories exist and are active"""
        if not value:
            return []
        
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            existing_users = User.objects.filter(id__in=value, is_active=True)
            if len(existing_users) != len(value):
                invalid_ids = set(value) - set(existing_users.values_list('id', flat=True))
                raise serializers.ValidationError(f"Invalid or inactive user IDs: {list(invalid_ids)}")
            return value
        except Exception as e:
            raise serializers.ValidationError(f"Error validating secondary signatories: {str(e)}")
    
    def validate(self, attrs):
        """Cross-field validation"""
        # Ensure primary signatory is not in secondary signatories
        primary_id = attrs.get('primary_signatory_id')
        secondary_ids = attrs.get('secondary_signatory_ids', [])
        
        if primary_id and primary_id in secondary_ids:
            raise serializers.ValidationError({
                'secondary_signatory_ids': 'Primary signatory cannot be listed as a secondary signatory'
            })
        
        # Validate overdraft settings
        if attrs.get('overdraft_protection') and not attrs.get('overdraft_limit'):
            raise serializers.ValidationError({
                'overdraft_limit': 'Overdraft limit is required when overdraft protection is enabled'
            })
        
        # Validate closing date
        if attrs.get('closing_date') and attrs.get('opening_date'):
            if attrs['closing_date'] <= attrs['opening_date']:
                raise serializers.ValidationError({
                    'closing_date': 'Closing date must be after opening date'
                })
        
        return attrs
    
    def create(self, validated_data):
        """Create bank account with proper relationship handling"""
        secondary_signatory_ids = validated_data.pop('secondary_signatory_ids', [])
    
        # Set created_by from request context
        if 'request' in self.context:
            validated_data['created_by'] = self.context['request'].user
    
        # Create and save the bank account first
        bank_account = BankAccount.objects.create(**validated_data)
    
        # Now set secondary signatories after the account has an ID
        if secondary_signatory_ids:
            bank_account.secondary_signatories.set(secondary_signatory_ids)
    
        return bank_account
    
    def update(self, instance, validated_data):
        """Update bank account with proper relationship handling"""
        secondary_signatory_ids = validated_data.pop('secondary_signatory_ids', None)
        
        # Update all other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        
        # Update secondary signatories if provided
        if secondary_signatory_ids is not None:
            instance.secondary_signatories.set(secondary_signatory_ids)
        
        return instance
    
    def to_representation(self, instance):
        """Return minimal representation after create/update"""
        return {
            'id': instance.id,
            'name': instance.name,
            'account_number': instance.account_number,
            'account_type': instance.account_type,
            'is_active': instance.is_active,
            'message': 'Bank account saved successfully'
        }


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
                'percentage': 0  # Will be calculated on frontend
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

class FundingSourceSerializer(serializers.ModelSerializer):
    currency = CurrencySerializer(read_only=True)
    currency_id = serializers.IntegerField(write_only=True)
    donation = serializers.StringRelatedField(read_only=True)
    donation_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    campaign = serializers.StringRelatedField(read_only=True)
    campaign_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    grant = serializers.StringRelatedField(read_only=True)
    grant_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    created_by = UserBasicSerializer(read_only=True)
    amount_remaining = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    formatted_amount = serializers.CharField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    is_available_now = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = FundingSource
        fields = [
            'id', 'name', 'funding_type', 'description', 'donation', 'donation_id', 'campaign',
            'campaign_id', 'grant', 'grant_id', 'amount_available', 'currency',
            'currency_id', 'amount_allocated', 'available_from', 'available_until', 
            'restrictions', 'is_active', 'created_by', 'created_at', 'updated_at',
            'amount_remaining', 'formatted_amount', 'is_expired', 'is_available_now'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

class BudgetItemSerializer(serializers.ModelSerializer):
    budget = serializers.StringRelatedField(read_only=True)
    responsible_person = UserBasicSerializer(read_only=True)
    responsible_person_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    remaining_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    spent_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    formatted_amount = serializers.CharField(read_only=True)
    
    class Meta:
        model = BudgetItem
        fields = [
            'id', 'budget', 'category', 'subcategory', 'description', 'budgeted_amount',
            'spent_amount', 'is_locked', 'approval_required_threshold', 'responsible_person',
            'responsible_person_id', 'notes', 'created_at', 'updated_at',
            'remaining_amount', 'spent_percentage', 'formatted_amount'
        ]
        read_only_fields = ['id', 'budget', 'created_at', 'updated_at']

class BudgetFundingSerializer(serializers.ModelSerializer):
    funding_source = FundingSourceSerializer(read_only=True)
    funding_source_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = BudgetFunding
        fields = [
            'id', 'funding_source', 'funding_source_id', 'amount_allocated',
            'allocation_date', 'notes'
        ]
        read_only_fields = ['id', 'allocation_date']

class BudgetSerializer(serializers.ModelSerializer):
    project = serializers.StringRelatedField(read_only=True)
    project_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    department = serializers.StringRelatedField(read_only=True)
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

class OrganizationalExpenseSerializer(serializers.ModelSerializer):
    budget_item = serializers.StringRelatedField(read_only=True)
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
    account = serializers.StringRelatedField(read_only=True)
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
    approved_by_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    formatted_amount = serializers.CharField(read_only=True)
    
    class Meta:
        model = FundAllocation
        fields = [
            'id', 'source_account', 'source_account_id', 'budget', 'budget_id',
            'amount_allocated', 'allocation_date', 'purpose', 'allocated_by',
            'approved_by', 'approved_by_id', 'is_active', 'created_at',
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
