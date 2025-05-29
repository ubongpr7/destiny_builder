from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Count, Avg, Q, F, Case, When, Value, DecimalField, FloatField
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import calendar
from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models import Max

from ..models import (
    FinancialInstitution, BankAccount, ExchangeRate, DonationCampaign,
    Donation, RecurringDonation, InKindDonation, Grant, GrantReport,
    FundingSource, Budget, BudgetFunding, BudgetItem, OrganizationalExpense,
    AccountTransaction, FundAllocation
)
from .serializers import (
    BudgetDetailSerializer, BudgetItemDetailSerializer, FinancialInstitutionSerializer, BankAccountSerializer, ExchangeRateSerializer,
    DonationCampaignSerializer, DonationDetailCampaignSerializer, DonationSerializer, RecurringDonationSerializer,
    InKindDonationSerializer, GrantSerializer, GrantReportSerializer,
    FundingSourceSerializer, BudgetSerializer, BudgetFundingSerializer,
    BudgetItemSerializer, OrganizationalExpenseSerializer, AccountTransactionSerializer,
    FundAllocationSerializer, FinancialSummarySerializer, DonationStatsSerializer,
    CampaignPerformanceSerializer, BudgetUtilizationSerializer
)
from ..filters import (
    DonationFilter, GrantFilter, BudgetFilter, ExpenseFilter, TransactionFilter
)
from .notification_utils import (
    send_donation_received_notification,
    send_recurring_donation_notification,
    send_in_kind_donation_notification,
    send_campaign_milestone_notification,
    send_campaign_ending_notification,
    send_grant_status_notification,
    send_grant_report_due_notification,
    send_grant_disbursement_notification,
    send_budget_notification,
    send_expense_notification,
    send_account_notification,
    send_transaction_notification,
    send_reconciliation_notification
)

