from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Count, Avg, Q, F
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import calendar

from ..models import (
    FinancialInstitution, BankAccount, ExchangeRate, DonationCampaign,
    Donation, RecurringDonation, InKindDonation, Grant, GrantReport,
    FundingSource, Budget, BudgetFunding, BudgetItem, OrganizationalExpense,
    AccountTransaction, FundAllocation
)
from .serializers import (
    FinancialInstitutionSerializer, BankAccountSerializer, ExchangeRateSerializer,
    DonationCampaignSerializer, DonationSerializer, RecurringDonationSerializer,
    InKindDonationSerializer, GrantSerializer, GrantReportSerializer,
    FundingSourceSerializer, BudgetSerializer, BudgetFundingSerializer,
    BudgetItemSerializer, OrganizationalExpenseSerializer, AccountTransactionSerializer,
    FundAllocationSerializer, FinancialSummarySerializer, DonationStatsSerializer,
    CampaignPerformanceSerializer, BudgetUtilizationSerializer
)
from ..filters import (
    DonationFilter, GrantFilter, BudgetFilter, ExpenseFilter, TransactionFilter
)

class FinancialInstitutionViewSet(viewsets.ModelViewSet):
    queryset = FinancialInstitution.objects.all()
    serializer_class = FinancialInstitutionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'code', 'branch_name']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

