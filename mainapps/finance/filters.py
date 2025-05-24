import django_filters
from django.db import models
from .models import (
    Donation, Grant, Budget, OrganizationalExpense, AccountTransaction
)

class DonationFilter(django_filters.FilterSet):
    amount_min = django_filters.NumberFilter(field_name='amount', lookup_expr='gte')
    amount_max = django_filters.NumberFilter(field_name='amount', lookup_expr='lte')
    donation_date_from = django_filters.DateFilter(field_name='donation_date', lookup_expr='gte')
    donation_date_to = django_filters.DateFilter(field_name='donation_date', lookup_expr='lte')
    
    class Meta:
        model = Donation
        fields = [
            'status', 'payment_method', 'currency', 'campaign', 'project',
            'is_anonymous', 'tax_deductible', 'receipt_sent'
        ]

class GrantFilter(django_filters.FilterSet):
    amount_min = django_filters.NumberFilter(field_name='amount', lookup_expr='gte')
    amount_max = django_filters.NumberFilter(field_name='amount', lookup_expr='lte')
    start_date_from = django_filters.DateFilter(field_name='start_date', lookup_expr='gte')
    start_date_to = django_filters.DateFilter(field_name='start_date', lookup_expr='lte')
    
    class Meta:
        model = Grant
        fields = [
            'status', 'grantor_type', 'currency', 'project', 'managed_by'
        ]

class BudgetFilter(django_filters.FilterSet):
    total_amount_min = django_filters.NumberFilter(field_name='total_amount', lookup_expr='gte')
    total_amount_max = django_filters.NumberFilter(field_name='total_amount', lookup_expr='lte')
    start_date_from = django_filters.DateFilter(field_name='start_date', lookup_expr='gte')
    start_date_to = django_filters.DateFilter(field_name='start_date', lookup_expr='lte')
    
    class Meta:
        model = Budget
        fields = [
            'budget_type', 'status', 'currency', 'project', 'department',
            'fiscal_year', 'created_by', 'approved_by'
        ]

class ExpenseFilter(django_filters.FilterSet):
    amount_min = django_filters.NumberFilter(field_name='amount', lookup_expr='gte')
    amount_max = django_filters.NumberFilter(field_name='amount', lookup_expr='lte')
    expense_date_from = django_filters.DateFilter(field_name='expense_date', lookup_expr='gte')
    expense_date_to = django_filters.DateFilter(field_name='expense_date', lookup_expr='lte')
    
    class Meta:
        model = OrganizationalExpense
        fields = [
            'status', 'expense_type', 'currency', 'budget_item', 'submitted_by',
            'approved_by'
        ]

class TransactionFilter(django_filters.FilterSet):
    amount_min = django_filters.NumberFilter(field_name='amount', lookup_expr='gte')
    amount_max = django_filters.NumberFilter(field_name='amount', lookup_expr='lte')
    transaction_date_from = django_filters.DateTimeFilter(field_name='transaction_date', lookup_expr='gte')
    transaction_date_to = django_filters.DateTimeFilter(field_name='transaction_date', lookup_expr='lte')
    
    class Meta:
        model = AccountTransaction
        fields = [
            'account', 'transaction_type', 'status', 'original_currency',
            'authorized_by', 'is_reconciled'
        ]
