from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db.models import Sum, Count, Avg
from decimal import Decimal
from ..models import (
    FinancialInstitution, BankAccount, ExchangeRate, DonationCampaign,
    Donation, RecurringDonation, InKindDonation, Grant, GrantReport,
    FundingSource, Budget, BudgetFunding, BudgetItem, OrganizationalExpense,
    AccountTransaction, FundAllocation
)
from mainapps.common.models import Currency
from mainapps.accounts.models import Department
from mainapps.project.models import Project

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
        fields = ['id', 'code', 'name', 'symbol']

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
    current_balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    formatted_balance = serializers.CharField(read_only=True)
    transactions_count = serializers.SerializerMethodField()
    
    class Meta:
        model = BankAccount
        fields = [
            'id', 'name', 'account_number', 'account_type', 'financial_institution',
            'financial_institution_id', 'currency', 'currency_id', 'purpose',
            'is_restricted', 'restrictions', 'primary_signatory', 'primary_signatory_id',
            'secondary_signatories', 'secondary_signatory_ids', 'is_active',
            'opening_date', 'closing_date', 'minimum_balance', 'api_key',
            'webhook_url', 'created_by', 'created_at', 'updated_at',
            'current_balance', 'formatted_balance', 'transactions_count'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']
        extra_kwargs = {
            'api_key': {'write_only': True},
        }
    
    def get_transactions_count(self, obj):
        return obj.transactions.count()
    
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

class DonationCampaignSerializer(serializers.ModelSerializer):
    target_currency = CurrencySerializer(read_only=True)
    target_currency_id = serializers.IntegerField(write_only=True)
    project = serializers.StringRelatedField(read_only=True)
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
        return obj.donations.filter(status='completed').values('donor').distinct().count()

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
            'deposited_to_account_id', 'deposit_date', 'bank_reference', 'notes',
            'receipt_sent', 'receipt_number', 'tax_deductible', 'processed_by',
            'created_at', 'updated_at', 'donor_name_display', 'formatted_amount'
        ]
        read_only_fields = ['id', 'processed_by', 'created_at', 'updated_at']

class RecurringDonationSerializer(serializers.ModelSerializer):
    donor = UserBasicSerializer(read_only=True)
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
            'id', 'donor', 'is_anonymous', 'campaign', 'campaign_id', 'project',
            'project_id', 'amount', 'currency', 'currency_id', 'frequency',
            'start_date', 'end_date', 'next_payment_date', 'payment_method',
            'subscription_id', 'status', 'total_donated', 'payment_count',
            'notes', 'created_at', 'updated_at', 'formatted_amount'
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
            'image', 'created_at', 'updated_at', 'donor_name_display', 'formatted_value'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

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
    amount_remaining = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    formatted_amount = serializers.CharField(read_only=True)
    
    class Meta:
        model = FundingSource
        fields = [
            'id', 'name', 'funding_type', 'donation', 'donation_id', 'campaign',
            'campaign_id', 'grant', 'grant_id', 'amount_available', 'currency',
            'currency_id', 'amount_allocated', 'is_active', 'created_at',
            'amount_remaining', 'formatted_amount'
        ]
        read_only_fields = ['id', 'created_at']

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
    authorized_by_id = serializers.IntegerField(write_only=True)
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
            'status', 'processor_fee', 'net_amount', 'authorized_by', 'authorized_by_id',
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