class BankAccountViewSet(viewsets.ModelViewSet):
    queryset = BankAccount.objects.select_related(
        'financial_institution', 'currency', 'primary_signatory', 'created_by'
    ).prefetch_related('secondary_signatories')
    serializer_class = BankAccountSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['account_type', 'currency', 'is_active', 'is_restricted']
    search_fields = ['name', 'account_number']
    ordering_fields = ['name', 'created_at', 'current_balance']
    ordering = ['name']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['get'])
    def transactions(self, request, pk=None):
        """Get transactions for a specific account"""
        account = self.get_object()
        transactions = account.transactions.all().order_by('-transaction_date')
        
        # Apply date filtering
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if start_date:
            transactions = transactions.filter(transaction_date__gte=start_date)
        if end_date:
            transactions = transactions.filter(transaction_date__lte=end_date)
        
        serializer = AccountTransactionSerializer(transactions, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def balance_history(self, request, pk=None):
        """Get balance history for an account"""
        account = self.get_object()
        days = int(request.query_params.get('days', 30))
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Calculate daily balances
        transactions = account.transactions.filter(
            transaction_date__gte=start_date,
            status='completed'
        ).order_by('transaction_date')
        
        balance_history = []
        running_balance = Decimal('0.00')
        
        for transaction in transactions:
            if transaction.transaction_type in ['credit', 'transfer_in']:
                running_balance += transaction.amount
            else:
                running_balance -= transaction.amount
            
            balance_history.append({
                'date': transaction.transaction_date.date(),
                'balance': running_balance,
                'transaction_type': transaction.transaction_type,
                'amount': transaction.amount
            })
        
        return Response(balance_history)

class ExchangeRateViewSet(viewsets.ModelViewSet):
    queryset = ExchangeRate.objects.select_related('from_currency', 'to_currency', 'created_by')
    serializer_class = ExchangeRateSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['from_currency', 'to_currency']
    ordering_fields = ['effective_date', 'rate']
    ordering = ['-effective_date']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def latest_rates(self, request):
        """Get latest exchange rates for all currency pairs"""
        latest_rates = []
        
        # Get unique currency pairs
        pairs = ExchangeRate.objects.values('from_currency', 'to_currency').distinct()
        
        for pair in pairs:
            latest_rate = ExchangeRate.objects.filter(
                from_currency=pair['from_currency'],
                to_currency=pair['to_currency']
            ).order_by('-effective_date').first()
            
            if latest_rate:
                latest_rates.append(ExchangeRateSerializer(latest_rate).data)
        
        return Response(latest_rates)

class DonationCampaignViewSet(viewsets.ModelViewSet):
    queryset = DonationCampaign.objects.select_related(
        'target_currency', 'project', 'created_by'
    ).prefetch_related('donations')
    serializer_class = DonationCampaignSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'is_featured', 'target_currency', 'project']
    search_fields = ['title', 'description']
    ordering_fields = ['title', 'start_date', 'end_date', 'target_amount', 'created_at']
    ordering = ['-created_at']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['get'])
    def donations(self, request, pk=None):
        """Get donations for a specific campaign"""
        campaign = self.get_object()
        donations = campaign.donations.filter(status='completed').order_by('-donation_date')
        serializer = DonationSerializer(donations, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Get detailed statistics for a campaign"""
        campaign = self.get_object()
        donations = campaign.donations.filter(status='completed')
        
        stats = {
            'total_raised': campaign.current_amount_in_target_currency,
            'target_amount': campaign.target_amount,
            'progress_percentage': campaign.progress_percentage,
            'total_donations': donations.count(),
            'unique_donors': donations.values('donor').distinct().count(),
            'average_donation': donations.aggregate(avg=Avg('amount'))['avg'] or 0,
            'largest_donation': donations.aggregate(max=Sum('amount'))['max'] or 0,
            'days_remaining': (campaign.end_date - timezone.now().date()).days,
            'is_completed': campaign.is_completed,
        }
        
        return Response(stats)

class DonationViewSet(viewsets.ModelViewSet):
    queryset = Donation.objects.select_related(
        'donor', 'campaign', 'project', 'currency', 'converted_currency',
        'processor_fee_currency', 'deposited_to_account', 'processed_by'
    )
    serializer_class = DonationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = DonationFilter
    search_fields = ['donor_name', 'donor_email', 'reference_number', 'transaction_id']
    ordering_fields = ['donation_date', 'amount', 'status', 'created_at']
    ordering = ['-donation_date']
    
    def perform_create(self, serializer):
        serializer.save(processed_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get donation statistics"""
        period = request.query_params.get('period', 'month')  # day, week, month, year
        
        now = timezone.now()
        if period == 'day':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == 'week':
            start_date = now - timedelta(days=7)
        elif period == 'month':
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif period == 'year':
            start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            start_date = now - timedelta(days=30)
        
        donations = Donation.objects.filter(
            donation_date__gte=start_date,
            status='completed'
        )
        
        stats = {
            'period': period,
            'total_amount': donations.aggregate(total=Sum('amount'))['total'] or 0,
            'donation_count': donations.count(),
            'average_donation': donations.aggregate(avg=Avg('amount'))['avg'] or 0,
            'unique_donors': donations.values('donor').distinct().count(),
            'top_campaigns': list(
                donations.values('campaign__title')
                .annotate(total=Sum('amount'), count=Count('id'))
                .order_by('-total')[:5]
            ),
            'payment_methods': list(
                donations.values('payment_method')
                .annotate(total=Sum('amount'), count=Count('id'))
                .order_by('-total')
            )
        }
        
        serializer = DonationStatsSerializer(stats)
        return Response(serializer.data)

class RecurringDonationViewSet(viewsets.ModelViewSet):
    queryset = RecurringDonation.objects.select_related(
        'donor', 'campaign', 'project', 'currency'
    )
    serializer_class = RecurringDonationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'frequency', 'currency', 'campaign', 'project']
    search_fields = ['donor__username', 'donor__email']
    ordering_fields = ['start_date', 'amount', 'next_payment_date', 'created_at']
    ordering = ['-created_at']
    
    @action(detail=False, methods=['get'])
    def due_payments(self, request):
        """Get recurring donations due for payment"""
        today = timezone.now().date()
        due_donations = self.queryset.filter(
            status='active',
            next_payment_date__lte=today
        )
        serializer = self.get_serializer(due_donations, many=True)
        return Response(serializer.data)

class InKindDonationViewSet(viewsets.ModelViewSet):
    queryset = InKindDonation.objects.select_related(
        'donor', 'campaign', 'project', 'valuation_currency', 'received_by'
    )
    serializer_class = InKindDonationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'category', 'valuation_currency', 'campaign', 'project']
    search_fields = ['item_description', 'donor_name', 'donor_email']
    ordering_fields = ['donation_date', 'estimated_value', 'received_date', 'created_at']
    ordering = ['-donation_date']

