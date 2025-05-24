from django.contrib import admin
from django.utils.html import format_html
from .models import (
    FinancialInstitution, BankAccount, ExchangeRate, DonationCampaign,
    Donation, RecurringDonation, InKindDonation, Grant, GrantReport,
    FundingSource, Budget, BudgetFunding, BudgetItem, OrganizationalExpense,
    AccountTransaction, FundAllocation
)

@admin.register(FinancialInstitution)
class FinancialInstitutionAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'branch_name', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'code', 'branch_name']
    ordering = ['name']

@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ['name', 'account_type', 'currency', 'formatted_balance', 'is_active']
    list_filter = ['account_type', 'currency', 'is_active', 'is_restricted']
    search_fields = ['name', 'account_number']
    readonly_fields = ['current_balance', 'formatted_balance']
    filter_horizontal = ['secondary_signatories']

@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ['from_currency', 'to_currency', 'rate', 'effective_date', 'source']
    list_filter = ['from_currency', 'to_currency', 'effective_date']
    ordering = ['-effective_date']

@admin.register(DonationCampaign)
class DonationCampaignAdmin(admin.ModelAdmin):
    list_display = ['title', 'target_amount', 'target_currency', 'progress_percentage', 'is_active', 'start_date', 'end_date']
    list_filter = ['is_active', 'is_featured', 'target_currency', 'start_date']
    search_fields = ['title', 'description']
    readonly_fields = ['current_amount_in_target_currency', 'progress_percentage', 'is_completed']

@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    list_display = ['donor_name_display', 'formatted_amount', 'campaign', 'status', 'donation_date']
    list_filter = ['status', 'payment_method', 'currency', 'is_anonymous', 'donation_date']
    search_fields = ['donor_name', 'donor_email', 'transaction_id', 'reference_number']
    readonly_fields = ['donor_name_display', 'formatted_amount']
    date_hierarchy = 'donation_date'

@admin.register(RecurringDonation)
class RecurringDonationAdmin(admin.ModelAdmin):
    list_display = ['donor', 'formatted_amount', 'frequency', 'status', 'next_payment_date']
    list_filter = ['frequency', 'status', 'currency']
    search_fields = ['donor__username', 'donor__email']

@admin.register(InKindDonation)
class InKindDonationAdmin(admin.ModelAdmin):
    list_display = ['donor_name_display', 'item_description', 'formatted_value', 'status', 'donation_date']
    list_filter = ['status', 'category', 'valuation_currency', 'donation_date']
    search_fields = ['item_description', 'donor_name', 'donor_email']

@admin.register(Grant)
class GrantAdmin(admin.ModelAdmin):
    list_display = ['title', 'grantor', 'formatted_amount', 'status', 'start_date', 'end_date']
    list_filter = ['status', 'grantor_type', 'currency', 'start_date']
    search_fields = ['title', 'grantor', 'description']
    readonly_fields = ['remaining_amount', 'formatted_amount']

@admin.register(GrantReport)
class GrantReportAdmin(admin.ModelAdmin):
    list_display = ['title', 'grant', 'report_type', 'status', 'due_date', 'submission_date']
    list_filter = ['status', 'report_type', 'due_date']
    search_fields = ['title', 'grant__title']

@admin.register(FundingSource)
class FundingSourceAdmin(admin.ModelAdmin):
    list_display = ['name', 'funding_type', 'formatted_amount', 'amount_remaining', 'is_active']
    list_filter = ['funding_type', 'currency', 'is_active']
    search_fields = ['name']
    readonly_fields = ['amount_remaining', 'formatted_amount']

class BudgetItemInline(admin.TabularInline):
    model = BudgetItem
    extra = 0
    readonly_fields = ['remaining_amount', 'spent_percentage']

class BudgetFundingInline(admin.TabularInline):
    model = BudgetFunding
    extra = 0

@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ['title', 'budget_type', 'formatted_amount', 'spent_percentage', 'status']
    list_filter = ['budget_type', 'status', 'currency', 'fiscal_year']
    search_fields = ['title', 'fiscal_year']
    readonly_fields = ['remaining_amount', 'spent_percentage', 'formatted_amount', 'total_funding_allocated']
    inlines = [BudgetItemInline, BudgetFundingInline]

@admin.register(BudgetItem)
class BudgetItemAdmin(admin.ModelAdmin):
    list_display = ['budget', 'category', 'subcategory', 'formatted_amount', 'spent_percentage', 'is_locked']
    list_filter = ['budget', 'category', 'is_locked']
    search_fields = ['category', 'subcategory', 'description']
    readonly_fields = ['remaining_amount', 'spent_percentage', 'formatted_amount']

@admin.register(OrganizationalExpense)
class OrganizationalExpenseAdmin(admin.ModelAdmin):
    list_display = ['title', 'expense_type', 'formatted_amount', 'status', 'expense_date', 'submitted_by']
    list_filter = ['status', 'expense_type', 'currency', 'expense_date']
    search_fields = ['title', 'description', 'vendor']
    readonly_fields = ['formatted_amount']
    date_hierarchy = 'expense_date'

@admin.register(AccountTransaction)
class AccountTransactionAdmin(admin.ModelAdmin):
    list_display = ['account', 'transaction_type', 'formatted_amount', 'status', 'transaction_date', 'is_reconciled']
    list_filter = ['transaction_type', 'status', 'is_reconciled', 'transaction_date']
    search_fields = ['reference_number', 'bank_reference', 'description']
    readonly_fields = ['formatted_amount']
    date_hierarchy = 'transaction_date'

@admin.register(FundAllocation)
class FundAllocationAdmin(admin.ModelAdmin):
    list_display = ['source_account', 'budget', 'formatted_amount', 'allocation_date', 'is_active']
    list_filter = ['is_active', 'allocation_date']
    search_fields = ['purpose']
    readonly_fields = ['formatted_amount']