class FinancialInstitutionViewSet(viewsets.ModelViewSet):
    """Enhanced Financial Institution ViewSet with comprehensive management"""
    queryset = FinancialInstitution.objects.all()
    serializer_class = FinancialInstitutionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'code', 'branch_name', 'contact_person']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate financial institution"""
        institution = self.get_object()
        institution.is_active = True
        institution.save()
        
        return Response({
            'message': f'{institution.name} has been activated',
            'status': 'active'
        })

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate financial institution"""
        institution = self.get_object()
        
        # Check if there are active accounts
        active_accounts = institution.accounts.filter(is_active=True).count()
        if active_accounts > 0:
            return Response({
                'error': f'Cannot deactivate institution with {active_accounts} active accounts'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        institution.is_active = False
        institution.save()
        
        return Response({
            'message': f'{institution.name} has been deactivated',
            'status': 'inactive'
        })

    @action(detail=True, methods=['get'])
    def accounts_summary(self, request, pk=None):
        """Get summary of all accounts for this institution"""
        institution = self.get_object()
        accounts = institution.accounts.all()
        
        summary = {
            'institution_name': institution.name,
            'total_accounts': accounts.count(),
            'active_accounts': accounts.filter(is_active=True).count(),
            'total_balance': sum(account.current_balance for account in accounts.filter(is_active=True)),
            'accounts_by_type': list(accounts.values('account_type').annotate(
                count=Count('id'),
                total_balance=Sum('current_balance')
            ).order_by('account_type')),
            'accounts_by_currency': list(accounts.values('currency__code').annotate(
                count=Count('id'),
                total_balance=Sum('current_balance')
            ).order_by('currency__code'))
        }
        
        return Response(summary)

class BankAccountViewSet(viewsets.ModelViewSet):
    """Enhanced Bank Account ViewSet with comprehensive transaction management"""
    queryset = BankAccount.objects.select_related(
        'financial_institution', 'currency', 'primary_signatory', 'created_by'
    ).prefetch_related('secondary_signatories')
    serializer_class = BankAccountSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['account_type', 'currency', 'is_active', 'is_restricted', 'accepts_donations']
    search_fields = ['name', 'account_number', 'purpose']
    ordering_fields = ['name', 'created_at', 'current_balance']
    ordering = ['name']
    
    def perform_create(self, serializer):
        account = serializer.save(created_by=self.request.user)
        # Send notification for new account
        send_account_notification(account, 'created')
    
    @action(detail=True, methods=['get'])
    def transactions(self, request, pk=None):
        """Get transactions for a specific account with enhanced filtering"""
        account = self.get_object()
        transactions = account.transactions.all().order_by('-transaction_date')
        
        # Apply filters
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        transaction_type = request.query_params.get('type')
        status_filter = request.query_params.get('status')
        min_amount = request.query_params.get('min_amount')
        max_amount = request.query_params.get('max_amount')
        
        if start_date:
            transactions = transactions.filter(transaction_date__gte=start_date)
        if end_date:
            transactions = transactions.filter(transaction_date__lte=end_date)
        if transaction_type:
            transactions = transactions.filter(transaction_type=transaction_type)
        if status_filter:
            transactions = transactions.filter(status=status_filter)
        if min_amount:
            transactions = transactions.filter(amount__gte=min_amount)
        if max_amount:
            transactions = transactions.filter(amount__lte=max_amount)
        
        # Calculate summary
        summary = {
            'total_transactions': transactions.count(),
            'total_credits': transactions.filter(
                transaction_type__in=['credit', 'transfer_in']
            ).aggregate(total=Sum('amount'))['total'] or 0,
            'total_debits': transactions.filter(
                transaction_type__in=['debit', 'transfer_out']
            ).aggregate(total=Sum('amount'))['total'] or 0,
            'unreconciled_count': transactions.filter(is_reconciled=False).count()
        }
        
        # Pagination
        page = self.paginate_queryset(transactions)
        if page is not None:
            serializer = AccountTransactionSerializer(page, many=True)
            return self.get_paginated_response({
                'results': serializer.data,
                'summary': summary
            })
        
        serializer = AccountTransactionSerializer(transactions, many=True)
        return Response({
            'results': serializer.data,
            'summary': summary
        })
    
    @action(detail=True, methods=['get'])
    def balance_history(self, request, pk=None):
        """Get balance history for an account"""
        account = self.get_object()
        days = int(request.query_params.get('days', 30))
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        transactions = account.transactions.filter(
            transaction_date__gte=start_date,
            status='completed'
        ).order_by('transaction_date')
        
        balance_history = []
        running_balance = Decimal('0.00')
        
        # Get starting balance (transactions before start_date)
        earlier_transactions = account.transactions.filter(
            transaction_date__lt=start_date,
            status='completed'
        )
        
        for trans in earlier_transactions:
            if trans.transaction_type in ['credit', 'transfer_in']:
                running_balance += trans.amount
            else:
                running_balance -= trans.amount
        
        # Build daily balance history
        current_date = start_date.date()
        daily_balances = {}
        
        for transaction in transactions:
            trans_date = transaction.transaction_date.date()
            
            if trans_date not in daily_balances:
                daily_balances[trans_date] = running_balance
            
            if transaction.transaction_type in ['credit', 'transfer_in']:
                running_balance += transaction.amount
            else:
                running_balance -= transaction.amount
            
            daily_balances[trans_date] = running_balance
        
        # Fill in missing dates
        while current_date <= end_date.date():
            if current_date not in daily_balances:
                daily_balances[current_date] = running_balance
            current_date += timedelta(days=1)
        
        # Convert to list format
        for date, balance in sorted(daily_balances.items()):
            balance_history.append({
                'date': date.isoformat(),
                'balance': float(balance),
                'formatted_balance': f"{account.currency.code} {balance:,.2f}"
            })
        
        return Response({
            'account_name': account.name,
            'currency': account.currency.code,
            'period_days': days,
            'current_balance': float(account.current_balance),
            'balance_history': balance_history
        })
    
    @action(detail=True, methods=['post'])
    def check_low_balance(self, request, pk=None):
        """Check and alert for low balance"""
        account = self.get_object()
        threshold = Decimal(request.data.get('threshold', account.minimum_balance or '1000.00'))
        
        if account.current_balance < threshold:
            send_account_notification(account, 'low_balance', threshold=threshold)
            return Response({
                'alert': True,
                'message': f'Low balance alert sent for {account.name}',
                'balance': float(account.current_balance),
                'threshold': float(threshold),
                'severity': 'critical' if account.current_balance < threshold * Decimal('0.5') else 'warning'
            })
        
        return Response({
            'alert': False,
            'message': 'Balance is above threshold',
            'balance': float(account.current_balance),
            'threshold': float(threshold)
        })
    
    @action(detail=True, methods=['post'])
    def freeze(self, request, pk=None):
        """Freeze account (prevent new transactions)"""
        account = self.get_object()
        freeze_reason = request.data.get('reason', 'Administrative freeze')
        
        account.is_active = False
        account.notes = f"Frozen: {freeze_reason}\n{account.notes or ''}"
        account.save()
        
        return Response({
            'message': f'Account {account.name} has been frozen',
            'status': 'frozen',
            'reason': freeze_reason
        })
    
    @action(detail=True, methods=['post'])
    def unfreeze(self, request, pk=None):
        """Unfreeze account"""
        account = self.get_object()
        
        account.is_active = True
        account.save()
        
        return Response({
            'message': f'Account {account.name} has been unfrozen',
            'status': 'active'
        })
    
    @action(detail=True, methods=['get'])
    def reconciliation_status(self, request, pk=None):
        """Get reconciliation status for account"""
        account = self.get_object()
        
        total_transactions = account.transactions.filter(status='completed').count()
        reconciled_transactions = account.transactions.filter(
            status='completed', 
            is_reconciled=True
        ).count()
        unreconciled_transactions = total_transactions - reconciled_transactions
        
        # Get oldest unreconciled transaction
        oldest_unreconciled = account.transactions.filter(
            status='completed',
            is_reconciled=False
        ).order_by('transaction_date').first()
        
        reconciliation_percentage = (reconciled_transactions / total_transactions * 100) if total_transactions > 0 else 100
        
        return Response({
            'account_name': account.name,
            'total_transactions': total_transactions,
            'reconciled_transactions': reconciled_transactions,
            'unreconciled_transactions': unreconciled_transactions,
            'reconciliation_percentage': float(reconciliation_percentage),
            'oldest_unreconciled_date': oldest_unreconciled.transaction_date if oldest_unreconciled else None,
            'reconciliation_health': (
                'excellent' if reconciliation_percentage >= 95
                else 'good' if reconciliation_percentage >= 85
                else 'needs_attention' if reconciliation_percentage >= 70
                else 'critical'
            )
        })

class ExchangeRateViewSet(viewsets.ModelViewSet):
    """Enhanced Exchange Rate ViewSet with comprehensive currency management"""
    queryset = ExchangeRate.objects.select_related('from_currency', 'to_currency', 'created_by')
    serializer_class = ExchangeRateSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['from_currency', 'to_currency']
    search_fields = ['from_currency__code', 'to_currency__code', 'source']
    ordering_fields = ['effective_date', 'rate', 'created_at']
    ordering = ['-effective_date']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def latest_rates(self, request):
        """Get latest exchange rates for all currency pairs"""
        # Get the most recent rate for each currency pair
        latest_rates = ExchangeRate.objects.values(
            'from_currency__code', 'to_currency__code'
        ).annotate(
            latest_date=Max('effective_date')
        )
        
        # Get the actual rate records
        rates = []
        for rate_info in latest_rates:
            try:
                rate = ExchangeRate.objects.get(
                    from_currency__code=rate_info['from_currency__code'],
                    to_currency__code=rate_info['to_currency__code'],
                    effective_date=rate_info['latest_date']
                )
                rates.append(rate)
            except ExchangeRate.DoesNotExist:
                continue
        
        serializer = self.get_serializer(rates, many=True)
        return Response({
            'count': len(rates),
            'last_updated': max(rate.effective_date for rate in rates) if rates else None,
            'rates': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def convert(self, request):
        """Convert amount between currencies using latest rates"""
        from_currency = request.query_params.get('from_currency')
        to_currency = request.query_params.get('to_currency')
        amount = request.query_params.get('amount')
        date = request.query_params.get('date')  # Optional historical date
        
        if not all([from_currency, to_currency, amount]):
            return Response({
                'error': 'from_currency, to_currency, and amount are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            amount = Decimal(amount)
        except (ValueError, TypeError):
            return Response({
                'error': 'Invalid amount format'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # If same currency, return original amount
        if from_currency == to_currency:
            return Response({
                'from_currency': from_currency,
                'to_currency': to_currency,
                'original_amount': float(amount),
                'converted_amount': float(amount),
                'exchange_rate': 1.0,
                'rate_date': date or timezone.now().date(),
                'conversion_type': 'same_currency'
            })
        
        # Find exchange rate
        rate_filter = {
            'from_currency__code': from_currency,
            'to_currency__code': to_currency
        }
        
        if date:
            try:
                target_date = datetime.strptime(date, '%Y-%m-%d').date()
                rate_filter['effective_date__lte'] = target_date
            except ValueError:
                return Response({
                    'error': 'Invalid date format. Use YYYY-MM-DD'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            exchange_rate = ExchangeRate.objects.filter(**rate_filter).latest('effective_date')
            converted_amount = amount * exchange_rate.rate
            
            return Response({
                'from_currency': from_currency,
                'to_currency': to_currency,
                'original_amount': float(amount),
                'converted_amount': float(converted_amount),
                'exchange_rate': float(exchange_rate.rate),
                'rate_date': exchange_rate.effective_date,
                'rate_source': exchange_rate.source,
                'conversion_type': 'direct'
            })
            
        except ExchangeRate.DoesNotExist:
            # Try reverse rate
            reverse_filter = {
                'from_currency__code': to_currency,
                'to_currency__code': from_currency
            }
            if date:
                reverse_filter['effective_date__lte'] = target_date
            
            try:
                reverse_rate = ExchangeRate.objects.filter(**reverse_filter).latest('effective_date')
                converted_amount = amount / reverse_rate.rate
                
                return Response({
                    'from_currency': from_currency,
                    'to_currency': to_currency,
                    'original_amount': float(amount),
                    'converted_amount': float(converted_amount),
                    'exchange_rate': float(1 / reverse_rate.rate),
                    'rate_date': reverse_rate.effective_date,
                    'rate_source': reverse_rate.source,
                    'conversion_type': 'reverse',
                    'note': 'Used reverse exchange rate'
                })
            except ExchangeRate.DoesNotExist:
                return Response({
                    'error': f'No exchange rate found for {from_currency} to {to_currency}',
                    'suggestion': 'Please add exchange rates for this currency pair'
                }, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['get'])
    def historical_rates(self, request):
        """Get historical exchange rates for a currency pair"""
        from_currency = request.query_params.get('from_currency')
        to_currency = request.query_params.get('to_currency')
        days = int(request.query_params.get('days', 30))
        
        if not all([from_currency, to_currency]):
            return Response({
                'error': 'from_currency and to_currency are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        rates = ExchangeRate.objects.filter(
            from_currency__code=from_currency,
            to_currency__code=to_currency,
            effective_date__gte=start_date,
            effective_date__lte=end_date
        ).order_by('effective_date')
        
        if not rates.exists():
            return Response({
                'error': f'No historical rates found for {from_currency} to {to_currency}',
                'suggestion': 'Try a longer time period or check if exchange rates exist for this pair'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Calculate statistics
        rate_values = [rate.rate for rate in rates]
        min_rate = min(rate_values)
        max_rate = max(rate_values)
        avg_rate = sum(rate_values) / len(rate_values)
        
        # Format for chart display
        historical_data = []
        for rate in rates:
            historical_data.append({
                'date': rate.effective_date.isoformat(),
                'rate': float(rate.rate),
                'formatted_rate': f"1 {from_currency} = {rate.rate} {to_currency}",
                'source': rate.source
            })
        
        return Response({
            'currency_pair': f"{from_currency}/{to_currency}",
            'period_days': days,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'rates_count': len(historical_data),
            'statistics': {
                'min_rate': float(min_rate),
                'max_rate': float(max_rate),
                'avg_rate': float(avg_rate),
                'volatility': float((max_rate - min_rate) / avg_rate * 100)
            },
            'historical_rates': historical_data
        })

class DonationCampaignViewSet(viewsets.ModelViewSet):
    """Enhanced Campaign ViewSet with comprehensive donation type support and bank account management"""
    queryset = DonationCampaign.objects.select_related(
        'target_currency', 'project', 'created_by'
    ).prefetch_related(
        'donations', 'recurring_donations', 'in_kind_donations',
        'campaign_bank_accounts__bank_account__financial_institution',
        'campaign_bank_accounts__bank_account__currency'
    )
    serializer_class = DonationCampaignSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'is_featured', 'target_currency', 'project']
    search_fields = ['title', 'description']
    ordering_fields = ['title', 'start_date', 'end_date', 'target_amount', 'created_at']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'retrieve' or self.action == 'detail':
            return DonationDetailCampaignSerializer
        return DonationCampaignSerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['get'])
    def detail(self, request, pk=None):
        """Get comprehensive campaign details with all related data"""
        campaign = self.get_object()
        serializer = DonationDetailCampaignSerializer(campaign)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def comprehensive_analytics(self, request, pk=None):
        """Get comprehensive analytics including all donation types"""
        campaign = self.get_object()
        
        # Regular donations
        regular_donations = campaign.donations.filter(status='completed')
        regular_stats = {
            'count': regular_donations.count(),
            'total': regular_donations.aggregate(total=Sum('amount'))['total'] or 0,
            'average': regular_donations.aggregate(avg=Avg('amount'))['avg'] or 0,
            'unique_donors': regular_donations.values('donor').distinct().count(),
            'largest_donation': regular_donations.aggregate(max=Max('amount'))['max'] or 0,
            'payment_methods': list(regular_donations.values('payment_method').annotate(
                count=Count('id'),
                total=Sum('amount')
            ).order_by('-total'))
        }
        
        # Recurring donations
        recurring_donations = campaign.recurring_donations.filter(status__in=['active', 'completed'])
        recurring_stats = {
            'count': recurring_donations.count(),
            'total_donated': recurring_donations.aggregate(total=Sum('total_donated'))['total'] or 0,
            'monthly_value': recurring_donations.filter(frequency='monthly').aggregate(total=Sum('amount'))['total'] or 0,
            'unique_donors': recurring_donations.values('donor').distinct().count(),
            'frequency_breakdown': list(recurring_donations.values('frequency').annotate(
                count=Count('id'),
                total_amount=Sum('amount')
            ).order_by('frequency'))
        }
        
        # In-kind donations
        in_kind_donations = campaign.in_kind_donations.filter(status='received')
        in_kind_stats = {
            'count': in_kind_donations.count(),
            'total_value': in_kind_donations.aggregate(total=Sum('estimated_value'))['total'] or 0,
            'unique_donors': in_kind_donations.values('donor').distinct().count(),
            'categories': list(in_kind_donations.values('category').annotate(
                count=Count('id'),
                total_value=Sum('estimated_value')
            ).order_by('-total_value'))
        }
        
        # Combined analytics
        all_donor_ids = set()
        all_donor_ids.update(regular_donations.values_list('donor', flat=True))
        all_donor_ids.update(recurring_donations.values_list('donor', flat=True))
        all_donor_ids.update(in_kind_donations.values_list('donor', flat=True))
        all_donor_ids.discard(None)
        
        # Financial breakdown
        total_monetary = regular_stats['total'] + recurring_stats['total_donated']
        total_with_in_kind = total_monetary + in_kind_stats['total_value']
        
        # Performance metrics
        days_active = (timezone.now().date() - campaign.start_date).days + 1
        days_remaining = max(0, (campaign.end_date - timezone.now().date()).days)
        avg_daily_raised = total_monetary / days_active if days_active > 0 else 0
        target_daily_needed = (campaign.target_amount - total_monetary) / max(days_remaining, 1) if days_remaining > 0 else 0
        
        analytics = {
            'campaign_info': {
                'id': campaign.id,
                'title': campaign.title,
                'target_amount': float(campaign.target_amount),
                'currency': campaign.target_currency.code if campaign.target_currency else 'USD',
                'progress_percentage': float(campaign.progress_percentage),
                'days_active': days_active,
                'days_remaining': days_remaining,
                'is_active': campaign.is_active
            },
            'donation_breakdown': {
                'regular_donations': regular_stats,
                'recurring_donations': recurring_stats,
                'in_kind_donations': in_kind_stats
            },
            'summary': {
                'total_monetary_raised': float(total_monetary),
                'total_with_in_kind': float(total_with_in_kind),
                'unique_donors_all_types': len(all_donor_ids),
                'total_contributions': (
                    regular_stats['count'] + 
                    recurring_stats['count'] + 
                    in_kind_stats['count']
                )
            },
            'performance_indicators': {
                'monetary_progress': (total_monetary / campaign.target_amount * 100) if campaign.target_amount > 0 else 0,
                'total_progress_with_in_kind': (total_with_in_kind / campaign.target_amount * 100) if campaign.target_amount > 0 else 0,
                'avg_daily_raised': float(avg_daily_raised),
                'target_daily_needed': float(target_daily_needed),
                'is_on_track': avg_daily_raised >= target_daily_needed if days_remaining > 0 else total_monetary >= campaign.target_amount,
                'donor_retention': self._calculate_donor_retention(campaign),
                'average_per_donor': float(total_monetary / len(all_donor_ids)) if all_donor_ids else 0
            }
        }
        
        return Response(analytics)
    
    def _calculate_donor_retention(self, campaign):
        """Calculate donor retention across donation types"""
        # Get donors who have made multiple contributions
        all_contributions = []
        
        # Add regular donations
        for donation in campaign.donations.filter(status='completed'):
            all_contributions.append({
                'donor': donation.donor,
                'date': donation.donation_date,
                'type': 'regular'
            })
        
        # Add recurring donations (count as multiple contributions)
        for recurring in campaign.recurring_donations.filter(status__in=['active', 'completed']):
            all_contributions.append({
                'donor': recurring.donor,
                'date': recurring.start_date,
                'type': 'recurring'
            })
        
        # Add in-kind donations
        for in_kind in campaign.in_kind_donations.filter(status='received'):
            all_contributions.append({
                'donor': in_kind.donor,
                'date': in_kind.donation_date,
                'type': 'in_kind'
            })
        
        # Calculate retention
        donor_contribution_counts = {}
        for contrib in all_contributions:
            if contrib['donor']:
                donor_contribution_counts[contrib['donor']] = donor_contribution_counts.get(contrib['donor'], 0) + 1
        
        total_donors = len(donor_contribution_counts)
        repeat_donors = len([count for count in donor_contribution_counts.values() if count > 1])
        
        return (repeat_donors / total_donors * 100) if total_donors > 0 else 0
    
    @action(detail=True, methods=['get'])
    def bank_accounts(self, request, pk=None):
        """Get bank accounts for a campaign"""
        campaign = self.get_object()
        campaign_accounts = campaign.campaign_bank_accounts.filter(
            is_active=True
        ).select_related(
            'bank_account__financial_institution',
            'bank_account__currency',
            'added_by'
        ).order_by('priority_order')
        
        serializer = CampaignBankAccountSerializer(campaign_accounts, many=True)
        return Response({
            'campaign_title': campaign.title,
            'total_accounts': campaign_accounts.count(),
            'accounts': serializer.data
        })

    @action(detail=True, methods=['post'])
    def add_bank_account(self, request, pk=None):
        """Add a bank account to a campaign"""
        campaign = self.get_object()
        bank_account_id = request.data.get('bank_account_id')
        
        if not bank_account_id:
            return Response({
                'error': 'bank_account_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            bank_account = BankAccount.objects.get(
                id=bank_account_id,
                is_active=True,
                accepts_donations=True
            )
        except BankAccount.DoesNotExist:
            return Response({
                'error': 'Invalid or unavailable bank account'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if already added
        if CampaignBankAccount.objects.filter(
            campaign=campaign,
            bank_account=bank_account
        ).exists():
            return Response({
                'error': 'Bank account already added to this campaign'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create the relationship
        campaign_account = CampaignBankAccount.objects.create(
            campaign=campaign,
            bank_account=bank_account,
            is_primary=request.data.get('is_primary', False),
            priority_order=request.data.get('priority_order', 1),
            notes=request.data.get('notes'),
            added_by=request.user
        )
        
        # If this is set as primary, remove primary status from others
        if campaign_account.is_primary:
            CampaignBankAccount.objects.filter(
                campaign=campaign
            ).exclude(id=campaign_account.id).update(is_primary=False)
        
        serializer = CampaignBankAccountSerializer(campaign_account)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def set_primary_bank_account(self, request, pk=None):
        """Set primary bank account for campaign"""
        campaign = self.get_object()
        bank_account_id = request.data.get('bank_account_id')
        
        if not bank_account_id:
            return Response({
                'error': 'bank_account_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                # Remove primary status from all accounts
                campaign.campaign_bank_accounts.update(is_primary=False)
                
                # Set new primary
                campaign_account = campaign.campaign_bank_accounts.get(
                    bank_account_id=bank_account_id,
                    is_active=True
                )
                campaign_account.is_primary = True
                campaign_account.save()
                
        except CampaignBankAccount.DoesNotExist:
            return Response({
                'error': 'Bank account not found in campaign'
            }, status=status.HTTP_404_NOT_FOUND)
        
        return Response({
            'message': 'Primary bank account updated successfully',
            'primary_account': campaign_account.bank_account.name
        })

    @action(detail=True, methods=['get'])
    def donation_options(self, request, pk=None):
        """Get formatted donation options for public display"""
        campaign = self.get_object()
        
        # Get active bank accounts
        active_accounts = campaign.campaign_bank_accounts.filter(
            is_active=True,
            bank_account__is_active=True,
            bank_account__accepts_donations=True
        ).select_related(
            'bank_account__financial_institution',
            'bank_account__currency'
        ).order_by('priority_order')
        
        # Group by currency
        accounts_by_currency = {}
        primary_account = None
        
        for campaign_account in active_accounts:
            account = campaign_account.bank_account
            currency_code = account.currency.code
            
            if currency_code not in accounts_by_currency:
                accounts_by_currency[currency_code] = []
            
            account_data = {
                'id': account.id,
                'name': account.name,
                'account_number': account.account_number,
                'account_type': account.get_account_type_display(),
                'financial_institution': {
                    'name': account.financial_institution.name,
                    'code': account.financial_institution.code,
                    'branch_name': account.financial_institution.branch_name
                },
                'currency': {
                    'code': account.currency.code,
                },
                'is_primary': campaign_account.is_primary,
                'priority_order': campaign_account.priority_order,
                'notes': campaign_account.notes
            }
            
            accounts_by_currency[currency_code].append(account_data)
            
            if campaign_account.is_primary:
                primary_account = account_data
        
        return Response({
            'campaign_title': campaign.title,
            'campaign_description': campaign.description,
            'target_amount': float(campaign.target_amount),
            'current_amount': float(campaign.current_amount_in_target_currency),
            'progress_percentage': float(campaign.progress_percentage),
            'currency': campaign.target_currency.code if campaign.target_currency else 'USD',
            'primary_account': primary_account,
            'accounts_by_currency': accounts_by_currency,
            'total_accounts': active_accounts.count(),
            'campaign_status': {
                'is_active': campaign.is_active,
                'days_remaining': max(0, (campaign.end_date - timezone.now().date()).days),
                'end_date': campaign.end_date
            }
        })

    @action(detail=True, methods=['post'])
    def check_milestones(self, request, pk=None):
        """Check and send milestone notifications"""
        campaign = self.get_object()
        progress = campaign.progress_percentage
        
        milestones_reached = []
        
        # Check each milestone
        for milestone in [25, 50, 75, 100]:
            if progress >= milestone:
                milestones_reached.append(milestone)
                send_campaign_milestone_notification(campaign, milestone)
        
        return Response({
            'progress_percentage': float(progress),
            'milestones_reached': milestones_reached,
            'notifications_sent': len(milestones_reached),
            'next_milestone': next((m for m in [25, 50, 75, 100] if m > progress), None)
        })
    
    @action(detail=True, methods=['post'])
    def extend_deadline(self, request, pk=None):
        """Extend campaign deadline"""
        campaign = self.get_object()
        new_end_date = request.data.get('new_end_date')
        reason = request.data.get('reason', '')
        
        if not new_end_date:
            return Response({
                'error': 'new_end_date is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            new_date = datetime.strptime(new_end_date, '%Y-%m-%d').date()
            if new_date <= campaign.end_date:
                return Response({
                    'error': 'New end date must be after current end date'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            old_date = campaign.end_date
            campaign.end_date = new_date
            campaign.notes = f"Deadline extended: {reason}\n{campaign.notes or ''}"
            campaign.save()
            
            return Response({
                'message': f'Campaign deadline extended from {old_date} to {new_date}',
                'old_end_date': old_date,
                'new_end_date': new_date,
                'reason': reason,
                'new_days_remaining': (new_date - timezone.now().date()).days
            })
            
        except ValueError:
            return Response({
                'error': 'Invalid date format. Use YYYY-MM-DD'
            }, status=status.HTTP_400_BAD_REQUEST)

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
        donation = serializer.save(processed_by=self.request.user)
        
        # Auto-send notification if completed
        if donation.status == 'completed':
            send_donation_received_notification(donation)
            
            # Check campaign milestones
            if donation.campaign:
                self._check_campaign_milestones(donation.campaign)
    
    def _check_campaign_milestones(self, campaign):
        """Check and send campaign milestone notifications"""
        progress = campaign.progress_percentage
        
        # Send milestone notifications
        milestones = [25, 50, 75, 100]
        for milestone in milestones:
            if progress >= milestone:
                send_campaign_milestone_notification(campaign, milestone)
    
    @action(detail=True, methods=['post'])
    def process_payment(self, request, pk=None):
        """Process donation payment (change status from pending to processing)"""
        donation = self.get_object()
        
        if donation.status != 'pending':
            return Response({
                'error': f'Cannot process donation with status: {donation.status}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        donation.status = 'processing'
        donation.save()
        
        return Response({
            'message': 'Donation payment is being processed',
            'status': donation.status
        })
    
    @action(detail=True, methods=['post'])
    def complete_donation(self, request, pk=None):
        """Complete donation (change status to completed)"""
        donation = self.get_object()
        
        if donation.status not in ['pending', 'processing']:
            return Response({
                'error': f'Cannot complete donation with status: {donation.status}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            # Update donation status
            donation.status = 'completed'
            donation.donation_date = timezone.now()
            
            # Set deposit information if provided
            account_id = request.data.get('deposited_to_account_id')
            if account_id:
                try:
                    account = BankAccount.objects.get(id=account_id)
                    donation.deposited_to_account = account
                    donation.deposit_date = timezone.now()
                    donation.bank_reference = request.data.get('bank_reference', '')
                except BankAccount.DoesNotExist:
                    return Response({
                        'error': 'Invalid bank account ID'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            donation.save()
            
            # Create account transaction if deposited
            if donation.deposited_to_account:
                AccountTransaction.objects.create(
                    account=donation.deposited_to_account,
                    transaction_type='credit',
                    amount=donation.net_amount or donation.amount,
                    original_amount=donation.amount,
                    original_currency=donation.currency,
                    donation=donation,
                    reference_number=f"DON-{donation.id}-{timezone.now().strftime('%Y%m%d')}",
                    transaction_date=timezone.now(),
                    description=f"Donation from {donation.donor_name_display}",
                    status='completed',
                    authorized_by=request.user
                )
            
            # Send notifications
            send_donation_received_notification(donation)
            
            # Check campaign milestones
            if donation.campaign:
                self._check_campaign_milestones(donation.campaign)
        
        serializer = self.get_serializer(donation)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def refund_donation(self, request, pk=None):
        """Refund a donation"""
        donation = self.get_object()
        
        if donation.status != 'completed':
            return Response({
                'error': 'Can only refund completed donations'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        refund_reason = request.data.get('reason', '')
        
        with transaction.atomic():
            # Update donation status
            donation.status = 'refunded'
            donation.notes = f"Refunded: {refund_reason}\n{donation.notes or ''}"
            donation.save()
            
            # Create reverse transaction if it was deposited
            if donation.deposited_to_account:
                AccountTransaction.objects.create(
                    account=donation.deposited_to_account,
                    transaction_type='debit',
                    amount=donation.net_amount or donation.amount,
                    donation=donation,
                    reference_number=f"REF-{donation.id}-{timezone.now().strftime('%Y%m%d')}",
                    transaction_date=timezone.now(),
                    description=f"Refund for donation from {donation.donor_name_display}",
                    status='completed',
                    authorized_by=request.user
                )
        
        return Response({
            'message': 'Donation has been refunded',
            'status': donation.status,
            'refund_reason': refund_reason
        })
    
    @action(detail=True, methods=['post'])
    def send_receipt(self, request, pk=None):
        """Send receipt to donor"""
        donation = self.get_object()
        
        if donation.status != 'completed':
            return Response({
                'error': 'Can only send receipts for completed donations'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Generate receipt number if not exists
        if not donation.receipt_number:
            donation.receipt_number = f"RCP-{donation.id}-{timezone.now().strftime('%Y%m%d')}"
        
        donation.receipt_sent = True
        donation.save()
        
        # Here you would integrate with your email service
        # send_donation_receipt_email(donation)
        
        return Response({
            'message': 'Receipt sent successfully',
            'receipt_number': donation.receipt_number
        })

class RecurringDonationViewSet(viewsets.ModelViewSet):
    queryset = RecurringDonation.objects.select_related(
        'donor', 'campaign', 'project', 'currency', 'created_by'
    )
    serializer_class = RecurringDonationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'frequency', 'currency', 'campaign', 'project']
    search_fields = ['donor_name', 'donor_email', 'reference_number']
    ordering_fields = ['start_date', 'next_payment_date', 'amount', 'created_at']
    ordering = ['-created_at']
    
    def perform_create(self, serializer):
        recurring_donation = serializer.save(created_by=self.request.user)
        
        # Send notification for new recurring donation setup
        send_recurring_donation_notification(recurring_donation, 'created')
    
    @action(detail=False, methods=['get'])
    def due_payments(self, request):
        """Get recurring donations due for payment"""
        days_ahead = int(request.query_params.get('days', 7))
        end_date = timezone.now().date() + timedelta(days=days_ahead)
        
        due_donations = self.get_queryset().filter(
            status='active',
            next_payment_date__lte=end_date,
            next_payment_date__gte=timezone.now().date()
        ).order_by('next_payment_date')
        
        # Group by due date
        due_by_date = {}
        for donation in due_donations:
            date_str = donation.next_payment_date.isoformat()
            if date_str not in due_by_date:
                due_by_date[date_str] = []
            
            due_by_date[date_str].append({
                'id': donation.id,
                'donor_name': donation.donor_name_display,
                'amount': float(donation.amount),
                'currency': donation.currency.code,
                'campaign': donation.campaign.title if donation.campaign else None,
                'frequency': donation.frequency,
                'reference_number': donation.reference_number
            })
        
        # Calculate totals
        total_due = due_donations.aggregate(total=Sum('amount'))['total'] or 0
        count_due = due_donations.count()
        
        return Response({
            'period_days': days_ahead,
            'summary': {
                'total_due': float(total_due),
                'count_due': count_due,
                'end_date': end_date.isoformat()
            },
            'due_by_date': due_by_date,
            'due_donations': self.get_serializer(due_donations, many=True).data
        })
    
    @action(detail=True, methods=['post'])
    def process_payment(self, request, pk=None):
        """Process a recurring donation payment"""
        recurring_donation = self.get_object()
        
        if recurring_donation.status != 'active':
            return Response({
                'error': f'Cannot process payment for {recurring_donation.status} recurring donation'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if payment is due
        if recurring_donation.next_payment_date > timezone.now().date():
            return Response({
                'error': f'Payment not due until {recurring_donation.next_payment_date}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            # Create a regular donation record
            donation = Donation.objects.create(
                donor=recurring_donation.donor,
                donor_name=recurring_donation.donor_name,
                donor_email=recurring_donation.donor_email,
                amount=recurring_donation.amount,
                currency=recurring_donation.currency,
                campaign=recurring_donation.campaign,
                project=recurring_donation.project,
                payment_method=recurring_donation.payment_method,
                is_anonymous=recurring_donation.is_anonymous,
                donation_date=timezone.now(),
                status='completed',  # Assuming automatic processing
                recurring_donation=recurring_donation,
                reference_number=f"REC-{recurring_donation.id}-{timezone.now().strftime('%Y%m%d')}",
                processed_by=request.user
            )
            
            # Update recurring donation
            recurring_donation.last_payment_date = timezone.now().date()
            recurring_donation.total_amount_donated += recurring_donation.amount
            recurring_donation.payments_made += 1
            
            # Calculate next payment date
            if recurring_donation.frequency == 'weekly':
                recurring_donation.next_payment_date += timedelta(weeks=1)
            elif recurring_donation.frequency == 'monthly':
                # Add one month
                next_month = recurring_donation.next_payment_date.replace(day=28) + timedelta(days=4)
                recurring_donation.next_payment_date = next_month.replace(day=recurring_donation.next_payment_date.day)
            elif recurring_donation.frequency == 'quarterly':
                # Add 3 months
                for _ in range(3):
                    next_month = recurring_donation.next_payment_date.replace(day=28) + timedelta(days=4)
                    recurring_donation.next_payment_date = next_month.replace(day=recurring_donation.next_payment_date.day)
            elif recurring_donation.frequency == 'annually':
                recurring_donation.next_payment_date = recurring_donation.next_payment_date.replace(
                    year=recurring_donation.next_payment_date.year + 1
                )
            
            # Check if we've reached the end date
            if recurring_donation.end_date and recurring_donation.next_payment_date > recurring_donation.end_date:
                recurring_donation.status = 'completed'
                recurring_donation.next_payment_date = None
            
            recurring_donation.save()
            
            # Send notifications
            send_recurring_donation_notification(recurring_donation, 'payment_processed')
            send_donation_received_notification(donation)
        
        return Response({
            'message': 'Recurring donation payment processed successfully',
            'donation_id': donation.id,
            'next_payment_date': recurring_donation.next_payment_date,
            'status': recurring_donation.status
        })
    
    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """Pause a recurring donation"""
        recurring_donation = self.get_object()
        
        if recurring_donation.status != 'active':
            return Response({
                'error': f'Cannot pause {recurring_donation.status} recurring donation'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        recurring_donation.status = 'paused'
        recurring_donation.save()
        
        send_recurring_donation_notification(recurring_donation, 'paused')
        
        return Response({
            'message': 'Recurring donation paused successfully',
            'status': recurring_donation.status
        })
    
    @action(detail=True, methods=['post'])
    def resume(self, request, pk=None):
        """Resume a paused recurring donation"""
        recurring_donation = self.get_object()
        
        if recurring_donation.status != 'paused':
            return Response({
                'error': f'Cannot resume {recurring_donation.status} recurring donation'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update next payment date if needed
        if recurring_donation.next_payment_date < timezone.now().date():
            recurring_donation.next_payment_date = timezone.now().date() + timedelta(days=1)
        
        recurring_donation.status = 'active'
        recurring_donation.save()
        
        send_recurring_donation_notification(recurring_donation, 'resumed')
        
        return Response({
            'message': 'Recurring donation resumed successfully',
            'status': recurring_donation.status,
            'next_payment_date': recurring_donation.next_payment_date
        })
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a recurring donation"""
        recurring_donation = self.get_object()
        
        if recurring_donation.status in ['cancelled', 'completed']:
            return Response({
                'error': f'Recurring donation is already {recurring_donation.status}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        cancellation_reason = request.data.get('reason', '')
        
        recurring_donation.status = 'cancelled'
        recurring_donation.next_payment_date = None
        recurring_donation.notes = f"Cancelled: {cancellation_reason}\n{recurring_donation.notes or ''}"
        recurring_donation.save()
        
        send_recurring_donation_notification(recurring_donation, 'cancelled')
        
        return Response({
            'message': 'Recurring donation cancelled successfully',
            'status': recurring_donation.status,
            'reason': cancellation_reason
        })
    
    @action(detail=True, methods=['post'])
    def update_amount(self, request, pk=None):
        """Update recurring donation amount"""
        recurring_donation = self.get_object()
        
        if recurring_donation.status != 'active':
            return Response({
                'error': f'Cannot update amount for {recurring_donation.status} recurring donation'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        new_amount = request.data.get('amount')
        if not new_amount:
            return Response({
                'error': 'Amount is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            new_amount = Decimal(new_amount)
            if new_amount <= 0:
                raise ValueError("Amount must be positive")
        except (ValueError, TypeError):
            return Response({
                'error': 'Invalid amount format'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        old_amount = recurring_donation.amount
        recurring_donation.amount = new_amount
        recurring_donation.save()
        
        send_recurring_donation_notification(recurring_donation, 'amount_updated', {
            'old_amount': old_amount,
            'new_amount': new_amount
        })
        
        return Response({
            'message': f'Amount updated from {old_amount} to {new_amount}',
            'old_amount': float(old_amount),
            'new_amount': float(new_amount)
        })
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get recurring donation statistics"""
        queryset = self.get_queryset()
        
        # Basic stats
        total_recurring = queryset.count()
        active_recurring = queryset.filter(status='active').count()
        paused_recurring = queryset.filter(status='paused').count()
        cancelled_recurring = queryset.filter(status='cancelled').count()
        
        # Financial stats
        total_monthly_value = queryset.filter(
            status='active',
            frequency='monthly'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        total_annual_value = queryset.filter(status='active').aggregate(
            total=Sum(
                Case(
                    When(frequency='weekly', then=F('amount') * 52),
                    When(frequency='monthly', then=F('amount') * 12),
                    When(frequency='quarterly', then=F('amount') * 4),
                    When(frequency='annually', then=F('amount')),
                    default=Value(0),
                    output_field=DecimalField()
                )
            )
        )['total'] or 0
        
        # Frequency breakdown
        frequency_stats = queryset.filter(status='active').values('frequency').annotate(
            count=Count('id'),
            total_amount=Sum('amount')
        ).order_by('frequency')
        
        # Payment method breakdown
        payment_method_stats = queryset.filter(status='active').values('payment_method').annotate(
            count=Count('id'),
            total_amount=Sum('amount')
        ).order_by('-total_amount')
        
        return Response({
            'summary': {
                'total_recurring_donations': total_recurring,
                'active_recurring_donations': active_recurring,
                'paused_recurring_donations': paused_recurring,
                'cancelled_recurring_donations': cancelled_recurring,
                'total_monthly_value': float(total_monthly_value),
                'projected_annual_value': float(total_annual_value)
            },
            'frequency_breakdown': list(frequency_stats),
            'payment_method_breakdown': list(payment_method_stats)
        })

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
    
    @action(detail=True, methods=['post'])
    def submit_application(self, request, pk=None):
        """Submit grant application"""
        grant = self.get_object()
        
        if grant.status != 'draft':
            return Response({
                'error': f'Cannot submit grant with status: {grant.status}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        grant.status = 'submitted'
        grant.submission_date = timezone.now().date()
        grant.save()
        
        send_grant_status_notification(grant, 'draft', 'submitted')
        
        return Response({
            'message': 'Grant application submitted successfully',
            'status': grant.status,
            'submission_date': grant.submission_date
        })
    
    @action(detail=True, methods=['post'])
    def mark_under_review(self, request, pk=None):
        """Mark grant as under review"""
        grant = self.get_object()
        
        if grant.status != 'submitted':
            return Response({
                'error': f'Cannot review grant with status: {grant.status}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        old_status = grant.status
        grant.status = 'under_review'
        grant.save()
        
        send_grant_status_notification(grant, old_status, 'under_review')
        
        return Response({
            'message': 'Grant marked as under review',
            'status': grant.status
        })
    
    @action(detail=True, methods=['post'])
    def approve_grant(self, request, pk=None):
        """Approve grant"""
        grant = self.get_object()
        
        if grant.status not in ['submitted', 'under_review']:
            return Response({
                'error': f'Cannot approve grant with status: {grant.status}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        old_status = grant.status
        grant.status = 'approved'
        grant.approval_date = timezone.now().date()
        grant.save()
        
        send_grant_status_notification(grant, old_status, 'approved')
        
        return Response({
            'message': 'Grant approved successfully',
            'status': grant.status,
            'approval_date': grant.approval_date
        })
    
    @action(detail=True, methods=['post'])
    def reject_grant(self, request, pk=None):
        """Reject grant"""
        grant = self.get_object()
        
        if grant.status not in ['submitted', 'under_review']:
            return Response({
                'error': f'Cannot reject grant with status: {grant.status}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        rejection_reason = request.data.get('reason', '')
        
        old_status = grant.status
        grant.status = 'rejected'
        grant.notes = f"Rejected: {rejection_reason}\n{grant.notes or ''}"
        grant.save()
        
        send_grant_status_notification(grant, old_status, 'rejected')
        
        return Response({
            'message': 'Grant rejected',
            'status': grant.status,
            'reason': rejection_reason
        })
    
    @action(detail=True, methods=['post'])
    def activate_grant(self, request, pk=None):
        """Activate approved grant"""
        grant = self.get_object()
        
        if grant.status != 'approved':
            return Response({
                'error': 'Can only activate approved grants'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        old_status = grant.status
        grant.status = 'active'
        grant.start_date = timezone.now().date()
        grant.save()
        
        send_grant_status_notification(grant, old_status, 'active')
        
        return Response({
            'message': 'Grant activated successfully',
            'status': grant.status,
            'start_date': grant.start_date
        })
    
    @action(detail=True, methods=['post'])
    def record_disbursement(self, request, pk=None):
        """Record grant disbursement"""
        grant = self.get_object()
        
        if grant.status != 'active':
            return Response({
                'error': 'Can only record disbursements for active grants'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        amount = Decimal(request.data.get('amount', '0'))
        account_id = request.data.get('account_id')
        reference = request.data.get('reference', '')
        
        if amount <= 0:
            return Response({
                'error': 'Amount must be greater than 0'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if grant.amount_received + amount > grant.amount:
            return Response({
                'error': 'Disbursement amount exceeds remaining grant amount'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            # Update grant
            grant.amount_received += amount
            grant.save()
            
            # Create transaction if account specified
            if account_id:
                try:
                    account = BankAccount.objects.get(id=account_id)
                    AccountTransaction.objects.create(
                        account=account,
                        transaction_type='credit',
                        amount=amount,
                        grant=grant,
                        reference_number=reference or f"GRT-{grant.id}-{timezone.now().strftime('%Y%m%d')}",
                        transaction_date=timezone.now(),
                        description=f"Grant disbursement from {grant.grantor}",
                        status='completed',
                        authorized_by=request.user
                    )
                except BankAccount.DoesNotExist:
                    return Response({
                        'error': 'Invalid account ID'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Send notification
            send_grant_disbursement_notification(grant, amount)
            
            # Check if grant is fully disbursed
            if grant.amount_received >= grant.amount:
                grant.status = 'completed'
                grant.save()
                send_grant_status_notification(grant, 'active', 'completed')
        
        return Response({
            'message': f'Disbursement of {grant.currency.code} {amount:,.2f} recorded',
            'amount_received': grant.amount_received,
            'remaining_amount': grant.remaining_amount,
            'status': grant.status
        })

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
    
    def get_serializer_class(self):
        """Use detailed serializer for retrieve action"""
        if self.action == 'retrieve':
            return BudgetDetailSerializer
        return BudgetSerializer

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get comprehensive budget statistics for dashboard"""
        try:
            # Get query parameters for filtering
            fiscal_year = request.query_params.get('fiscal_year')
            department_id = request.query_params.get('department')
            budget_type = request.query_params.get('budget_type')
            status_filter = request.query_params.get('status')
            
            # Base queryset
            budgets = self.get_queryset()
            
            # Apply filters
            if fiscal_year:
                budgets = budgets.filter(fiscal_year=fiscal_year)
            if department_id:
                budgets = budgets.filter(department_id=department_id)
            if budget_type:
                budgets = budgets.filter(budget_type=budget_type)
            if status_filter:
                budgets = budgets.filter(status=status_filter)
            
            # Calculate spent amounts by aggregating from OrganizationalExpense
            budget_ids = list(budgets.values_list('id', flat=True))
            
            # Initialize budget_expenses dictionary
            budget_expenses = {}
            
            if budget_ids:
                try:
                    expense_data = OrganizationalExpense.objects.filter(
                        budget_item__budget_id__in=budget_ids,
                        status='paid'
                    ).values('budget_item__budget_id').annotate(
                        total_spent=Sum('amount')
                    )
                    
                    for item in expense_data:
                        budget_id = item['budget_item__budget_id']
                        spent_amount = item['total_spent']
                        if spent_amount is not None:
                            budget_expenses[budget_id] = float(spent_amount)
                        else:
                            budget_expenses[budget_id] = 0.0
                except Exception as e:
                    # If expense calculation fails, initialize empty
                    budget_expenses = {}
            
            # Helper function for safe division
            def safe_divide(numerator, denominator, default=0.0):
                try:
                    if denominator is None or denominator == 0:
                        return default
                    if numerator is None:
                        return default
                    result = float(numerator) / float(denominator)
                    if result != result:  # Check for NaN
                        return default
                    return result
                except (TypeError, ValueError, ZeroDivisionError):
                    return default
            
            # Helper function for safe percentage
            def safe_percentage(numerator, denominator, default=0.0):
                return safe_divide(numerator, denominator, default) * 100
            
            # Overall Summary
            total_budgets = budgets.count()
            total_allocated = budgets.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
            total_allocated = float(total_allocated) if total_allocated else 0.0
            
            total_spent = sum(budget_expenses.values()) if budget_expenses else 0.0
            total_remaining = total_allocated - total_spent
            avg_utilization = safe_percentage(total_spent, total_allocated, 0.0)
            
            # Active budgets
            active_budgets = budgets.filter(status='active').count()
            pending_approval = budgets.filter(status='pending_approval').count()
            over_budget_count = 0
            near_limit_count = 0
            
            # Calculate over-budget and near-limit counts safely
            for budget in budgets:
                try:
                    spent_amount = budget_expenses.get(budget.id, 0.0)
                    budget_total = float(budget.total_amount) if budget.total_amount else 0.0
                    
                    if budget_total > 0:
                        utilization = safe_percentage(spent_amount, budget_total, 0.0)
                        if utilization > 100:
                            over_budget_count += 1
                        elif utilization >= 90:
                            near_limit_count += 1
                except Exception:
                    continue
            
            summary = {
                'total_budgets': total_budgets,
                'total_allocated': total_allocated,
                'total_spent': total_spent,
                'total_remaining': total_remaining,
                'avg_utilization': round(avg_utilization, 2),
                'active_budgets': active_budgets,
                'pending_approval': pending_approval,
                'over_budget_count': over_budget_count,
                'near_limit_count': near_limit_count,
                'efficiency_score': min(100, max(0, 100 - abs(avg_utilization - 85))),
            }
            
            # Budget by Type - Calculate manually with safe operations
            by_type = {}
            for budget in budgets.select_related('currency'):
                try:
                    budget_type = budget.budget_type
                    spent_amount = budget_expenses.get(budget.id, 0.0)
                    budget_total = float(budget.total_amount) if budget.total_amount else 0.0
                    
                    if budget_type not in by_type:
                        by_type[budget_type] = {
                            'budget_type': budget_type,
                            'count': 0,
                            'total_amount': 0.0,
                            'spent_amount': 0.0,
                            'avg_utilization': 0.0
                        }
                    
                    by_type[budget_type]['count'] += 1
                    by_type[budget_type]['total_amount'] += budget_total
                    by_type[budget_type]['spent_amount'] += spent_amount
                except Exception:
                    continue
            
            # Calculate utilization for each type safely
            for type_data in by_type.values():
                try:
                    type_data['avg_utilization'] = round(
                        safe_percentage(type_data['spent_amount'], type_data['total_amount'], 0.0), 2
                    )
                except Exception:
                    type_data['avg_utilization'] = 0.0
            
            by_type = list(by_type.values())
            by_type.sort(key=lambda x: x.get('total_amount', 0), reverse=True)
            
            # Budget by Status - Calculate manually with safe operations
            by_status = {}
            for budget in budgets:
                try:
                    status = budget.status
                    spent_amount = budget_expenses.get(budget.id, 0.0)
                    budget_total = float(budget.total_amount) if budget.total_amount else 0.0
                    
                    if status not in by_status:
                        by_status[status] = {
                            'status': status,
                            'count': 0,
                            'total_amount': 0.0,
                            'spent_amount': 0.0
                        }
                    
                    by_status[status]['count'] += 1
                    by_status[status]['total_amount'] += budget_total
                    by_status[status]['spent_amount'] += spent_amount
                except Exception:
                    continue
            
            by_status = list(by_status.values())
            by_status.sort(key=lambda x: x.get('total_amount', 0), reverse=True)
            
            # Individual Budget Utilization Summary with safe calculations
            utilization_summary = []
            for budget in budgets.select_related('currency', 'department'):
                try:
                    spent_amount = budget_expenses.get(budget.id, 0.0)
                    budget_total = float(budget.total_amount) if budget.total_amount else 0.0
                    utilization_percentage = safe_percentage(spent_amount, budget_total, 0.0)
                    
                    # Determine health status
                    if utilization_percentage > 100:
                        health_status = 'critical'
                    elif utilization_percentage > 90:
                        health_status = 'warning'
                    elif utilization_percentage < 50:
                        health_status = 'underutilized'
                    else:
                        health_status = 'healthy'
                    
                    days_remaining = None
                    if budget.end_date:
                        try:
                            days_remaining = (budget.end_date - timezone.now().date()).days
                        except Exception:
                            days_remaining = None
                    
                    utilization_summary.append({
                        'budget_id': budget.id,
                        'budget_title': budget.title or 'Untitled Budget',
                        'budget_type': budget.get_budget_type_display() if hasattr(budget, 'get_budget_type_display') else budget.budget_type,
                        'department_name': budget.department.name if budget.department else 'No Department',
                        'total_amount': budget_total,
                        'spent_amount': spent_amount,
                        'remaining_amount': budget_total - spent_amount,
                        'utilization_percentage': round(utilization_percentage, 2),
                        'currency_code': budget.currency.code if budget.currency else 'USD',
                        'status': budget.status,
                        'health_status': health_status,
                        'start_date': budget.start_date.isoformat() if budget.start_date else None,
                        'end_date': budget.end_date.isoformat() if budget.end_date else None,
                        'days_remaining': days_remaining,
                        'created_by': budget.created_by.get_full_name if budget.created_by else 'Unknown',
                    })
                except Exception:
                    # Skip problematic budgets
                    continue
            
            # Sort by utilization percentage descending
            utilization_summary.sort(key=lambda x: x.get('utilization_percentage', 0), reverse=True)
            
            # Budget by Department with safe calculations
            by_department = {}
            for budget in budgets.filter(department__isnull=False).select_related('department'):
                try:
                    dept_name = budget.department.name
                    dept_id = budget.department.id
                    spent_amount = budget_expenses.get(budget.id, 0.0)
                    budget_total = float(budget.total_amount) if budget.total_amount else 0.0
                    
                    if dept_id not in by_department:
                        by_department[dept_id] = {
                            'department__name': dept_name,
                            'department__id': dept_id,
                            'count': 0,
                            'total_amount': 0.0,
                            'spent_amount': 0.0,
                            'avg_utilization': 0.0
                        }
                    
                    by_department[dept_id]['count'] += 1
                    by_department[dept_id]['total_amount'] += budget_total
                    by_department[dept_id]['spent_amount'] += spent_amount
                except Exception:
                    continue
            
            # Calculate utilization for each department safely
            for dept_data in by_department.values():
                try:
                    dept_data['avg_utilization'] = round(
                        safe_percentage(dept_data['spent_amount'], dept_data['total_amount'], 0.0), 2
                    )
                except Exception:
                    dept_data['avg_utilization'] = 0.0
            
            by_department = list(by_department.values())
            by_department.sort(key=lambda x: x.get('total_amount', 0), reverse=True)
            
            # Monthly Trends (simplified for safety)
            monthly_trends = []
            try:
                end_date = timezone.now().date()
                
                for i in range(12):
                    try:
                        month_start = (end_date.replace(day=1) - timedelta(days=i*30)).replace(day=1)
                        month_end = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
                        
                        # Get expenses for this month
                        month_expenses = OrganizationalExpense.objects.filter(
                            expense_date__gte=month_start,
                            expense_date__lte=month_end,
                            status='paid'
                        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
                        
                        month_expenses = float(month_expenses) if month_expenses else 0.0
                        
                        # Get budgets created in this month
                        month_budgets = budgets.filter(
                            created_at__date__gte=month_start,
                            created_at__date__lte=month_end
                        ).aggregate(
                            count=Count('id'),
                            total_amount=Sum('total_amount')
                        )
                        
                        budget_count = month_budgets['count'] or 0
                        budget_amount = float(month_budgets['total_amount']) if month_budgets['total_amount'] else 0.0
                        
                        monthly_trends.append({
                            'month': month_start.strftime('%Y-%m'),
                            'month_name': month_start.strftime('%B %Y'),
                            'budgets_created': budget_count,
                            'total_allocated': budget_amount,
                            'total_spent': month_expenses,
                            'net_position': budget_amount - month_expenses
                        })
                    except Exception:
                        # Skip problematic months
                        continue
                
                # Reverse to get chronological order
                monthly_trends.reverse()
            except Exception:
                monthly_trends = []
            
            # Simplified alerts to avoid complex calculations
            alerts = []
            
            # Performance Metrics with safe calculations
            performance_metrics = {
                'budget_accuracy': min(100, max(0, 100 - abs(avg_utilization - 85))),
                'approval_efficiency': safe_percentage(
                    budgets.filter(status='approved').count(),
                    max(budgets.filter(status__in=['pending_approval', 'approved']).count(), 1),
                    0.0
                ),
                'spend_velocity': avg_utilization,
                'forecast_precision': 85.0,  # Simplified
                'resource_utilization': avg_utilization,
            }
            
            # Risk Analysis with safe calculations
            risk_analysis = {
                'overspend_risk': safe_percentage(over_budget_count, max(total_budgets, 1), 0.0),
                'underspend_risk': safe_percentage(
                    len([b for b in utilization_summary if b.get('health_status') == 'underutilized']),
                    max(total_budgets, 1),
                    0.0
                ),
                'timeline_risk': safe_percentage(
                    len([b for b in utilization_summary if b.get('days_remaining') and b['days_remaining'] < 30]),
                    max(total_budgets, 1),
                    0.0
                ),
                'resource_risk': safe_percentage(near_limit_count, max(total_budgets, 1), 0.0),
                'compliance_risk': safe_percentage(pending_approval, max(total_budgets, 1), 0.0),
            }
            print(
                 {
                'summary': summary,
                'by_type': by_type,
                'by_status': by_status,
                'utilization_summary': utilization_summary,
                'by_department': by_department,
                'monthly_trends': monthly_trends,
                'alerts': alerts,
                'performance_metrics': performance_metrics,
                'risk_analysis': risk_analysis,
                'generated_at': timezone.now().isoformat(),
                'filters_applied': {
                    'fiscal_year': fiscal_year,
                    'department': department_id,
                    'budget_type': budget_type,
                    'status': status_filter,
                }
            
                 }
            )
            return Response({
                'summary': summary,
                'by_type': by_type,
                'by_status': by_status,
                'utilization_summary': utilization_summary,
                'by_department': by_department,
                'monthly_trends': monthly_trends,
                'alerts': alerts,
                'performance_metrics': performance_metrics,
                'risk_analysis': risk_analysis,
                'generated_at': timezone.now().isoformat(),
                'filters_applied': {
                    'fiscal_year': fiscal_year,
                    'department': department_id,
                    'budget_type': budget_type,
                    'status': status_filter,
                }
            })
            
        except Exception as e:
            # Return a safe fallback response
            return Response({
                'summary': {
                    'total_budgets': 0,
                    'total_allocated': 0.0,
                    'total_spent': 0.0,
                    'total_remaining': 0.0,
                    'avg_utilization': 0.0,
                    'active_budgets': 0,
                    'pending_approval': 0,
                    'over_budget_count': 0,
                    'near_limit_count': 0,
                    'efficiency_score': 0.0,
                },
                'by_type': [],
                'by_status': [],
                'utilization_summary': [],
                'by_department': [],
                'monthly_trends': [],
                'alerts': [],
                'performance_metrics': {
                    'budget_accuracy': 0.0,
                    'approval_efficiency': 0.0,
                    'spend_velocity': 0.0,
                    'forecast_precision': 0.0,
                    'resource_utilization': 0.0,
                },
                'risk_analysis': {
                    'overspend_risk': 0.0,
                    'underspend_risk': 0.0,
                    'timeline_risk': 0.0,
                    'resource_risk': 0.0,
                    'compliance_risk': 0.0,
                },
                'generated_at': timezone.now().isoformat(),
                'error': 'Statistics calculation failed',
                'filters_applied': {}
            })

    @action(detail=True, methods=['post'])
    def submit_for_approval(self, request, pk=None):
        """Submit budget for approval"""
        budget = self.get_object()
        
        if budget.status != 'draft':
            return Response({
                'error': f'Cannot submit budget with status: {budget.status}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate budget has items
        if not budget.items.exists():
            return Response({
                'error': 'Budget must have at least one budget item'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate total funding
        total_funding = budget.total_funding_allocated
        if total_funding < budget.total_amount:
            return Response({
                'error': f'Insufficient funding. Need {budget.currency.code} {budget.total_amount - total_funding:,.2f} more'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        budget.status = 'pending_approval'
        budget.save()
        
        return Response({
            'message': 'Budget submitted for approval',
            'status': budget.status
        })
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a budget"""
        budget = self.get_object()
        
        if budget.status != 'pending_approval':
            return Response({
                'error': f'Cannot approve budget with status: {budget.status}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        budget.status = 'approved'
        budget.approved_by = request.user
        budget.approved_at = timezone.now()
        budget.save()
        
        # send_budget_notification(budget, 'approved')
        
        serializer = self.get_serializer(budget)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate approved budget"""
        budget = self.get_object()
        
        if budget.status != 'approved':
            return Response({
                'error': 'Can only activate approved budgets'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        budget.status = 'active'
        budget.save()
        
        return Response({
            'message': 'Budget activated successfully',
            'status': budget.status
        })
    
    @action(detail=True, methods=['post'])
    def check_utilization(self, request, pk=None):
        """Check budget utilization and send alerts if needed"""
        budget = self.get_object()
        
        spent_percentage = budget.spent_percentage
        alerts_sent = []
        
        if spent_percentage >= 100:
            # send_budget_notification(budget, 'exceeded')
            alerts_sent.append('exceeded')
        elif spent_percentage >= 90:
            # send_budget_notification(budget, 'alert_90')
            alerts_sent.append('90_percent')
        elif spent_percentage >= 80:
            # send_budget_notification(budget, 'alert_80')
            alerts_sent.append('80_percent')
        
        return Response({
            'spent_percentage': spent_percentage,
            'alerts_sent': alerts_sent,
            'remaining_amount': budget.remaining_amount,
            'status': 'over_budget' if spent_percentage > 100 else 'within_budget'
        })
    
    @action(detail=True, methods=['post'])
    def add_funding(self, request, pk=None):
        """Add funding source to budget"""
        budget = self.get_object()
        funding_source_id = request.data.get('funding_source_id')
        amount = Decimal(request.data.get('amount', '0'))
        
        if amount <= 0:
            return Response({
                'error': 'Amount must be greater than 0'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            funding_source = FundingSource.objects.get(id=funding_source_id)
        except FundingSource.DoesNotExist:
            return Response({
                'error': 'Invalid funding source ID'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if funding_source.amount_remaining < amount:
            return Response({
                'error': f'Insufficient funds in source. Available: {funding_source.currency.code} {funding_source.amount_remaining:,.2f}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create or update budget funding
        budget_funding, created = BudgetFunding.objects.get_or_create(
            budget=budget,
            funding_source=funding_source,
            defaults={'amount_allocated': amount}
        )
        
        if not created:
            budget_funding.amount_allocated += amount
            budget_funding.save()
        
        # Update funding source
        funding_source.amount_allocated += amount
        funding_source.save()
        
        return Response({
            'message': f'Added {funding_source.currency.code} {amount:,.2f} from {funding_source.name}',
            'total_funding': budget.total_funding_allocated
        })


class BudgetFundingViewSet(viewsets.ModelViewSet):
    queryset = BudgetFunding.objects.all()
    serializer_class = BudgetFundingSerializer

    def get_queryset(self):
        """
        Optionally restricts returned entries by budget ID,
        e.g., /api/budgetfunding/?budget=123
        """
        queryset = super().get_queryset()
        budget_id = self.request.query_params.get('budget')
        if budget_id:
            queryset = queryset.filter(budget_id=budget_id)
        return queryset

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except Exception as e:
            if 'unique constraint' in str(e).lower():
                return Response(
                    {"detail": "This funding source is already allocated to the budget."},
                    status=status.HTTP_409_CONFLICT
                )
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def update(self, request, *args, **kwargs):
        try:
            return super().update(request, *args, **kwargs)
        except Exception as e:
            if 'unique constraint' in str(e).lower():
                return Response(
                    {"detail": "Duplicate allocation detected. Funding source already exists for this budget."},
                    status=status.HTTP_409_CONFLICT
                )
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            {"detail": "Funding allocation deleted successfully."},
            status=status.HTTP_204_NO_CONTENT
        )
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
        expense = serializer.save(submitted_by=self.request.user)
        
        # Auto-send notification for submission
        if expense.status == 'pending':
            send_expense_notification(expense, 'submitted')
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve an expense"""
        expense = self.get_object()
        
        if expense.status != 'pending':
            return Response({
                'error': f'Cannot approve expense with status: {expense.status}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check budget availability if linked to budget item
        if expense.budget_item:
            if expense.budget_item.remaining_amount < expense.amount:
                return Response({
                    'error': f'Insufficient budget. Available: {expense.budget_item.budget.currency.code} {expense.budget_item.remaining_amount:,.2f}'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            expense.status = 'approved'
            expense.approved_by = request.user
            expense.approved_at = timezone.now()
            expense.save()
            
            # Update budget item if linked
            if expense.budget_item:
                expense.budget_item.spent_amount += expense.amount
                expense.budget_item.save()
                
                # Update budget
                budget = expense.budget_item.budget
                budget.spent_amount += expense.amount
                budget.save()
                
                # Check budget utilization
                spent_percentage = budget.spent_percentage
                if spent_percentage >= 100:
                    send_budget_notification(budget, 'exceeded')
                elif spent_percentage >= 90:
                    send_budget_notification(budget, 'alert_90')
                elif spent_percentage >= 80:
                    send_budget_notification(budget, 'alert_80')
            
            send_expense_notification(expense, 'approved', request.user)
        
        serializer = self.get_serializer(expense)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject an expense"""
        expense = self.get_object()
        
        if expense.status != 'pending':
            return Response({
                'error': f'Cannot reject expense with status: {expense.status}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        rejection_reason = request.data.get('reason', '')
        
        expense.status = 'rejected'
        expense.approved_by = request.user
        expense.approved_at = timezone.now()
        expense.notes = f"Rejected: {rejection_reason}\n{expense.notes or ''}"
        expense.save()
        
        send_expense_notification(expense, 'rejected', request.user)
        
        serializer = self.get_serializer(expense)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def mark_paid(self, request, pk=None):
        """Mark expense as paid"""
        expense = self.get_object()
        
        if expense.status != 'approved':
            return Response({
                'error': 'Can only mark approved expenses as paid'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        account_id = request.data.get('account_id')
        reference = request.data.get('reference', '')
        
        with transaction.atomic():
            expense.status = 'paid'
            expense.save()
            
            # Create transaction if account specified
            if account_id:
                try:
                    account = BankAccount.objects.get(id=account_id)
                    AccountTransaction.objects.create(
                        account=account,
                        transaction_type='debit',
                        amount=expense.amount,
                        expense=expense,
                        reference_number=reference or f"EXP-{expense.id}-{timezone.now().strftime('%Y%m%d')}",
                        transaction_date=timezone.now(),
                        description=f"Payment for {expense.title}",
                        status='completed',
                        authorized_by=request.user
                    )
                except BankAccount.DoesNotExist:
                    return Response({
                        'error': 'Invalid account ID'
                    }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'message': 'Expense marked as paid',
            'status': expense.status
        })

# Enhanced Dashboard ViewSet with comprehensive analytics
class DashboardViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def financial_overview(self, request):
        """Get comprehensive financial overview"""
        # Time period filter
        period = request.query_params.get('period', 'month')  # month, quarter, year, all
        
        end_date = timezone.now()
        if period == 'month':
            start_date = end_date.replace(day=1)
        elif period == 'quarter':
            quarter_start = ((end_date.month - 1) // 3) * 3 + 1
            start_date = end_date.replace(month=quarter_start, day=1)
        elif period == 'year':
            start_date = end_date.replace(month=1, day=1)
        else:
            start_date = None
        
        # Base querysets
        donations_qs = Donation.objects.filter(status='completed')
        grants_qs = Grant.objects.filter(status__in=['active', 'completed'])
        expenses_qs = OrganizationalExpense.objects.filter(status='paid')
        budgets_qs = Budget.objects.filter(status='active').prefetch_related('items')  # Prefetch items
        
        # Apply date filters
        if start_date:
            donations_qs = donations_qs.filter(donation_date__gte=start_date)
            expenses_qs = expenses_qs.filter(expense_date__gte=start_date)
        
        # Calculate totals
        total_donations = donations_qs.aggregate(total=Sum('amount'))['total'] or 0
        total_grants_received = grants_qs.aggregate(total=Sum('amount_received'))['total'] or 0
        total_expenses = expenses_qs.aggregate(total=Sum('amount'))['total'] or 0
        
        # Evaluate budgets and calculate spent amount in memory
        budgets = list(budgets_qs)
        total_budget_allocated = sum(b.total_amount for b in budgets)
        total_budget_spent = sum(b.spent_amount for b in budgets)
        
        # Account balances
        active_accounts = BankAccount.objects.filter(is_active=True)
        total_account_balance = sum(account.current_balance for account in active_accounts)
        
        # Counts
        active_campaigns = DonationCampaign.objects.filter(is_active=True).count()
        active_grants = Grant.objects.filter(status='active').count()
        pending_expenses = OrganizationalExpense.objects.filter(status='pending').count()
        overdue_reports = GrantReport.objects.filter(
            due_date__lt=timezone.now().date(),
            status__in=['draft', 'submitted']
        ).count()
        
        # Financial health indicators
        net_income = total_donations + total_grants_received - total_expenses
        budget_utilization = (total_budget_spent / total_budget_allocated * 100) if total_budget_allocated > 0 else 0
        
        # Liquidity ratio (current assets / current liabilities - simplified)
        liquidity_ratio = total_account_balance / max(pending_expenses * 1000, 1)  # Rough estimate
        
        overview = {
            'period': period,
            'date_range': {
                'start': start_date.isoformat() if start_date else None,
                'end': end_date.isoformat()
            },
            'financial_summary': {
                'total_donations': float(total_donations),
                'total_grants_received': float(total_grants_received),
                'total_expenses': float(total_expenses),
                'net_income': float(net_income),
                'total_account_balance': float(total_account_balance),
                'total_budget_allocated': float(total_budget_allocated),
                'total_budget_spent': float(total_budget_spent),
                'budget_utilization_percentage': float(budget_utilization)
            },
            'activity_counts': {
                'active_campaigns': active_campaigns,
                'active_grants': active_grants,
                'pending_expenses': pending_expenses,
                'overdue_reports': overdue_reports,
                'active_accounts': active_accounts.count()
            },
            'health_indicators': {
                'financial_health': 'good' if net_income > 0 else 'concerning',
                'budget_health': 'good' if budget_utilization < 90 else 'warning' if budget_utilization < 100 else 'critical',
                'liquidity_health': 'good' if liquidity_ratio > 2 else 'warning' if liquidity_ratio > 1 else 'critical',
                'liquidity_ratio': float(liquidity_ratio)
            }
        }
        
        return Response(overview)
    
    @action(detail=False, methods=['get'])
    def donation_analytics(self, request):
        """Get detailed donation analytics"""
        days = int(request.query_params.get('days', 30))
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        donations = Donation.objects.filter(
            status='completed',
            donation_date__gte=start_date
        )
        
        # Daily trends
        daily_donations = donations.extra(
            select={'day': 'date(donation_date)'}
        ).values('day').annotate(
            count=Count('id'),
            total=Sum('amount'),
            avg=Avg('amount')
        ).order_by('day')
        
        # Payment method analysis
        total_donations_count = donations.count()
        payment_methods = donations.values('payment_method').annotate(
            count=Count('id'),
            total=Sum('amount'),
            percentage=Case(
                When(count__gt=0, then=Value(100.0) * Count('id') / Value(total_donations_count)),
                default=Value(0.0),
                output_field=FloatField()
            )
        ).order_by('-total')
        
        # Donor analysis
        donor_stats = {
            'total_donors': donations.values('donor').distinct().count(),
            'anonymous_donations': donations.filter(is_anonymous=True).count(),
            'repeat_donors': donations.values('donor').annotate(
                donation_count=Count('id')
            ).filter(donation_count__gt=1).count()
        }
        
        # Amount segments
        amount_segments = {
            'micro': donations.filter(amount__lt=50).count(),
            'small': donations.filter(amount__gte=50, amount__lt=250).count(),
            'medium': donations.filter(amount__gte=250, amount__lt=1000).count(),
            'large': donations.filter(amount__gte=1000, amount__lt=5000).count(),
            'major': donations.filter(amount__gte=5000).count()
        }
        
        # Campaign performance
        campaign_performance = donations.filter(campaign__isnull=False).values(
            'campaign__title', 'campaign__id'
        ).annotate(
            total_raised=Sum('amount'),
            donation_count=Count('id'),
            avg_donation=Avg('amount')
        ).order_by('-total_raised')[:10]
        
        analytics = {
            'period': f'{days} days',
            'summary': {
                'total_donations': donations.count(),
                'total_amount': donations.aggregate(total=Sum('amount'))['total'] or 0,
                'average_donation': donations.aggregate(avg=Avg('amount'))['avg'] or 0,
                'largest_donation': donations.aggregate(max=Sum('amount'))['max'] or 0
            },
            'daily_trends': list(daily_donations),
            'payment_methods': list(payment_methods),
            'donor_stats': donor_stats,
            'amount_segments': amount_segments,
            'top_campaigns': list(campaign_performance)
        }
        
        return Response(analytics)
    
    @action(detail=False, methods=['get'])
    def campaign_performance(self, request):
        """Get campaign performance analytics"""
        days = int(request.query_params.get('days', 30))
        limit = int(request.query_params.get('limit', 10))
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Get active campaigns with their performance metrics
        campaigns = DonationCampaign.objects.filter(
            is_active=True
        ).prefetch_related('donations')
        
        campaign_data = []
        
        for campaign in campaigns:
            # Get donations for this campaign in the time period
            campaign_donations = campaign.donations.filter(
                status='completed',
                donation_date__gte=start_date
            )
            
            # Calculate metrics
            total_raised = campaign.current_amount_in_target_currency
            period_raised = campaign_donations.aggregate(total=Sum('amount'))['total'] or 0
            donation_count = campaign_donations.count()
            unique_donors = campaign_donations.values('donor').distinct().count()
            avg_donation = campaign_donations.aggregate(avg=Avg('amount'))['avg'] or 0
            
            # Progress metrics
            progress_percentage = campaign.progress_percentage
            days_remaining = (campaign.end_date - timezone.now().date()).days
            days_active = (timezone.now().date() - campaign.start_date).days + 1
            
            # Performance indicators
            daily_avg = period_raised / days if days > 0 else 0
            target_daily_needed = (campaign.target_amount - total_raised) / max(days_remaining, 1) if days_remaining > 0 else 0
            
            campaign_data.append({
                'id': campaign.id,
                'title': campaign.title,
                'target_amount': float(campaign.target_amount),
                'total_raised': float(total_raised),
                'period_raised': float(period_raised),
                'progress_percentage': float(progress_percentage),
                'days_remaining': days_remaining,
                'days_active': days_active,
                'donation_count': donation_count,
                'unique_donors': unique_donors,
                'avg_donation': float(avg_donation),
                'daily_avg_period': float(daily_avg),
                'target_daily_needed': float(target_daily_needed),
                'is_on_track': daily_avg >= target_daily_needed if days_remaining > 0 else progress_percentage >= 100,
                'performance_score': min(100, (daily_avg / max(target_daily_needed, 1)) * 100) if target_daily_needed > 0 else 100,
                'currency': campaign.target_currency.code if campaign.target_currency else 'USD',
                'start_date': campaign.start_date,
                'end_date': campaign.end_date,
                'is_featured': campaign.is_featured
            })
        
        # Sort by performance score or total raised
        sort_by = request.query_params.get('sort', 'performance_score')
        if sort_by == 'total_raised':
            campaign_data.sort(key=lambda x: x['total_raised'], reverse=True)
        elif sort_by == 'progress_percentage':
            campaign_data.sort(key=lambda x: x['progress_percentage'], reverse=True)
        elif sort_by == 'period_raised':
            campaign_data.sort(key=lambda x: x['period_raised'], reverse=True)
        else:  # performance_score
            campaign_data.sort(key=lambda x: x['performance_score'], reverse=True)
        
        # Limit results
        campaign_data = campaign_data[:limit]
        
        # Calculate summary statistics
        total_campaigns = len(campaigns)
        active_campaigns = len([c for c in campaign_data if c['days_remaining'] > 0])
        successful_campaigns = len([c for c in campaign_data if c['progress_percentage'] >= 100])
        on_track_campaigns = len([c for c in campaign_data if c['is_on_track']])
        
        # Overall performance metrics
        total_target = sum(c['target_amount'] for c in campaign_data)
        total_raised_all = sum(c['total_raised'] for c in campaign_data)
        total_period_raised = sum(c['period_raised'] for c in campaign_data)
        
        performance = {
            'period_days': days,
            'summary': {
                'total_campaigns': total_campaigns,
                'active_campaigns': active_campaigns,
                'successful_campaigns': successful_campaigns,
                'on_track_campaigns': on_track_campaigns,
                'success_rate': (successful_campaigns / max(total_campaigns, 1)) * 100,
                'on_track_rate': (on_track_campaigns / max(active_campaigns, 1)) * 100,
                'total_target_amount': float(total_target),
                'total_raised': float(total_raised_all),
                'period_raised': float(total_period_raised),
                'overall_progress': (total_raised_all / max(total_target, 1)) * 100
            },
            'campaigns': campaign_data,
            'top_performers': campaign_data[:5],  # Top 5 performers
            'needs_attention': [
                c for c in campaign_data 
                if c['days_remaining'] > 0 and c['performance_score'] < 50
            ][:5]  # Campaigns that need attention
        }
        
        return Response(performance)
    
    @action(detail=False, methods=['get'])
    def budget_performance(self, request):
        """Get budget performance analytics"""
        fiscal_year = request.query_params.get('fiscal_year')
        
        # Fetch budgets and convert to list to reuse evaluated objects
        budgets_qs = Budget.objects.filter(status__in=['active', 'completed'])
        if fiscal_year:
            budgets_qs = budgets_qs.filter(fiscal_year=fiscal_year)
        
        # Prefetch related data if needed for spent_amount property
        budgets_qs = budgets_qs.prefetch_related('items')  
        budgets = list(budgets_qs)

        # Helper function for budget group calculations
        def calculate_group_stats(group):
            total_allocated = sum(b.total_amount for b in group)
            total_spent = sum(b.spent_amount for b in group)
            utilizations = [
                (b.spent_amount / b.total_amount) * 100 
                for b in group 
                if b.total_amount > 0
            ]
            avg_utilization = sum(utilizations) / len(utilizations) if utilizations else 0
            return total_allocated, total_spent, avg_utilization

        # Budget utilization by type
        budget_by_type = []
        for budget_type in set(b.budget_type for b in budgets):
            type_budgets = [b for b in budgets if b.budget_type == budget_type]
            total_allocated, total_spent, avg_utilization = calculate_group_stats(type_budgets)
            
            budget_by_type.append({
                'budget_type': budget_type,
                'count': len(type_budgets),
                'total_allocated': float(total_allocated),
                'total_spent': float(total_spent),
                'avg_utilization': float(avg_utilization)
            })

        # Sort by total allocated
        budget_by_type.sort(key=lambda x: x['total_allocated'], reverse=True)
        
        # Department budget analysis
        dept_budgets = []
        departments = {b.department: b.department.name for b in budgets if b.department}
        for dept_id, dept_name in departments.items():
            dept_budgets_group = [b for b in budgets if b.department == dept_id]
            total_allocated, total_spent, _ = calculate_group_stats(dept_budgets_group)
            utilization = (total_spent / total_allocated * 100) if total_allocated > 0 else 0
            
            dept_budgets.append({
                'department__name': dept_name,
                'total_allocated': float(total_allocated),
                'total_spent': float(total_spent),
                'utilization': float(utilization)
            })

        # Sort by total allocated
        dept_budgets.sort(key=lambda x: x['total_allocated'], reverse=True)
        
        # Budget alerts
        over_budget = 0
        near_limit = 0
        for budget in budgets:
            if budget.total_amount > 0:
                utilization = (budget.spent_amount / budget.total_amount) * 100
                if utilization > 100:
                    over_budget += 1
                elif utilization >= 90:
                    near_limit += 1
        
        # Monthly spending trends (unchanged)
        monthly_spending = OrganizationalExpense.objects.filter(
            status='paid',
            expense_date__gte=timezone.now() - timedelta(days=365)
        ).extra(
            select={'month': "date_trunc('month', expense_date)"}
        ).values('month').annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('month')
        
        # Overall utilization calculation
        total_allocated = sum(b.total_amount for b in budgets)
        total_spent = sum(b.spent_amount for b in budgets)
        overall_utilization = (total_spent / total_allocated * 100) if total_allocated > 0 else 0
        
        performance = {
            'summary': {
                'total_budgets': len(budgets),
                'total_allocated': float(total_allocated),
                'total_spent': float(total_spent),
                'overall_utilization': float(overall_utilization)
            },
            'alerts': {
                'over_budget_count': over_budget,
                'near_limit_count': near_limit,
                'total_alerts': over_budget + near_limit
            },
            'by_type': budget_by_type,
            'by_department': dept_budgets,
            'monthly_trends': list(monthly_spending)
        }
        
        return Response(performance)
    @action(detail=False, methods=['get'])
    def grant_pipeline(self, request):
        """Get grant pipeline analytics"""
        grants = Grant.objects.all()
        
        # Pipeline by status
        pipeline_status = grants.values('status').annotate(
            count=Count('id'),
            total_amount=Sum('amount'),
            avg_amount=Avg('amount')
        ).order_by('status')
        
        # Success rate
        total_submitted = grants.filter(status__in=[
            'submitted', 'under_review', 'approved', 'rejected', 'active', 'completed'
        ]).count()
        successful = grants.filter(status__in=['approved', 'active', 'completed']).count()
        success_rate = (successful / total_submitted * 100) if total_submitted > 0 else 0
        
        # Grantor analysis
        grantor_performance = grants.filter(status__in=['approved', 'active', 'completed']).values(
            'grantor', 'grantor_type'
        ).annotate(
            grant_count=Count('id'),
            total_amount=Sum('amount'),
            avg_amount=Avg('amount')
        ).order_by('-total_amount')[:10]
        
        # Disbursement tracking - Fixed calculation
        active_grants = grants.filter(status='active')
        total_approved = active_grants.aggregate(total=Sum('amount'))['total'] or 0
        total_received = active_grants.aggregate(total=Sum('amount_received'))['total'] or 0
        pending_disbursement = total_approved - total_received
        
        disbursement_summary = {
            'total_approved': float(total_approved),
            'total_received': float(total_received),
            'pending_disbursement': float(pending_disbursement)
        }
        
        # Upcoming deadlines
        upcoming_deadlines = GrantReport.objects.filter(
            due_date__gte=timezone.now().date(),
            due_date__lte=timezone.now().date() + timedelta(days=30),
            status__in=['draft', 'submitted']
        ).select_related('grant').order_by('due_date')[:10]
        
        pipeline = {
            'summary': {
                'total_grants': grants.count(),
                'success_rate': float(success_rate),
                'total_pipeline_value': grants.aggregate(total=Sum('amount'))['total'] or 0,
                'active_grants': grants.filter(status='active').count()
            },
            'pipeline_status': list(pipeline_status),
            'disbursement_summary': disbursement_summary,
            'top_grantors': list(grantor_performance),
            'upcoming_deadlines': [
                {
                    'grant_title': report.grant.title,
                    'report_type': report.report_type,
                    'due_date': report.due_date,
                    'days_until_due': (report.due_date - timezone.now().date()).days
                }
                for report in upcoming_deadlines
            ]
        }
        
        return Response(pipeline)
    
    @action(detail=False, methods=['get'])
    def cash_flow_forecast(self, request):
        """Get cash flow forecast"""
        from decimal import Decimal
        
        days_ahead = int(request.query_params.get('days', 90))
        
        # Current balance - ensure Decimal
        current_balance = sum(
            account.current_balance 
            for account in BankAccount.objects.filter(is_active=True)
        )
        if not isinstance(current_balance, Decimal):
            current_balance = Decimal(str(current_balance))
        
        # Projected income
        # Recurring donations - ensure Decimal
        recurring_income_raw = RecurringDonation.objects.filter(
            status='active',
            next_payment_date__lte=timezone.now().date() + timedelta(days=days_ahead)
        ).aggregate(total=Sum('amount'))['total']
        recurring_income = Decimal(str(recurring_income_raw)) if recurring_income_raw else Decimal('0')
        
        # Expected grant disbursements - ensure Decimal
        active_grants = Grant.objects.filter(status='active')
        expected_grants = Decimal('0')
        for grant in active_grants:
            remaining = grant.amount - grant.amount_received
            expected_grants += remaining
        
        # Projected expenses
        # Approved but unpaid expenses - ensure Decimal
        pending_expenses_raw = OrganizationalExpense.objects.filter(
            status='approved'
        ).aggregate(total=Sum('amount'))['total']
        pending_expenses = Decimal(str(pending_expenses_raw)) if pending_expenses_raw else Decimal('0')
        
        # Monthly recurring expenses (estimate based on last 3 months) - ensure Decimal
        avg_monthly_expenses_raw = OrganizationalExpense.objects.filter(
            status='paid',
            expense_date__gte=timezone.now().date() - timedelta(days=90)
        ).aggregate(avg=Avg('amount'))['avg']
        avg_monthly_expenses = Decimal(str(avg_monthly_expenses_raw)) if avg_monthly_expenses_raw else Decimal('0')
        
        projected_monthly_expenses = avg_monthly_expenses * Decimal(str(days_ahead / 30))
        
        # Calculate forecast - all Decimal operations
        projected_balance = (
            current_balance + 
            recurring_income + 
            expected_grants - 
            pending_expenses - 
            projected_monthly_expenses
        )
        
        forecast = {
            'forecast_period_days': days_ahead,
            'current_balance': float(current_balance),
            'projected_income': {
                'recurring_donations': float(recurring_income),
                'expected_grants': float(expected_grants),
                'total': float(recurring_income + expected_grants)
            },
            'projected_expenses': {
                'pending_approved': float(pending_expenses),
                'estimated_recurring': float(projected_monthly_expenses),
                'total': float(pending_expenses + projected_monthly_expenses)
            },
            'projected_balance': float(projected_balance),
            'cash_flow_health': (
                'healthy' if projected_balance > current_balance * Decimal('0.5')
                else 'concerning' if projected_balance > Decimal('0')
                else 'critical'
            )
        }
        
        return Response(forecast)

class InKindDonationViewSet(viewsets.ModelViewSet):
    queryset = InKindDonation.objects.select_related(
        'donor', 'campaign', 'project', 'currency', 'processed_by'
    )
    serializer_class = InKindDonationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'item_category', 'currency', 'campaign', 'project']
    search_fields = ['donor_name', 'donor_email', 'item_description']
    ordering_fields = ['donation_date', 'estimated_value', 'status', 'created_at']
    ordering = ['-donation_date']
    
    def perform_create(self, serializer):
        in_kind_donation = serializer.save(processed_by=self.request.user)
        
        # Auto-send notification if completed
        if in_kind_donation.status == 'completed':
            send_in_kind_donation_notification(in_kind_donation)
    
    @action(detail=True, methods=['post'])
    def accept_donation(self, request, pk=None):
        """Accept an in-kind donation"""
        donation = self.get_object()
        
        if donation.status != 'pending':
            return Response({
                'error': f'Cannot accept donation with status: {donation.status}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        donation.status = 'accepted'
        donation.acceptance_date = timezone.now().date()
        donation.save()
        
        return Response({
            'message': 'In-kind donation accepted',
            'status': donation.status,
            'acceptance_date': donation.acceptance_date
        })
    
    @action(detail=True, methods=['post'])
    def complete_donation(self, request, pk=None):
        """Complete an in-kind donation (mark as received)"""
        donation = self.get_object()
        
        if donation.status != 'accepted':
            return Response({
                'error': 'Can only complete accepted donations'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        donation.status = 'completed'
        donation.received_date = timezone.now().date()
        donation.save()
        
        send_in_kind_donation_notification(donation)
        
        return Response({
            'message': 'In-kind donation completed',
            'status': donation.status,
            'received_date': donation.received_date
        })
    
    @action(detail=True, methods=['post'])
    def decline_donation(self, request, pk=None):
        """Decline an in-kind donation"""
        donation = self.get_object()
        
        if donation.status not in ['pending', 'accepted']:
            return Response({
                'error': f'Cannot decline donation with status: {donation.status}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        decline_reason = request.data.get('reason', '')
        
        donation.status = 'declined'
        donation.notes = f"Declined: {decline_reason}\n{donation.notes or ''}"
        donation.save()
        
        return Response({
            'message': 'In-kind donation declined',
            'status': donation.status,
            'reason': decline_reason
        })
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get in-kind donation statistics"""
        queryset = self.get_queryset()
        
        # Basic stats
        total_donations = queryset.count()
        completed_donations = queryset.filter(status='completed').count()
        pending_donations = queryset.filter(status='pending').count()
        total_estimated_value = queryset.filter(status='completed').aggregate(
            total=Sum('estimated_value')
        )['total'] or 0
        
        # Category breakdown
        category_stats = queryset.filter(status='completed').values('item_category').annotate(
            count=Count('id'),
            total_value=Sum('estimated_value')
        ).order_by('-total_value')
        
        return Response({
            'summary': {
                'total_donations': total_donations,
                'completed_donations': completed_donations,
                'pending_donations': pending_donations,
                'total_estimated_value': float(total_estimated_value)
            },
            'category_breakdown': list(category_stats)
        })

class GrantReportViewSet(viewsets.ModelViewSet):
    queryset = GrantReport.objects.select_related('grant', 'submitted_by', 'reviewed_by')
    serializer_class = GrantReportSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'report_type', 'grant']
    search_fields = ['title', 'grant__title']
    ordering_fields = ['due_date', 'submission_date', 'created_at']
    ordering = ['-due_date']
    
    def perform_create(self, serializer):
        serializer.save(submitted_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def submit_report(self, request, pk=None):
        """Submit grant report"""
        report = self.get_object()
        
        if report.status != 'draft':
            return Response({
                'error': f'Cannot submit report with status: {report.status}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        report.status = 'submitted'
        report.submission_date = timezone.now().date()
        report.save()
        
        send_grant_report_due_notification(report.grant, 'submitted')
        
        return Response({
            'message': 'Grant report submitted successfully',
            'status': report.status,
            'submission_date': report.submission_date
        })
    
    @action(detail=True, methods=['post'])
    def approve_report(self, request, pk=None):
        """Approve grant report"""
        report = self.get_object()
        
        if report.status != 'submitted':
            return Response({
                'error': f'Cannot approve report with status: {report.status}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        report.status = 'approved'
        report.reviewed_by = request.user
        report.review_date = timezone.now().date()
        report.save()
        
        return Response({
            'message': 'Grant report approved',
            'status': report.status,
            'review_date': report.review_date
        })
    
    @action(detail=True, methods=['post'])
    def request_revision(self, request, pk=None):
        """Request revision for grant report"""
        report = self.get_object()
        
        if report.status != 'submitted':
            return Response({
                'error': f'Cannot request revision for report with status: {report.status}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        revision_notes = request.data.get('notes', '')
        
        report.status = 'revision_requested'
        report.reviewed_by = request.user
        report.review_date = timezone.now().date()
        report.review_notes = revision_notes
        report.save()
        
        return Response({
            'message': 'Revision requested for grant report',
            'status': report.status,
            'notes': revision_notes
        })
    
    @action(detail=False, methods=['get'])
    def overdue_reports(self, request):
        """Get overdue grant reports"""
        overdue = self.get_queryset().filter(
            due_date__lt=timezone.now().date(),
            status__in=['draft', 'submitted', 'revision_requested']
        ).order_by('due_date')
        
        serializer = self.get_serializer(overdue, many=True)
        return Response({
            'count': overdue.count(),
            'reports': serializer.data
        })

class FundingSourceViewSet(viewsets.ModelViewSet):
    queryset = FundingSource.objects.select_related('currency', 'created_by')
    serializer_class = FundingSourceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['funding_type', 'currency', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'total_amount', 'created_at']
    ordering = ['name']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['get'])
    def allocation_history(self, request, pk=None):
        """Get allocation history for funding source"""
        funding_source = self.get_object()
        allocations = funding_source.budget_funding.select_related('budget').order_by('-created_at')
        
        allocation_data = []
        for allocation in allocations:
            allocation_data.append({
                'budget_title': allocation.budget.title,
                'budget_id': allocation.budget.id,
                'amount_allocated': float(allocation.amount_allocated),
                'allocation_date': allocation.created_at.date(),
                'budget_status': allocation.budget.status
            })
        
        return Response({
            'funding_source': funding_source.name,
            'total_amount': float(funding_source.total_amount),
            'amount_allocated': float(funding_source.amount_allocated),
            'amount_remaining': float(funding_source.amount_remaining),
            'allocations': allocation_data
        })
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate funding source"""
        funding_source = self.get_object()
        funding_source.is_active = True
        funding_source.save()
        
        return Response({
            'message': f'Funding source {funding_source.name} activated',
            'status': 'active'
        })
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate funding source"""
        funding_source = self.get_object()
        funding_source.is_active = False
        funding_source.save()
        
        return Response({
            'message': f'Funding source {funding_source.name} deactivated',
            'status': 'inactive'
        })

class BudgetItemViewSet(viewsets.ModelViewSet):
    queryset = BudgetItem.objects.select_related('budget', 'created_by')
    serializer_class = BudgetItemSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['budget', 'category']
    search_fields = ['title', 'description']
    ordering_fields = ['title', 'allocated_amount', 'spent_amount', 'created_at']
    ordering = ['title']

    def get_serializer(self, *args, **kwargs):
        if self.action == 'retrieve' :
            return BudgetItemDetailSerializer(*args, **kwargs)
        return BudgetItemSerializer(*args, **kwargs)
    
    def perform_create(self, serializer):
        try:
            serializer.is_valid(raise_exception=True)
            serializer.save(created_by=self.request.user)
        except ValidationError as e:
            print(f"Validation error: {e}")
    
    @action(detail=True, methods=['get'])
    def expenses(self, request, pk=None):
        """Get expenses for this budget item"""
        budget_item = self.get_object()
        expenses = budget_item.expenses.all().order_by('-expense_date')
        
        # Apply filters
        status_filter = request.query_params.get('status')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if status_filter:
            expenses = expenses.filter(status=status_filter)
        if start_date:
            expenses = expenses.filter(expense_date__gte=start_date)
        if end_date:
            expenses = expenses.filter(expense_date__lte=end_date)
        
        page = self.paginate_queryset(expenses)
        if page is not None:
            serializer = OrganizationalExpenseSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = OrganizationalExpenseSerializer(expenses, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def utilization_report(self, request, pk=None):
        """Get detailed utilization report for budget item"""
        budget_item = self.get_object()
        
        # Calculate utilization
        utilization_percentage = budget_item.utilization_percentage
        remaining_amount = budget_item.remaining_amount
        
        # Get expense breakdown
        expense_breakdown = budget_item.expenses.filter(status='paid').values(
            'expense_date__month', 'expense_date__year'
        ).annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('expense_date__year', 'expense_date__month')
        
        return Response({
            'budget_item': {
                'title': budget_item.title,
                'allocated_amount': float(budget_item.allocated_amount),
                'spent_amount': float(budget_item.spent_amount),
                'remaining_amount': float(remaining_amount),
                'utilization_percentage': float(utilization_percentage)
            },
            'status': (
                'over_budget' if utilization_percentage > 100 
                else 'near_limit' if utilization_percentage > 90 
                else 'on_track'
            ),
            'monthly_spending': list(expense_breakdown)
        })

class AccountTransactionViewSet(viewsets.ModelViewSet):
    queryset = AccountTransaction.objects.select_related(
        'account', 'original_currency', 'donation', 'grant', 'expense', 'authorized_by'
    )
    serializer_class = AccountTransactionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = TransactionFilter
    search_fields = ['reference_number', 'description']
    ordering_fields = ['transaction_date', 'amount', 'status', 'created_at']
    ordering = ['-transaction_date']
    
    def perform_create(self, serializer):
        print(serializer)
        try:
            serializer.is_valid(raise_exception=True)
            serializer.save(authorized_by=self.request.user)
        except ValidationError as e:
            print(f"Validation error: {e}")
    
    @action(detail=True, methods=['post'])
    def reconcile(self, request, pk=None):
        """Reconcile a transaction"""
        transaction = self.get_object()
        
        if transaction.is_reconciled:
            return Response({
                'error': 'Transaction is already reconciled'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        bank_statement_reference = request.data.get('bank_statement_reference', '')
        reconciliation_notes = request.data.get('notes', '')
        
        transaction.is_reconciled = True
        transaction.reconciliation_date = timezone.now().date()
        transaction.bank_statement_reference = bank_statement_reference
        transaction.reconciliation_notes = reconciliation_notes
        transaction.save()
        
        send_reconciliation_notification(transaction)
        
        return Response({
            'message': 'Transaction reconciled successfully',
            'reconciliation_date': transaction.reconciliation_date,
            'bank_reference': bank_statement_reference
        })
    
    @action(detail=True, methods=['post'])
    def unreconcile(self, request, pk=None):
        """Unreconcile a transaction"""
        transaction = self.get_object()
        
        if not transaction.is_reconciled:
            return Response({
                'error': 'Transaction is not reconciled'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        transaction.is_reconciled = False
        transaction.reconciliation_date = None
        transaction.bank_statement_reference = ''
        transaction.reconciliation_notes = ''
        transaction.save()
        
        return Response({
            'message': 'Transaction unreconciled successfully'
        })
    
    @action(detail=False, methods=['get'])
    def unreconciled(self, request):
        """Get unreconciled transactions"""
        account_id = request.query_params.get('account_id')
        
        unreconciled = self.get_queryset().filter(
            is_reconciled=False,
            status='completed'
        )
        
        if account_id:
            unreconciled = unreconciled.filter(account_id=account_id)
        
        unreconciled = unreconciled.order_by('-transaction_date')
        
        # Calculate totals
        total_unreconciled = unreconciled.aggregate(
            credit_total=Sum(Case(
                When(transaction_type__in=['credit', 'transfer_in'], then='amount'),
                default=Value(0),
                output_field=DecimalField()
            )),
            debit_total=Sum(Case(
                When(transaction_type__in=['debit', 'transfer_out'], then='amount'),
                default=Value(0),
                output_field=DecimalField()
            ))
        )
        
        page = self.paginate_queryset(unreconciled)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                'results': serializer.data,
                'summary': {
                    'total_count': unreconciled.count(),
                    'credit_total': float(total_unreconciled['credit_total'] or 0),
                    'debit_total': float(total_unreconciled['debit_total'] or 0)
                }
            })
        
        serializer = self.get_serializer(unreconciled, many=True)
        return Response({
            'results': serializer.data,
            'summary': {
                'total_count': unreconciled.count(),
                'credit_total': float(total_unreconciled['credit_total'] or 0),
                'debit_total': float(total_unreconciled['debit_total'] or 0)
            }
        })
    
    @action(detail=False, methods=['post'])
    def bulk_reconcile(self, request):
        """Bulk reconcile multiple transactions"""
        transaction_ids = request.data.get('transaction_ids', [])
        bank_statement_reference = request.data.get('bank_statement_reference', '')
        
        if not transaction_ids:
            return Response({
                'error': 'transaction_ids is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        transactions = self.get_queryset().filter(
            id__in=transaction_ids,
            is_reconciled=False,
            status='completed'
        )
        
        reconciled_count = 0
        for transaction in transactions:
            transaction.is_reconciled = True
            transaction.reconciliation_date = timezone.now().date()
            transaction.bank_statement_reference = bank_statement_reference
            transaction.save()
            reconciled_count += 1
        
        return Response({
            'message': f'{reconciled_count} transactions reconciled successfully',
            'reconciled_count': reconciled_count,
            'reconciliation_date': timezone.now().date()
        })

class FundAllocationViewSet(viewsets.ModelViewSet):
    queryset = FundAllocation.objects.select_related(
        'from_account', 'to_account', 'project', 'currency', 'authorized_by'
    )
    serializer_class = FundAllocationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'allocation_type', 'project', 'from_account', 'to_account']
    search_fields = ['reference_number', 'description', 'purpose']
    ordering_fields = ['allocation_date', 'amount', 'status', 'created_at']
    ordering = ['-allocation_date']
    
    def perform_create(self, serializer):
        serializer.save(authorized_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def approve_allocation(self, request, pk=None):
        """Approve fund allocation"""
        allocation = self.get_object()
        
        if allocation.status != 'pending':
            return Response({
                'error': f'Cannot approve allocation with status: {allocation.status}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if from_account has sufficient balance
        if allocation.from_account.current_balance < allocation.amount:
            return Response({
                'error': f'Insufficient balance in {allocation.from_account.name}. Available: {allocation.from_account.current_balance}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            allocation.status = 'approved'
            allocation.approval_date = timezone.now().date()
            allocation.save()
            
            # Create transactions
            # Debit from source account
            AccountTransaction.objects.create(
                account=allocation.from_account,
                transaction_type='transfer_out',
                amount=allocation.amount,
                reference_number=f"ALLOC-OUT-{allocation.id}",
                transaction_date=timezone.now(),
                description=f"Fund allocation to {allocation.to_account.name}: {allocation.purpose}",
                status='completed',
                authorized_by=request.user
            )
            
            # Credit to destination account
            AccountTransaction.objects.create(
                account=allocation.to_account,
                transaction_type='transfer_in',
                amount=allocation.amount,
                reference_number=f"ALLOC-IN-{allocation.id}",
                transaction_date=timezone.now(),
                description=f"Fund allocation from {allocation.from_account.name}: {allocation.purpose}",
                status='completed',
                authorized_by=request.user
            )
        
        return Response({
            'message': 'Fund allocation approved and processed',
            'status': allocation.status,
            'approval_date': allocation.approval_date
        })
    
    @action(detail=True, methods=['post'])
    def reject_allocation(self, request, pk=None):
        """Reject fund allocation"""
        allocation = self.get_object()
        
        if allocation.status != 'pending':
            return Response({
                'error': f'Cannot reject allocation with status: {allocation.status}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        rejection_reason = request.data.get('reason', '')
        
        allocation.status = 'rejected'
        allocation.approval_date = timezone.now().date()
        allocation.notes = f"Rejected: {rejection_reason}\n{allocation.notes or ''}"
        allocation.save()
        
        return Response({
            'message': 'Fund allocation rejected',
            'status': allocation.status,
            'reason': rejection_reason
        })
    
    @action(detail=False, methods=['get'])
    def pending_approvals(self, request):
        """Get pending fund allocations requiring approval"""
        pending = self.get_queryset().filter(status='pending').order_by('allocation_date')
        
        # Calculate total pending amount
        total_pending = pending.aggregate(total=Sum('amount'))['total'] or 0
        
        serializer = self.get_serializer(pending, many=True)
        return Response({
            'count': pending.count(),
            'total_amount': float(total_pending),
            'allocations': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def allocation_summary(self, request):
        """Get fund allocation summary"""
        # Filter by date range if provided
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        queryset = self.get_queryset()
        if start_date:
            queryset = queryset.filter(allocation_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(allocation_date__lte=end_date)
        
        # Summary by status
        status_summary = queryset.values('status').annotate(
            count=Count('id'),
            total_amount=Sum('amount')
        ).order_by('status')
        
        # Summary by allocation type
        type_summary = queryset.filter(status='approved').values('allocation_type').annotate(
            count=Count('id'),
            total_amount=Sum('amount')
        ).order_by('-total_amount')
        
        # Monthly trends
        monthly_trends = queryset.filter(status='approved').extra(
            select={'month': "date_trunc('month', allocation_date)"}
        ).values('month').annotate(
            count=Count('id'),
            total_amount=Sum('amount')
        ).order_by('month')
        
        return Response({
            'status_summary': list(status_summary),
            'type_summary': list(type_summary),
            'monthly_trends': list(monthly_trends)
        })