class GrantViewSet(viewsets.ModelViewSet):
    queryset = Grant.objects.select_related(
        'currency', 'project', 'designated_account', 'created_by', 'managed_by'
    ).prefetch_related('reports')
    serializer_class = GrantSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = GrantFilter
    search_fields = ['title', 'grantor', 'description']
    ordering_fields = ['title', 'amount', 'start_date', 'end_date', 'created_at']
    ordering = ['-created_at']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get grant statistics"""
        grants = Grant.objects.all()
        
        stats = {
            'total_grants': grants.count(),
            'total_amount': grants.aggregate(total=Sum('amount'))['total'] or 0,
            'total_received': grants.aggregate(total=Sum('amount_received'))['total'] or 0,
            'active_grants': grants.filter(status='active').count(),
            'pending_grants': grants.filter(status__in=['submitted', 'under_review']).count(),
            'by_type': list(
                grants.values('grantor_type')
                .annotate(count=Count('id'), total_amount=Sum('amount'))
                .order_by('-total_amount')
            ),
            'by_status': list(
                grants.values('status')
                .annotate(count=Count('id'), total_amount=Sum('amount'))
                .order_by('-total_amount')
            )
        }
        
        return Response(stats)

class GrantReportViewSet(viewsets.ModelViewSet):
    queryset = GrantReport.objects.select_related('grant', 'submitted_by')
    serializer_class = GrantReportSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'report_type', 'grant']
    search_fields = ['title', 'grant__title']
    ordering_fields = ['due_date', 'submission_date', 'created_at']
    ordering = ['-created_at']
    
    def perform_create(self, serializer):
        serializer.save(submitted_by=self.request.user)

class FundingSourceViewSet(viewsets.ModelViewSet):
    queryset = FundingSource.objects.select_related(
        'currency', 'donation', 'campaign', 'grant'
    )
    serializer_class = FundingSourceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['funding_type', 'currency', 'is_active']
    search_fields = ['name']
    ordering_fields = ['name', 'amount_available', 'created_at']
    ordering = ['name']

class BudgetViewSet(viewsets.ModelViewSet):
    queryset = Budget.objects.select_related(
        'project', 'department', 'currency', 'created_by', 'approved_by'
    ).prefetch_related('items', 'budget_funding__funding_source')
    serializer_class = BudgetSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = BudgetFilter
    search_fields = ['title', 'fiscal_year']
    ordering_fields = ['title', 'total_amount', 'start_date', 'end_date', 'created_at']
    ordering = ['-created_at']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a budget"""
        budget = self.get_object()
        budget.status = 'approved'
        budget.approved_by = request.user
        budget.approved_at = timezone.now()
        budget.save()
        
        serializer = self.get_serializer(budget)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def utilization(self, request, pk=None):
        """Get budget utilization details"""
        budget = self.get_object()
        
        utilization = {
            'budget_id': budget.id,
            'budget_title': budget.title,
            'budget_type': budget.get_budget_type_display(),
            'total_amount': budget.total_amount,
            'spent_amount': budget.spent_amount,
            'remaining_amount': budget.remaining_amount,
            'utilization_percentage': budget.spent_percentage,
            'currency_code': budget.currency.code,
            'items_breakdown': []
        }
        
        for item in budget.items.all():
            utilization['items_breakdown'].append({
                'category': item.category,
                'subcategory': item.subcategory,
                'budgeted_amount': item.budgeted_amount,
                'spent_amount': item.spent_amount,
                'remaining_amount': item.remaining_amount,
                'utilization_percentage': item.spent_percentage
            })
        
        return Response(utilization)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get budget statistics"""
        budgets = Budget.objects.all()
        
        stats = {
            'total_budgets': budgets.count(),
            'total_allocated': budgets.aggregate(total=Sum('total_amount'))['total'] or 0,
            'total_spent': budgets.aggregate(total=Sum('spent_amount'))['total'] or 0,
            'by_type': list(
                budgets.values('budget_type')
                .annotate(
                    count=Count('id'),
                    total_amount=Sum('total_amount'),
                    spent_amount=Sum('spent_amount')
                )
                .order_by('-total_amount')
            ),
            'by_status': list(
                budgets.values('status')
                .annotate(
                    count=Count('id'),
                    total_amount=Sum('total_amount'),
                    spent_amount=Sum('spent_amount')
                )
                .order_by('-total_amount')
            ),
            'utilization_summary': []
        }
        
        # Calculate utilization for each budget
        for budget in budgets.filter(status='active'):
            utilization_data = {
                'budget_id': budget.id,
                'budget_title': budget.title,
                'budget_type': budget.get_budget_type_display(),
                'total_amount': budget.total_amount,
                'spent_amount': budget.spent_amount,
                'remaining_amount': budget.remaining_amount,
                'utilization_percentage': budget.spent_percentage,
                'currency_code': budget.currency.code
            }
            stats['utilization_summary'].append(utilization_data)
        
        return Response(stats)

class BudgetItemViewSet(viewsets.ModelViewSet):
    queryset = BudgetItem.objects.select_related('budget', 'responsible_person')
    serializer_class = BudgetItemSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['budget', 'category', 'responsible_person', 'is_locked']
    search_fields = ['category', 'subcategory', 'description']
    ordering_fields = ['category', 'budgeted_amount', 'spent_amount', 'created_at']
    ordering = ['category', 'subcategory']

class OrganizationalExpenseViewSet(viewsets.ModelViewSet):
    queryset = OrganizationalExpense.objects.select_related(
        'budget_item', 'currency', 'submitted_by', 'approved_by'
    )
    serializer_class = OrganizationalExpenseSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ExpenseFilter
    search_fields = ['title', 'description', 'vendor']
    ordering_fields = ['expense_date', 'amount', 'status', 'created_at']
    ordering = ['-expense_date']
    
    def perform_create(self, serializer):
        serializer.save(submitted_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve an expense"""
        expense = self.get_object()
        expense.status = 'approved'
        expense.approved_by = request.user
        expense.approved_at = timezone.now()
        expense.save()
        
        serializer = self.get_serializer(expense)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def pending_approvals(self, request):
        """Get expenses pending approval"""
        pending_expenses = self.queryset.filter(status='pending')
        serializer = self.get_serializer(pending_expenses, many=True)
        return Response(serializer.data)

class AccountTransactionViewSet(viewsets.ModelViewSet):
    queryset = AccountTransaction.objects.select_related(
        'account', 'original_currency', 'donation', 'grant', 'expense',
        'transfer_to_account', 'authorized_by', 'reconciled_by'
    )
    serializer_class = AccountTransactionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = TransactionFilter
    search_fields = ['reference_number', 'bank_reference', 'description']
    ordering_fields = ['transaction_date', 'amount', 'status', 'created_at']
    ordering = ['-transaction_date']
    
    @action(detail=True, methods=['post'])
    def reconcile(self, request, pk=None):
        """Mark transaction as reconciled"""
        transaction = self.get_object()
        transaction.is_reconciled = True
        transaction.reconciled_date = timezone.now()
        transaction.reconciled_by = request.user
        transaction.save()
        
        serializer = self.get_serializer(transaction)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def unreconciled(self, request):
        """Get unreconciled transactions"""
        unreconciled = self.queryset.filter(is_reconciled=False, status='completed')
        serializer = self.get_serializer(unreconciled, many=True)
        return Response(serializer.data)

class FundAllocationViewSet(viewsets.ModelViewSet):
    queryset = FundAllocation.objects.select_related(
        'source_account', 'budget', 'allocated_by', 'approved_by'
    )
    serializer_class = FundAllocationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['source_account', 'budget', 'is_active']
    search_fields = ['purpose']
    ordering_fields = ['allocation_date', 'amount_allocated', 'created_at']
    ordering = ['-allocation_date']
    
    def perform_create(self, serializer):
        serializer.save(allocated_by=self.request.user)

# Dashboard and Statistics ViewSet
class DashboardViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def financial_summary(self, request):
        """Get overall financial summary"""
        # Calculate totals
        total_donations = Donation.objects.filter(status='completed').aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        total_grants = Grant.objects.filter(status='active').aggregate(
            total=Sum('amount_received')
        )['total'] or 0
        
        total_expenses = OrganizationalExpense.objects.filter(status='paid').aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        total_budget_allocated = Budget.objects.filter(status='active').aggregate(
            total=Sum('total_amount')
        )['total'] or 0
        
        total_account_balance = sum(account.current_balance for account in BankAccount.objects.filter(is_active=True))
        
        active_campaigns_count = DonationCampaign.objects.filter(is_active=True).count()
        active_grants_count = Grant.objects.filter(status='active').count()
        pending_expenses_count = OrganizationalExpense.objects.filter(status='pending').count()
        
        summary = {
            'total_donations': total_donations,
            'total_grants': total_grants,
            'total_expenses': total_expenses,
            'total_budget_allocated': total_budget_allocated,
            'total_account_balance': total_account_balance,
            'active_campaigns_count': active_campaigns_count,
            'active_grants_count': active_grants_count,
            'pending_expenses_count': pending_expenses_count,
        }
        
        serializer = FinancialSummarySerializer(summary)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def campaign_performance(self, request):
        """Get campaign performance data"""
        campaigns = DonationCampaign.objects.filter(is_active=True)
        performance_data = []
        
        for campaign in campaigns:
            days_remaining = (campaign.end_date - timezone.now().date()).days
            donors_count = campaign.donations.filter(status='completed').values('donor').distinct().count()
            
            performance_data.append({
                'campaign_id': campaign.id,
                'campaign_title': campaign.title,
                'target_amount': campaign.target_amount,
                'raised_amount': campaign.current_amount_in_target_currency,
                'progress_percentage': campaign.progress_percentage,
                'donors_count': donors_count,
                'days_remaining': days_remaining,
            })
        
        serializer = CampaignPerformanceSerializer(performance_data, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def budget_utilization(self, request):
        """Get budget utilization data"""
        budgets = Budget.objects.filter(status='active')
        utilization_data = []
        
        for budget in budgets:
            utilization_data.append({
                'budget_id': budget.id,
                'budget_title': budget.title,
                'budget_type': budget.get_budget_type_display(),
                'total_amount': budget.total_amount,
                'spent_amount': budget.spent_amount,
                'remaining_amount': budget.remaining_amount,
                'utilization_percentage': budget.spent_percentage,
                'currency_code': budget.currency.code,
            })
        
        serializer = BudgetUtilizationSerializer(utilization_data, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def monthly_trends(self, request):
        """Get monthly financial trends"""
        months = int(request.query_params.get('months', 12))
        end_date = timezone.now()
        start_date = end_date - timedelta(days=months * 30)
        
        trends = []
        
        for i in range(months):
            month_start = start_date + timedelta(days=i * 30)
            month_end = month_start + timedelta(days=30)
            
            donations = Donation.objects.filter(
                donation_date__gte=month_start,
                donation_date__lt=month_end,
                status='completed'
            ).aggregate(total=Sum('amount'), count=Count('id'))
            
            expenses = OrganizationalExpense.objects.filter(
                expense_date__gte=month_start.date(),
                expense_date__lt=month_end.date(),
                status='paid'
            ).aggregate(total=Sum('amount'), count=Count('id'))
            
            trends.append({
                'month': month_start.strftime('%Y-%m'),
                'donations_total': donations['total'] or 0,
                'donations_count': donations['count'] or 0,
                'expenses_total': expenses['total'] or 0,
                'expenses_count': expenses['count'] or 0,
                'net_income': (donations['total'] or 0) - (expenses['total'] or 0)
            })
        
        return Response(trends)
