from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated,IsAuthenticatedOrReadOnly
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Count, Avg, Q, F,Min, Case, When, Value, DecimalField, FloatField
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import calendar
from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models import Max
from django.core.paginator import Paginator

from mainapps.permit.mixins import ActivityTrackingMixin

from ..models import (
    FinancialInstitution, BankAccount, ExchangeRate, DonationCampaign,
    Donation, RecurringDonation, InKindDonation, Grant, GrantReport,
    FundingSource, Budget, BudgetFunding, BudgetItem, OrganizationalExpense,
    AccountTransaction, FundAllocation
)
from .serializers import (
    BudgetDetailSerializer, BudgetItemDetailSerializer, CurrencyConversionSerializer,
      DonationCampaignDetailSerializer, DonationCampaignListSerializer, DonationDetailSerializer, 
      DonationListSerializer, FinancialInstitutionSerializer, BankAccountSerializer,
        ExchangeRateSerializer,
      GrantDetailSerializer, GrantListSerializer, GrantReportDetailSerializer,
        GrantReportListSerializer, InKindDonationDetailSerializer, InKindDonationListSerializer, PaymentStatusUpdateSerializer, 
        RecurringDonationDetailSerializer, RecurringDonationListSerializer, 
      GrantReportSerializer,
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

class FinancialInstitutionViewSet(ActivityTrackingMixin,viewsets.ModelViewSet):
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

class BankAccountViewSet(ActivityTrackingMixin,viewsets.ModelViewSet):
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

    def get_queryset(self):
        base_qs = super().get_queryset()
        min_balance = self.request.query_params.get('min_balance')
        max_balance = self.request.query_params.get('max_balance')

        try:
            min_balance = float(min_balance) if min_balance is not None else None
            max_balance = float(max_balance) if max_balance is not None else None
        except ValueError:
            min_balance = None
            max_balance = None

        # Filter in Python (temporary list)
        if min_balance is not None or max_balance is not None:
            filtered_ids = [
                acc.pk for acc in base_qs
                if (min_balance is None or acc.current_balance >= min_balance)
                and (max_balance is None or acc.current_balance <= max_balance)
            ]
            return base_qs.filter(pk__in=filtered_ids)

        return base_qs
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


class DonationCampaignViewSet(viewsets.ModelViewSet):
    """
    Comprehensive ViewSet for Donation Campaigns with enhanced analytics
    """
    queryset = DonationCampaign.objects.select_related(
        'target_currency', 'project', 'created_by'
    ).prefetch_related('managed_by')
    
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    # filterset_class = DonationCampaignFilter
    search_fields = ['title', 'description', 'campaign_type']
    ordering_fields = [
        'created_at', 'start_date', 'end_date', 'target_amount', 
        'current_amount'
    ]
    ordering = ['-created_at']

    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_serializer_class(self):
        if self.action == 'list':
            return DonationCampaignListSerializer
        return DonationCampaignDetailSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by campaign health
        health_filter = self.request.query_params.get('health')
        if health_filter:
            # This would require custom filtering based on calculated properties
            pass
        
        # Filter by progress range
        min_progress = self.request.query_params.get('min_progress')
        max_progress = self.request.query_params.get('max_progress')
        if min_progress or max_progress:
            # Custom filtering would be implemented here
            pass
        
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        """Get comprehensive analytics for a campaign"""
        campaign = self.get_object()
        
        # Cache key for analytics
        cache_key = f"campaign_analytics_{pk}_{timezone.now().date()}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return Response(cached_data)
        
        analytics_data = {
            'financial_metrics': {
                'current_amount': campaign.current_amount,
                'total_donations_amount': campaign.total_donations_amount,
                'total_recurring_amount': campaign.total_recurring_amount,
                'total_in_kind_amount': campaign.total_in_kind_amount,
                'net_donations_amount': campaign.net_donations_amount,
                'progress_percentage': campaign.progress_percentage,
                'amount_remaining': campaign.amount_remaining,
                'daily_fundraising_rate': campaign.daily_fundraising_rate,
                'projected_final_amount': campaign.projected_final_amount,
            },
            'donor_metrics': {
                'total_donors_count': campaign.total_donors_count,
                'total_donations_count': campaign.total_donations_count,
                'average_donation_amount': campaign.average_donation_amount,
                'largest_donation_amount': campaign.largest_donation_amount,
            },
            'time_metrics': {
                'days_remaining': campaign.days_remaining,
                'days_elapsed': campaign.days_elapsed,
                'time_progress_percentage': campaign.time_progress_percentage,
                'campaign_status': campaign.campaign_status,
                'fundraising_health': campaign.fundraising_health,
            },
            'breakdown': campaign.get_donation_breakdown(),
            'performance': campaign.get_performance_metrics(),
        }
        
        # Cache for 1 hour
        cache.set(cache_key, analytics_data, 3600)
        
        return Response(analytics_data)



    @action(detail=False, methods=['get'])
    def dashboard_stats(self, request):
        """Get dashboard statistics for all campaigns"""
        # Get base queryset with annotations
        base_queryset = self.get_queryset()
        
        # Active campaigns
        active_campaigns = base_queryset.filter(
            status='active',
            start_date__lte=timezone.now().date(),
            end_date__gte=timezone.now().date()
        )
        
        # Calculate health distribution by iterating through campaigns
        # Since fundraising_health is a property, we need to evaluate it in Python
        active_campaigns_list = list(active_campaigns)
        health_distribution = {}
        
        for campaign in active_campaigns_list:
            health = campaign.fundraising_health
            health_distribution[health] = health_distribution.get(health, 0) + 1
        
        # Status distribution
        status_distribution = {}
        all_campaigns_list = list(base_queryset)
        
        for campaign in all_campaigns_list:
            status = campaign.campaign_status
            status_distribution[status] = status_distribution.get(status, 0) + 1
        
        # Top performing campaigns - sort by calculated progress in Python
        # since we can't order by the property in the database
        top_campaigns = sorted(
            active_campaigns_list,
            key=lambda x: x.progress_percentage,
            reverse=True
        )[:5]
        
        # Recent campaigns - this can be done in the database
        recent_campaigns = base_queryset.order_by('-created_at')[:5]
        
        return Response({
            'summary': {
                'total_campaigns': base_queryset.count(),
                'active_campaigns': len(active_campaigns_list),
                'completed_campaigns': base_queryset.filter(status='completed').count(),
            },
            'health_distribution': health_distribution,
            'status_distribution': status_distribution,
            'top_performing': DonationCampaignListSerializer(top_campaigns, many=True).data,
            'recent_campaigns': DonationCampaignListSerializer(recent_campaigns, many=True).data,
        })
    
    @action(detail=True, methods=['get'])
    def comprehensive_analytics(self, request, pk=None):
        """Get comprehensive analytics for a specific campaign"""
        campaign = self.get_object()
        
        # Financial metrics
        financial_metrics = {
            'current_amount': float(campaign.current_amount),
            'total_donations_amount': float(campaign.total_donations_amount),
            'total_recurring_amount': float(campaign.total_recurring_amount),
            'total_in_kind_amount': float(campaign.total_in_kind_amount),
            'net_donations_amount': float(campaign.net_donations_amount),
            'progress_percentage': float(campaign.progress_percentage),
            'minimum_goal_percentage': float(campaign.minimum_goal_percentage),
            'amount_remaining': float(campaign.amount_remaining),
            'amount_over_target': float(campaign.amount_over_target),
            'is_target_reached': campaign.is_target_reached,
            'is_minimum_reached': campaign.is_minimum_reached,
        }
        
        # Donor metrics
        donor_metrics = {
            'total_donors_count': campaign.total_donors_count,
            'total_donations_count': campaign.total_donations_count,
            'average_donation_amount': float(campaign.average_donation_amount),
            'largest_donation_amount': float(campaign.largest_donation_amount),
        }
        
        # Time metrics
        time_metrics = {
            'days_remaining': campaign.days_remaining,
            'days_elapsed': campaign.days_elapsed,
            'total_campaign_days': campaign.total_campaign_days,
            'time_progress_percentage': float(campaign.time_progress_percentage),
            'daily_fundraising_rate': float(campaign.daily_fundraising_rate),
            'projected_final_amount': float(campaign.projected_final_amount),
        }
        
        # Campaign info
        campaign_info = {
            'id': campaign.id,
            'title': campaign.title,
            'campaign_type': campaign.campaign_type,
            'target_amount': float(campaign.target_amount),
            'currency': campaign.target_currency.code,
            'campaign_status': campaign.campaign_status,
            'fundraising_health': campaign.fundraising_health,
            'is_active': campaign.is_active,
            'can_receive_donations': campaign.can_receive_donations,
        }
        
        # Formatted amounts
        formatted_amounts = {
            'target': campaign.formatted_target_amount,
            'current': campaign.formatted_current_amount,
            'remaining': campaign.formatted_amount_remaining,
            'minimum_goal': campaign.formatted_minimum_goal,
        }
        
        # Performance indicators
        performance_indicators = {
            'monetary_progress': float(campaign.progress_percentage),
            'is_on_track': campaign.fundraising_health in ['EXCELLENT', 'VERY_GOOD', 'ON_TRACK'],
            'donor_retention': 0,  # Calculate if needed
            'payment_method_efficiency': 0,  # Calculate if needed
            'recurring_donor_value': None,  # Calculate if needed
        }
        
        return Response({
            'campaign_info': campaign_info,
            'financial_metrics': financial_metrics,
            'donor_metrics': donor_metrics,
            'time_metrics': time_metrics,
            'breakdown': campaign.get_donation_breakdown(),
            'performance': campaign.get_performance_metrics(),
            'formatted_amounts': formatted_amounts,
            'performance_indicators': performance_indicators,
        })
    
    @action(detail=True, methods=['get'])
    def donation_trends(self, request, pk=None):
        """Get donation trends for a specific campaign"""
        campaign = self.get_object()
        period = int(request.query_params.get('period', 30))
        
        from datetime import timedelta
        from django.db.models import Sum, Count, Avg
        from django.db.models.functions import TruncDate
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=period)
        
        # Daily trends
        daily_donations = campaign.donations.filter(
            donation_date__date__gte=start_date,
            donation_date__date__lte=end_date,
            status='completed'
        ).annotate(
            day=TruncDate('donation_date')
        ).values('day').annotate(
            count=Count('id'),
            total=Sum('amount'),
            avg=Avg('amount')
        ).order_by('day')
        
        daily_trends = []
        for item in daily_donations:
            daily_trends.append({
                'day': item['day'].strftime('%Y-%m-%d'),
                'count': item['count'],
                'total': float(item['total'] or 0),
                'avg': float(item['avg'] or 0),
            })
        
        # Weekly trends (simplified)
        weekly_trends = []  # Implement if needed
        
        return Response({
            'daily_trends': daily_trends,
            'weekly_trends': weekly_trends,
            'period_summary': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'total_days': period,
            }
        })
    
    @action(detail=True, methods=['get'])
    def donor_analysis(self, request, pk=None):
        """Get donor analysis for a specific campaign"""
        campaign = self.get_object()
        
        # Define donor segments based on donation amounts
        donations = campaign.donations.filter(status='completed')
        
        segments = {
            'micro': {'min': 0, 'max': 50},
            'small': {'min': 50, 'max': 250},
            'medium': {'min': 250, 'max': 1000},
            'large': {'min': 1000, 'max': 5000},
            'major': {'min': 5000, 'max': float('inf')},
        }
        
        segment_data = {}
        for segment_name, limits in segments.items():
            segment_donations = donations.filter(
                amount__gte=limits['min'],
                amount__lt=limits['max'] if limits['max'] != float('inf') else 999999999
            )
            
            segment_data[segment_name] = {
                'count': segment_donations.count(),
                'total': float(segment_donations.aggregate(Sum('amount'))['amount__sum'] or 0),
                'avg': float(segment_donations.aggregate(Avg('amount'))['amount__avg'] or 0),
                'unique_donors': segment_donations.values('donor').distinct().count(),
            }
        
        # Repeat donors
        from django.db.models import Count
        repeat_donors = donations.values('donor').annotate(
            donation_count=Count('id'),
            total_donated=Sum('amount')
        ).filter(donation_count__gt=1).order_by('-total_donated')[:10]
        
        repeat_donors_data = []
        for donor in repeat_donors:
            repeat_donors_data.append({
                'donor': donor['donor'],
                'donation_count': donor['donation_count'],
                'total_donated': float(donor['total_donated']),
            })
        
        # Donor retention
        total_donors = donations.values('donor').distinct().count()
        repeat_donors_count = donations.values('donor').annotate(
            count=Count('id')
        ).filter(count__gt=1).count()
        
        donor_retention = {
            'total_donors': total_donors,
            'repeat_donors_count': repeat_donors_count,
            'first_time_donors_count': total_donors - repeat_donors_count,
            'retention_rate': (repeat_donors_count / total_donors * 100) if total_donors > 0 else 0,
        }
        
        return Response({
            'segments': segment_data,
            'repeat_donors': repeat_donors_data,
            'donor_retention': donor_retention,
        })
    
    @action(detail=True, methods=['get'])
    def payment_analysis(self, request, pk=None):
        campaign = self.get_object()
        target_currency = campaign.target_currency  # Campaign's currency
        
        # Fetch all completed donations (prefetch to reduce queries)
        completed_donations = campaign.donations.filter(status='completed').select_related('campaign')
        
        # 1. Payment Methods Breakdown
        payment_methods_map = {}
        for donation in completed_donations:
            method = donation.payment_method
            amount = donation.get_actual_amount_in_currency(target_currency)
            fee = donation.get_processor_fee_in_currency(target_currency)
            
            if method not in payment_methods_map:
                payment_methods_map[method] = {
                    'count': 0,
                    'total': Decimal('0.00'),
                    'total_fees': Decimal('0.00'),
                }
            payment_methods_map[method]['count'] += 1
            payment_methods_map[method]['total'] += amount
            payment_methods_map[method]['total_fees'] += fee

        # Convert map to sorted list
        payment_methods_data = [
            {
                'payment_method': method,
                'count': data['count'],
                'total': float(data['total']),
                'avg': float(data['total'] / data['count']) if data['count'] else 0,
                'total_fees': float(data['total_fees']),
            }
            for method, data in payment_methods_map.items()
        ]
        payment_methods_data.sort(key=lambda x: x['total'], reverse=True)
        
        # 2. Processing Efficiency
        total_gross = sum(data['total'] for data in payment_methods_map.values())
        total_fees = sum(data['total_fees'] for data in payment_methods_map.values())
        total_net = total_gross - total_fees
        avg_fee_percentage = (total_fees / total_gross * 100) if total_gross > 0 else 0
        
        processing_efficiency = {
            'total_gross': round(float(total_gross), 2),
            'total_fees': round(float(total_fees),2),
            'total_net': round(float(total_net),2),
            'avg_fee_percentage': round(float(avg_fee_percentage),2),
        }
        
        # 3. Status Breakdown (all donations)
        all_donations = campaign.donations.all().select_related('campaign')
        status_map = {}
        for donation in all_donations:
            status = donation.status
            amount = donation.get_actual_amount_in_currency(target_currency) if status == 'completed' else Decimal('0.00')
            
            if status not in status_map:
                status_map[status] = {'count': 0, 'total': Decimal('0.00')}
            status_map[status]['count'] += 1
            status_map[status]['total'] += amount

        status_data = [
            {'status': status, 'count': data['count'], 'total': float(data['total'])}
            for status, data in status_map.items()
        ]
        status_data.sort(key=lambda x: x['count'], reverse=True)
        
        # 4. Fee Analysis (uses completed donations data)
        fee_percentage = (total_fees / total_gross * 100) if total_gross > 0 else 0
        net_efficiency = (total_net / total_gross * 100) if total_gross > 0 else 0
        
        fee_analysis = {
            'total_fees': round(float(total_fees),2),
            'fee_percentage': round(float(fee_percentage),2),
            'net_efficiency': round(float(net_efficiency),2),
        }
        
        return Response({
            'payment_methods': payment_methods_data,
            'processing_efficiency': processing_efficiency,
            'status_breakdown': status_data,
            'fee_analysis': fee_analysis,
        })

    @action(detail=True, methods=['get'])
    def bank_accounts(self, request, pk=None):
        """Get bank accounts associated with a campaign"""
        campaign = self.get_object()
        
        # Get campaign bank accounts
        campaign_accounts = campaign.campaign_bank_accounts.select_related(
            'bank_account', 'bank_account__currency', 'bank_account__financial_institution'
        ).order_by('priority_order')
        
        accounts_data = []
        for campaign_account in campaign_accounts:
            accounts_data.append({
                'id': campaign_account.id,
                'bank_account': {
                    'id': campaign_account.bank_account.id,
                    'name': campaign_account.bank_account.name,
                    'account_type': campaign_account.bank_account.account_type,
                    'currency': {
                        'id': campaign_account.bank_account.currency.id,
                        'code': campaign_account.bank_account.currency.code,
                        'name': campaign_account.bank_account.currency.name,
                    },
                    'formatted_balance': campaign_account.bank_account.formatted_balance,
                    'is_active': campaign_account.bank_account.is_active,
                },
                'is_primary': campaign_account.is_primary,
                'priority_order': campaign_account.priority_order,
                'notes': campaign_account.notes,
                'created_at': campaign_account.created_at,
            })
        
        return Response({
            'campaign_title': campaign.title,
            'total_accounts': len(accounts_data),
            'accounts': accounts_data,
        })
    
    # @action(detail=True, methods=['get'])
    # def donations(self, request, pk=None):
    #     """Get all donations for a specific campaign (regular, recurring, in-kind)"""
    #     campaign = self.get_object()
        
    #     # Get query parameters
    #     donation_type = request.query_params.get('type', 'all')  # all, regular, recurring, in_kind
    #     start_date = request.query_params.get('start_date')
    #     end_date = request.query_params.get('end_date')
    #     min_amount = request.query_params.get('min_amount')
    #     max_amount = request.query_params.get('max_amount')
    #     status_filter = request.query_params.get('status')
    #     page = int(request.query_params.get('page', 1))
    #     page_size = int(request.query_params.get('page_size', 20))
        
    #     # Base querysets for each donation type
    #     regular_donations = campaign.donations.all().filter(recurring_donation__isnull=True)
    #     recurring_donations = campaign.recurring_donations.donations.all()
    #     in_kind_donations = campaign.in_kind_donations.all()
        
    #     # Apply date filters
    #     if start_date:
    #         start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
    #         regular_donations = regular_donations.filter(donation_date__gte=start_date)
    #         recurring_donations = recurring_donations.filter(created_at__gte=start_date)
    #         in_kind_donations = in_kind_donations.filter(donation_date__gte=start_date)
        
    #     if end_date:
    #         end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    #         regular_donations = regular_donations.filter(donation_date__lte=end_date)
    #         recurring_donations = recurring_donations.filter(created_at__lte=end_date)
    #         in_kind_donations = in_kind_donations.filter(donation_date__lte=end_date)
        
    #     # Apply amount filters (only for regular and recurring)
    #     if min_amount:
    #         min_amount = float(min_amount)
    #         regular_donations = regular_donations.filter(amount__gte=min_amount)
    #         recurring_donations = recurring_donations.filter(amount__gte=min_amount)
        
    #     if max_amount:
    #         max_amount = float(max_amount)
    #         regular_donations = regular_donations.filter(amount__lte=max_amount)
    #         recurring_donations = recurring_donations.filter(amount__lte=max_amount)
        
    #     # Apply status filter
    #     if status_filter:
    #         regular_donations = regular_donations.filter(status=status_filter)
    #         recurring_donations = recurring_donations.filter(status=status_filter)
    #         in_kind_donations = in_kind_donations.filter(status=status_filter)
        
    #     # Prepare unified donation data
    #     donations_data = []
        
    #     # Add regular donations
    #     if donation_type in ['all', 'regular']:
    #         for donation in regular_donations.select_related('donor', 'currency'):
    #             donations_data.append({
    #                 'id': donation.id,
    #                 'type': 'regular',
    #                 'donor': {
    #                     'id': donation.donor.id if donation.donor else None,
    #                     'name': donation.donor.get_full_name if donation.donor else 'Anonymous',
    #                     'email': donation.donor.email if donation.donor else None,
    #                 },
    #                 'amount': float(donation.amount),
    #                 'currency': {
    #                     'code': donation.currency.code if donation.currency else 'USD',
    #                 },
    #                 'status': donation.status,
    #                 'donation_date': donation.donation_date.isoformat() if donation.donation_date else None,
    #                 'payment_method': getattr(donation, 'payment_method', None),
    #                 'is_anonymous': getattr(donation, 'is_anonymous', False),
    #                 'message': getattr(donation, 'message', ''),
    #                 'created_at': donation.created_at.isoformat() if hasattr(donation, 'created_at') else None,
    #             })
        
    #     # Add recurring donations
    #     if donation_type in ['all', 'recurring']:
    #         for donation in recurring_donations.select_related('donor', 'currency'):
    #             donations_data.append({
    #                 'id': donation.id,
    #                 'type': 'recurring',
    #                 'donor': {
    #                     'id': donation.donor.id if donation.donor else None,
    #                     'name': donation.donor.get_full_name if donation.donor else 'Anonymous',
    #                     'email': donation.donor.email if donation.donor else None,
    #                 },
    #                 'amount': float(donation.amount),
    #                 'currency': {
    #                     'code': donation.currency.code if donation.currency else 'USD',
    #                 },
    #                 'status': donation.status,
    #                 'donation_date': donation.created_at.isoformat() if donation.created_at else None,
    #                 'payment_method': getattr(donation, 'payment_method', None),
    #                 'is_anonymous': getattr(donation, 'is_anonymous', False),
    #                 'message': getattr(donation, 'message', ''),
    #                 'frequency': getattr(donation, 'frequency', 'monthly'),
    #                 'next_payment_date': donation.next_payment_date.isoformat() if hasattr(donation, 'next_payment_date') and donation.next_payment_date else None,
    #                 'created_at': donation.created_at.isoformat() if hasattr(donation, 'created_at') else None,
    #             })
        
    #     # Add in-kind donations
    #     if donation_type in ['all', 'in_kind']:
    #         for donation in in_kind_donations.select_related('donor'):
    #             donations_data.append({
    #                 'id': donation.id,
    #                 'type': 'in_kind',
    #                 'donor': {
    #                     'id': donation.donor.id if donation.donor else None,
    #                     'name': donation.donor.get_full_name if donation.donor else 'Anonymous',
    #                     'email': donation.donor.email if donation.donor else None,
    #                 },
    #                 'amount': float(getattr(donation, 'estimated_value', 0)),
    #                 'currency': {
    #                     'code': 'USD',  # Default for in-kind
    #                 },
    #                 'status': donation.status,
    #                 'donation_date': donation.donation_date.isoformat() if donation.donation_date else None,
    #                 'payment_method': 'in_kind',
    #                 'is_anonymous': getattr(donation, 'is_anonymous', False),
    #                 'message': getattr(donation, 'message', ''),
    #                 'description': getattr(donation, 'description', ''),
    #                 'item_type': getattr(donation, 'item_type', ''),
    #                 'quantity': getattr(donation, 'quantity', 1),
    #                 'created_at': donation.created_at.isoformat() if hasattr(donation, 'created_at') else None,
    #             })
        
    #     # Sort by donation_date (most recent first)
    #     donations_data.sort(key=lambda x: x['donation_date'] or '', reverse=True)
        
    #     # Paginate results
    #     paginator = Paginator(donations_data, page_size)
    #     page_obj = paginator.get_page(page)
        
    #     # Calculate summary statistics
    #     total_regular = regular_donations.aggregate(
    #         count=Count('id'),
    #         total=Sum('amount')
    #     )
        
    #     total_recurring = recurring_donations.aggregate(
    #         count=Count('id'),
    #         total=Sum('amount')
    #     )
        
    #     total_in_kind = in_kind_donations.aggregate(
    #         count=Count('id'),
    #         total=Sum('estimated_value')
    #     )
        
    #     return Response({
    #         'results': list(page_obj),
    #         'count': paginator.count,
    #         'next': page_obj.has_next(),
    #         'previous': page_obj.has_previous(),
    #         'page': page,
    #         'page_size': page_size,
    #         'total_pages': paginator.num_pages,
    #         'summary': {
    #             'total_donations': paginator.count,
    #             'regular_donations': {
    #                 'count': total_regular['count'] or 0,
    #                 'total': float(total_regular['total'] or 0),
    #             },
    #             'recurring_donations': {
    #                 'count': total_recurring['count'] or 0,
    #                 'total': float(total_recurring['total'] or 0),
    #             },
    #             'in_kind_donations': {
    #                 'count': total_in_kind['count'] or 0,
    #                 'total': float(total_in_kind['total'] or 0),
    #             },
    #         },
    #         'filters_applied': {
    #             'type': donation_type,
    #             'start_date': start_date.isoformat() if start_date else None,
    #             'end_date': end_date.isoformat() if end_date else None,
    #             'min_amount': min_amount,
    #             'max_amount': max_amount,
    #             'status': status_filter,
    #         }
    #     })

    @action(detail=True, methods=['get'])
    def donations(self, request, pk=None):
        """Get all donations for a specific campaign (regular, recurring, in-kind)"""
        campaign = self.get_object()
        
        # Get query parameters
        donation_type = request.query_params.get('type', 'all')  # all, regular, recurring, in_kind
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        min_amount = request.query_params.get('min_amount')
        max_amount = request.query_params.get('max_amount')
        status_filter = request.query_params.get('status')
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        
        # Base querysets for each donation type
        regular_donations = campaign.donations.filter(recurring_donation__isnull=True)
        recurring_donations = campaign.recurring_donations.all()  # Ensure this is correct
        in_kind_donations = campaign.in_kind_donations.all()
        
        # Apply date filters
        if start_date:
            start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            regular_donations = regular_donations.filter(donation_date__gte=start_date)
            recurring_donations = recurring_donations.filter(created_at__gte=start_date)
            in_kind_donations = in_kind_donations.filter(donation_date__gte=start_date)
        
        if end_date:
            end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            regular_donations = regular_donations.filter(donation_date__lte=end_date)
            recurring_donations = recurring_donations.filter(created_at__lte=end_date)
            in_kind_donations = in_kind_donations.filter(donation_date__lte=end_date)
        
        # Apply amount filters (only for regular and recurring)
        if min_amount:
            min_amount = float(min_amount)
            regular_donations = regular_donations.filter(amount__gte=min_amount)
            recurring_donations = recurring_donations.filter(amount__gte=min_amount)
        
        if max_amount:
            max_amount = float(max_amount)
            regular_donations = regular_donations.filter(amount__lte=max_amount)
            recurring_donations = recurring_donations.filter(amount__lte=max_amount)
        
        # Apply status filter
        if status_filter:
            regular_donations = regular_donations.filter(status=status_filter)
            recurring_donations = recurring_donations.filter(status=status_filter)
            in_kind_donations = in_kind_donations.filter(status=status_filter)
        
        # Prepare unified donation data
        donations_data = []
        
        # Add regular donations
        if donation_type in ['all', 'regular']:
            for donation in regular_donations.select_related('donor', 'currency'):
                donations_data.append({
                    'id': donation.id,
                    'type': 'regular',
                    'donor': {
                        'id': donation.donor.id if donation.donor else None,
                        'name': donation.donor.get_full_name() if donation.donor else 'Anonymous',
                        'email': donation.donor.email if donation.donor else None,
                    },
                    'amount': float(donation.amount),
                    'currency': {
                        'code': donation.currency.code if donation.currency else 'USD',
                    },
                    'status': donation.status,
                    'donation_date': donation.donation_date.isoformat() if donation.donation_date else None,
                    'payment_method': getattr(donation, 'payment_method', None),
                    'is_anonymous': getattr(donation, 'is_anonymous', False),
                    'message': getattr(donation, 'message', ''),
                    'created_at': donation.created_at.isoformat() if hasattr(donation, 'created_at') else None,
                })
        
        # Add recurring donations
        if donation_type in ['all', 'recurring']:
            for donation in recurring_donations.select_related('donor', 'currency'):
                donations_data.append({
                    'id': donation.id,
                    'type': 'recurring',
                    'donor': {
                        'id': donation.donor.id if donation.donor else None,
                        'name': donation.donor.get_full_name() if donation.donor else 'Anonymous',
                        'email': donation.donor.email if donation.donor else None,
                    },
                    'amount': float(donation.amount),
                    'currency': {
                        'code': donation.currency.code if donation.currency else 'USD',
                    },
                    'status': donation.status,
                    'donation_date': donation.created_at.isoformat() if donation.created_at else None,
                    'payment_method': getattr(donation, 'payment_method', None),
                    'is_anonymous': getattr(donation, 'is_anonymous', False),
                    'message': getattr(donation, 'message', ''),
                    'frequency': getattr(donation, 'frequency', 'monthly'),
                    'next_payment_date': donation.next_payment_date.isoformat() if hasattr(donation, 'next_payment_date') and donation.next_payment_date else None,
                    'created_at': donation.created_at.isoformat() if hasattr(donation, 'created_at') else None,
                })
        
        # Add in-kind donations
        if donation_type in ['all', 'in_kind']:
            for donation in in_kind_donations.select_related('donor'):
                donations_data.append({
                    'id': donation.id,
                    'type': 'in_kind',
                    'donor': {
                        'id': donation.donor.id if donation.donor else None,
                        'name': donation.donor.get_full_name() if donation.donor else 'Anonymous',
                        'email': donation.donor.email if donation.donor else None,
                    },
                    'amount': float(getattr(donation, 'estimated_value', 0)),
                    'currency': {
                        'code': 'USD',  # Default for in-kind
                    },
                    'status': donation.status,
                    'donation_date': donation.donation_date.isoformat() if donation.donation_date else None,
                    'payment_method': 'in_kind',
                    'is_anonymous': getattr(donation, 'is_anonymous', False),
                    'message': getattr(donation, 'message', ''),
                    'description': getattr(donation, 'description', ''),
                    'item_type': getattr(donation, 'item_type', ''),
                    'quantity': getattr(donation, 'quantity', 1),
                    'created_at': donation.created_at.isoformat() if hasattr(donation, 'created_at') else None,
                })
        
        # Sort by donation_date (most recent first)
        donations_data.sort(key=lambda x: x['donation_date'] or '', reverse=True)
        
        # Paginate results
        paginator = Paginator(donations_data, page_size)
        page_obj = paginator.get_page(page)
        
        # Calculate summary statistics
        total_regular = regular_donations.aggregate(
            count=Count('id'),
            total=Sum('amount')
        )
        
        total_recurring = recurring_donations.aggregate(
            count=Count('id'),
            total=Sum('amount')
        )
        
        total_in_kind = in_kind_donations.aggregate(
            count=Count('id'),
            total=Sum('estimated_value')
        )
        
        return Response({
            'results': list(page_obj),
            'count': paginator.count,
            'next': page_obj.has_next(),
            'previous': page_obj.has_previous(),
            'page': page,
            'page_size': page_size,
            'total_pages': paginator.num_pages,
            'summary': {
                'total_donations': paginator.count,
                'regular_donations': {
                    'count': total_regular['count'] or 0,
                    'total': float(total_regular['total'] or 0),
                },
                'recurring_donations': {
                    'count': total_recurring['count'] or 0,
                    'total': float(total_recurring['total'] or 0),
                },
                'in_kind_donations': {
                    'count': total_in_kind['count'] or 0,
                    'total': float(total_in_kind['total'] or 0),
                },
            },
            'filters_applied': {
                'type': donation_type,
                'start_date': start_date.isoformat() if start_date else None,
                'end_date': end_date.isoformat() if end_date else None,
                'min_amount': min_amount,
                'max_amount': max_amount,
                'status': status_filter,
            }
        })

    @action(detail=True, methods=['post'])
    def add_bank_account(self, request, pk=None):
        """Add a bank account to a campaign"""
        campaign = self.get_object()
        
        bank_account_id = request.data.get('bank_account_id')
        is_primary = request.data.get('is_primary', False)
        priority_order = request.data.get('priority_order', 1)
        notes = request.data.get('notes', '')
        
        try:
            bank_account = BankAccount.objects.get(id=bank_account_id)
        except BankAccount.DoesNotExist:
            return Response(
                {'error': 'Bank account not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if already associated
        if campaign.campaign_bank_accounts.filter(bank_account=bank_account).exists():
            return Response(
                {'error': 'Bank account already associated with this campaign'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create association
        from ..models import CampaignBankAccount
        campaign_account = CampaignBankAccount.objects.create(
            campaign=campaign,
            bank_account=bank_account,
            is_primary=is_primary,
            priority_order=priority_order,
            notes=notes
        )
        
        # If this is set as primary, unset others
        if is_primary:
            campaign.campaign_bank_accounts.exclude(
                id=campaign_account.id
            ).update(is_primary=False)
        
        return Response({
            'message': 'Bank account added successfully',
            'campaign_account_id': campaign_account.id,
        })
    
    @action(detail=True, methods=['post'])
    def set_primary_bank_account(self, request, pk=None):
        """Set a bank account as primary for a campaign"""
        campaign = self.get_object()
        bank_account_id = request.data.get('bank_account_id')
        
        try:
            campaign_account = campaign.campaign_bank_accounts.get(
                bank_account_id=bank_account_id
            )
        except:
            return Response(
                {'error': 'Bank account not associated with this campaign'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Unset all primary flags
        campaign.campaign_bank_accounts.update(is_primary=False)
        
        # Set this one as primary
        campaign_account.is_primary = True
        campaign_account.save()
        
        return Response({
            'message': 'Primary bank account updated successfully',
            'primary_account': campaign_account.bank_account.name,
        })
    
    @action(detail=True, methods=['get'])
    def donation_options(self, request, pk=None):
        """Get donation options for public display"""
        campaign = self.get_object()
        
        # Get bank accounts grouped by currency
        campaign_accounts = campaign.campaign_bank_accounts.select_related(
            'bank_account', 'bank_account__currency'
        ).filter(bank_account__is_active=True).order_by('priority_order')
        
        accounts_by_currency = {}
        primary_account = None
        
        for campaign_account in campaign_accounts:
            currency_code = campaign_account.bank_account.currency.code
            
            if currency_code not in accounts_by_currency:
                accounts_by_currency[currency_code] = []
            
            account_data = {
                'id': campaign_account.bank_account.id,
                'name': campaign_account.bank_account.name,
                'account_type': campaign_account.bank_account.account_type,
                'is_primary': campaign_account.is_primary,
            }
            
            accounts_by_currency[currency_code].append(account_data)
            
            if campaign_account.is_primary:
                primary_account = account_data
        
        return Response({
            'campaign_title': campaign.title,
            'campaign_description': campaign.description,
            'target_amount': float(campaign.target_amount),
            'current_amount': float(campaign.current_amount),
            'progress_percentage': float(campaign.progress_percentage),
            'currency': campaign.target_currency.code,
            'primary_account': primary_account,
            'accounts_by_currency': accounts_by_currency,
            'total_accounts': campaign_accounts.count(),
            'campaign_status': {
                'is_active': campaign.can_receive_donations,
                'days_remaining': campaign.days_remaining,
                'end_date': campaign.end_date.strftime('%Y-%m-%d'),
            }
        })
    
    @action(detail=True, methods=['post'])
    def update_monetary_fields(self, request, pk=None):
        """Update monetary calculations for a campaign"""
        campaign = self.get_object()
        
        # Call the update method
        campaign.update_monetary_calculations()
        
        return Response({
            'message': 'Monetary fields updated successfully',
            'current_amount': float(campaign.current_amount),
            'progress_percentage': float(campaign.progress_percentage),
            'campaign_status': campaign.campaign_status,
            'fundraising_health': campaign.fundraising_health,
        })
    
    @action(detail=True, methods=['post'])
    def check_milestones(self, request, pk=None):
        """Check and update campaign milestones"""
        campaign = self.get_object()
        
        # Implement milestone checking logic here
        # This is a placeholder implementation
        
        return Response({
            'progress_percentage': float(campaign.progress_percentage),
            'milestones_reached': [],  # Implement milestone tracking
            'notifications_sent': 0,
            'next_milestone': None,
            'campaign_status': campaign.campaign_status,
            'fundraising_health': campaign.fundraising_health,
            'is_target_reached': campaign.is_target_reached,
        })
    
    @action(detail=True, methods=['post'])
    def extend_deadline(self, request, pk=None):
        """Extend campaign deadline"""
        campaign = self.get_object()
        
        new_end_date = request.data.get('new_end_date')
        reason = request.data.get('reason', '')
        
        if not new_end_date:
            return Response(
                {'error': 'new_end_date is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from datetime import datetime
        try:
            new_date = datetime.strptime(new_end_date, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if new_date <= campaign.end_date:
            return Response(
                {'error': 'New end date must be after current end date'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        old_end_date = campaign.end_date
        campaign.end_date = new_date
        campaign.save()
        
        return Response({
            'message': 'Campaign deadline extended successfully',
            'old_end_date': old_end_date.strftime('%Y-%m-%d'),
            'new_end_date': new_date.strftime('%Y-%m-%d'),
            'reason': reason,
            'new_days_remaining': campaign.days_remaining,
            'campaign_status': campaign.campaign_status,
        })
    
    @action(detail=True, methods=['get'])
    def export_data(self, request, pk=None):
        """Export campaign data"""
        campaign = self.get_object()
        format_type = request.query_params.get('format', 'csv')
        
        # Implement data export logic here
        # This is a placeholder implementation
        
        from django.http import HttpResponse
        import csv
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="campaign_{campaign.id}_data.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Campaign', 'Target', 'Current', 'Progress', 'Status'])
        writer.writerow([
            campaign.title,
            campaign.target_amount,
            campaign.current_amount,
            f"{campaign.progress_percentage:.2f}%",
            campaign.campaign_status
        ])
        
        return response
    
    @action(detail=True, methods=['get'])
    def detailed_statistics(self, request, pk=None):
        """Legacy endpoint for backward compatibility"""
        # Redirect to comprehensive_analytics
        return self.comprehensive_analytics(request, pk)


# ============================================================================
# DONATION VIEWSET
# ============================================================================

class DonationViewSet(viewsets.ModelViewSet):
    """
    Comprehensive ViewSet for Donations with enhanced features
    """
    queryset = Donation.objects.select_related(
        'donor', 'campaign', 'project', 'currency', 'converted_currency',
        'processor_fee_currency', 'processed_by'
    )
    
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = DonationFilter
    search_fields = ['donor_name', 'donor_email', 'transaction_id', 'reference_number']
    ordering_fields = [
        'donation_date', 'amount', 'status', 'created_at', 'net_amount'
    ]
    ordering = ['-donation_date']
    permission_classes = [IsAuthenticated]

   
    @action(detail=True, methods=['patch'], url_path='payment-status')
    def update_payment_status(self, request, pk=None):
        """Update payment status for one-time donation"""
        donation = get_object_or_404(Donation, pk=pk)
        
        serializer = PaymentStatusUpdateSerializer(data=request.data)
        if serializer.is_valid():
            # Update donation status (using 'status' field, not 'payment_status')
            donation.status = serializer.validated_data['status']
            
            # Store transaction data in notes or create a separate transaction log
            transaction_data = serializer.validated_data.get('transaction_data', {})
            if transaction_data:
                donation.transaction_id = transaction_data.get('transaction_id')
                donation.reference_number = transaction_data.get('flutterwave_ref')
                donation.bank_reference = transaction_data.get('tx_ref')
                
                # Add transaction details to notes
                transaction_notes = f"Flutterwave Transaction: {transaction_data.get('transaction_id', 'N/A')}"
                donation.notes = f"{donation.notes or ''}\n{transaction_notes}".strip()
            
            # Update timestamps based on status
            if donation.status == 'completed':
                donation.processed_date = timezone.now()
            
            donation.save()
            
            return Response({
                'message': 'Payment status updated successfully',
                'donation_id': donation.id,
                'status': donation.status
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


    def get_serializer_class(self):
        if self.action == 'list':
            return DonationListSerializer
        return DonationDetailSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by amount range
        min_amount = self.request.query_params.get('min_amount')
        max_amount = self.request.query_params.get('max_amount')
        if min_amount:
            queryset = queryset.filter(amount__gte=min_amount)
        if max_amount:
            queryset = queryset.filter(amount__lte=max_amount)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(donation_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(donation_date__lte=end_date)
        
        # Filter by donor type
        donor_type = self.request.query_params.get('donor_type')
        if donor_type == 'anonymous':
            queryset = queryset.filter(is_anonymous=True)
        elif donor_type == 'registered':
            queryset = queryset.filter(donor__isnull=False, is_anonymous=False)
        elif donor_type == 'guest':
            queryset = queryset.filter(donor__isnull=True, is_anonymous=False)
        
        return queryset

    def perform_create(self, serializer):
        donation = serializer.save()
        # Trigger any post-creation processing
        donation.update_monetary_calculations()

    @action(detail=True, methods=['post'])
    def mark_receipt_sent(self, request, pk=None):
        """Mark receipt as sent"""
        donation = self.get_object()
        donation.mark_receipt_sent()
        return Response({'message': 'Receipt marked as sent'})

    @action(detail=True, methods=['post'])
    def convert_currency(self, request, pk=None):
        """Convert donation amount to different currency"""
        donation = self.get_object()
        serializer = CurrencyConversionSerializer(data=request.data)
        
        if serializer.is_valid():
            target_currency_id = serializer.validated_data['to_currency_id']
            from mainapps.common.models import Currency
            
            try:
                target_currency = Currency.objects.get(id=target_currency_id)
                converted_amount = donation.get_amount_in_currency(target_currency)
                
                return Response({
                    'original_amount': donation.amount,
                    'original_currency': donation.currency.code,
                    'converted_amount': converted_amount,
                    'target_currency': target_currency.code,
                    'conversion_date': timezone.now().date()
                })
            except Currency.DoesNotExist:
                return Response({'error': 'Invalid currency'}, status=400)
        
        return Response(serializer.errors, status=400)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get donation statistics"""
        queryset = self.filter_queryset(self.get_queryset())
        completed_donations = queryset.filter(status='completed')
        
        stats = completed_donations.aggregate(
            total_amount=Sum('amount'),
            total_count=Count('id'),
            average_amount=Avg('amount'),
            max_amount=Max('amount'),
            min_amount=Min('amount'),
            total_net=Sum('amount') - Sum('processor_fee'),
            total_fees=Sum('processor_fee')
        )
        
        # Additional calculations
        stats['fee_percentage'] = (
            (stats['total_fees'] or 0) / max(stats['total_amount'] or 1, 1)
        ) * 100
        
        # Recent trends
        last_30_days = timezone.now().date() - timedelta(days=30)
        recent_stats = completed_donations.filter(
            donation_date__gte=last_30_days
        ).aggregate(
            recent_total=Sum('amount'),
            recent_count=Count('id'),
            recent_avg=Avg('amount')
        )
        
        stats.update(recent_stats)
        
        return Response(stats)

    @action(detail=False, methods=['get'])
    def payment_method_stats(self, request):
        """Get statistics by payment method"""
        queryset = self.filter_queryset(self.get_queryset())
        
        payment_stats = queryset.filter(status='completed').values(
            'payment_method'
        ).annotate(
            count=Count('id'),
            total=Sum('amount'),
            avg=Avg('amount'),
            total_fees=Sum('processor_fee'),
            success_rate=Count('id', filter=Q(status='completed')) * 100.0 / Count('id')
        ).order_by('-total')
        
        return Response(list(payment_stats))

    @action(detail=False, methods=['post'])
    def bulk_update_status(self, request):
        """Bulk update donation status"""
        donation_ids = request.data.get('donation_ids', [])
        new_status = request.data.get('status')
        
        if not donation_ids or not new_status:
            return Response({'error': 'donation_ids and status are required'}, status=400)
        
        updated_count = self.get_queryset().filter(
            id__in=donation_ids
        ).update(status=new_status)
        
        return Response({
            'message': f'Updated {updated_count} donations',
            'updated_count': updated_count
        })

    @action(detail=False, methods=['get'])
    def export(self, request):
        """Export donations to CSV"""
        queryset = self.filter_queryset(self.get_queryset())
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="donations.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'ID', 'Date', 'Donor', 'Campaign', 'Amount', 'Currency',
            'Net Amount', 'Payment Method', 'Status', 'Receipt Sent'
        ])
        
        for donation in queryset:
            writer.writerow([
                donation.id,
                donation.donation_date,
                donation.donor_name_display,
                donation.campaign.title if donation.campaign else '',
                donation.amount,
                donation.currency.code,
                donation.net_amount,
                donation.payment_method,
                donation.status,
                donation.receipt_sent
            ])
        
        return response

# ============================================================================
# RECURRING DONATION VIEWSET
# ============================================================================

class RecurringDonationViewSet(viewsets.ModelViewSet):
    """
    Comprehensive ViewSet for Recurring Donations
    """
    queryset = RecurringDonation.objects.select_related(
        'donor', 'campaign', 'project', 'currency'
    )
    
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    # filterset_class = RecurringDonationFilter
    search_fields = ['donor__username', 'donor__email', 'subscription_id']
    ordering_fields = [
        'created_at', 'start_date', 'next_payment_date', 'amount',
        'total_donated', 'payment_count'
    ]
    ordering = ['-created_at']
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'list':
            return RecurringDonationListSerializer
        return RecurringDonationDetailSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by health status
        health_filter = self.request.query_params.get('health')
        if health_filter == 'healthy':
            # This would require custom filtering based on calculated properties
            pass
        elif health_filter == 'at_risk':
            # Custom filtering for at-risk subscriptions
            pass
        
        # Filter by payment due
        payment_due = self.request.query_params.get('payment_due')
        if payment_due == 'true':
            queryset = queryset.filter(
                next_payment_date__lte=timezone.now().date(),
                status='active'
            )
        
        return queryset
    

    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """Pause a recurring donation"""
        recurring_donation = self.get_object()
        reason = request.data.get('reason', 'Paused by user')
        
        recurring_donation.pause_subscription(reason)
        
        return Response({
            'message': 'Recurring donation paused',
            'status': recurring_donation.status
        })

    @action(detail=True, methods=['patch'], url_path='payment-status')
    def update_payment_status(self, request, pk=None):
        """Update payment status for recurring donation"""
        recurring_donation = get_object_or_404(RecurringDonation, pk=pk)
        
        serializer = PaymentStatusUpdateSerializer(data=request.data)
        if serializer.is_valid():
            # Update recurring donation status
            new_status = serializer.validated_data['status']
            transaction_data = serializer.validated_data.get('transaction_data', {})
            
            # Map payment status to recurring donation status
            if new_status == 'completed':
                recurring_donation.status = 'active'
                # Create a related one-time donation record for this payment
                self._create_recurring_payment_record(recurring_donation, transaction_data)
            elif new_status == 'failed':
                recurring_donation.record_failed_payment()
                return Response({
                    'message': 'Failed payment recorded',
                    'recurring_donation_id': recurring_donation.id,
                    'status': recurring_donation.status
                }, status=status.HTTP_200_OK)
            
            # Store transaction reference
            if transaction_data:
                recurring_donation.subscription_id = transaction_data.get('flutterwave_ref')
                transaction_notes = f"Flutterwave Subscription: {transaction_data.get('transaction_id', 'N/A')}"
                recurring_donation.notes = f"{recurring_donation.notes or ''}\n{transaction_notes}".strip()
            
            recurring_donation.save()
            
            return Response({
                'message': 'Recurring donation payment status updated successfully',
                'recurring_donation_id': recurring_donation.id,
                'status': recurring_donation.status
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def _create_recurring_payment_record(self, recurring_donation, transaction_data):
        """Create a donation record for this recurring payment"""
        donation = Donation.objects.create(
            donor=recurring_donation.donor,
            is_anonymous=recurring_donation.is_anonymous,
            campaign=recurring_donation.campaign,
            project=recurring_donation.project,
            amount=recurring_donation.amount,
            currency=recurring_donation.currency,
            payment_method=recurring_donation.payment_method,
            transaction_id=transaction_data.get('transaction_id'),
            reference_number=transaction_data.get('flutterwave_ref'),
            bank_reference=transaction_data.get('tx_ref'),
            status='completed',
            processed_date=timezone.now(),
            donation_source='website',
            notes=f"Recurring donation payment #{recurring_donation.payment_count + 1}"
        )
        
        # Update recurring donation with successful payment
        recurring_donation.record_successful_payment(donation)
        
        return donation

    @action(detail=True, methods=['post'])
    def resume(self, request, pk=None):
        """Resume a paused recurring donation"""
        recurring_donation = self.get_object()
        
        if recurring_donation.status != 'paused':
            return Response(
                {'error': 'Can only resume paused subscriptions'}, 
                status=400
            )
        
        recurring_donation.resume_subscription()
        
        return Response({
            'message': 'Recurring donation resumed',
            'status': recurring_donation.status,
            'next_payment_date': recurring_donation.next_payment_date
        })

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a recurring donation"""
        recurring_donation = self.get_object()
        reason = request.data.get('reason', 'Cancelled by user')
        
        recurring_donation.cancel_subscription(reason)
        
        return Response({
            'message': 'Recurring donation cancelled',
            'status': recurring_donation.status
        })

    @action(detail=True, methods=['post'])
    def record_payment(self, request, pk=None):
        """Record a successful payment"""
        recurring_donation = self.get_object()
        
        # This would typically be called by payment processor webhooks
        donation_data = request.data
        
        # Create the donation record
        donation = Donation.objects.create(
            donor=recurring_donation.donor,
            campaign=recurring_donation.campaign,
            project=recurring_donation.project,
            amount=recurring_donation.amount,
            currency=recurring_donation.currency,
            payment_method=recurring_donation.payment_method,
            status='completed',
            donation_date=timezone.now(),
            # Add other relevant fields
        )
        
        # Update recurring donation
        recurring_donation.record_successful_payment(donation)
        
        return Response({
            'message': 'Payment recorded successfully',
            'donation_id': donation.id,
            'next_payment_date': recurring_donation.next_payment_date
        })

    @action(detail=True, methods=['post'])
    def record_failed_payment(self, request, pk=None):
        """Record a failed payment"""
        recurring_donation = self.get_object()
        
        recurring_donation.record_failed_payment()
        
        return Response({
            'message': 'Failed payment recorded',
            'failed_count': recurring_donation.failed_payment_count,
            'status': recurring_donation.status,
            'next_retry_date': recurring_donation.next_payment_date
        })

    @action(detail=False, methods=['get'])
    def health_report(self, request):
        """Get health report for all recurring donations"""
        queryset = self.get_queryset()
        
        health_stats = {
            'total': queryset.count(),
            'active': queryset.filter(status='active').count(),
            'paused': queryset.filter(status='paused').count(),
            'cancelled': queryset.filter(status='cancelled').count(),
            'failed': queryset.filter(status='failed').count(),
        }
        
        # Calculate health metrics for active subscriptions
        active_subscriptions = queryset.filter(status='active')
        healthy_count = 0
        at_risk_count = 0
        
        for subscription in active_subscriptions:
            if subscription.is_healthy:
                healthy_count += 1
            elif subscription.is_at_risk:
                at_risk_count += 1
        
        health_stats.update({
            'healthy': healthy_count,
            'at_risk': at_risk_count,
            'health_percentage': (healthy_count / max(active_subscriptions.count(), 1)) * 100
        })
        
        # Payment due analysis
        payment_due = active_subscriptions.filter(
            next_payment_date__lte=timezone.now().date()
        ).count()
        
        overdue = active_subscriptions.filter(
            next_payment_date__lt=timezone.now().date()
        ).count()
        
        health_stats.update({
            'payment_due': payment_due,
            'overdue': overdue
        })
        
        return Response(health_stats)

    @action(detail=False, methods=['get'])
    def performance_summary(self, request):
        """Get performance summary for recurring donations"""
        queryset = self.filter_queryset(self.get_queryset())
        
        # Aggregate performance metrics
        performance = queryset.aggregate(
            total_subscriptions=Count('id'),
            total_donated=Sum('total_donated'),
            avg_monthly_value=Avg('amount'),
            total_payments=Sum('payment_count'),
            total_failed_payments=Sum('failed_payment_count')
        )
        
        # Calculate success rate
        total_attempts = (performance['total_payments'] or 0) + (performance['total_failed_payments'] or 0)
        performance['overall_success_rate'] = (
            (performance['total_payments'] or 0) / max(total_attempts, 1)
        ) * 100
        
        # Frequency breakdown
        frequency_breakdown = queryset.values('frequency').annotate(
            count=Count('id'),
            total_value=Sum('total_donated'),
            avg_value=Avg('amount')
        ).order_by('-count')
        
        performance['frequency_breakdown'] = list(frequency_breakdown)
        
        return Response(performance)

# ============================================================================
# IN-KIND DONATION VIEWSET
# ============================================================================

class InKindDonationViewSet(viewsets.ModelViewSet):
    """
    Comprehensive ViewSet for In-Kind Donations
    """
    queryset = InKindDonation.objects.select_related(
        'donor', 'campaign', 'project', 'valuation_currency', 'received_by'
    )
    
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    # filterset_class = InKindDonationFilter
    search_fields = ['item_description', 'donor_name', 'donor_email', 'brand_model']
    ordering_fields = [
        'donation_date', 'estimated_value', 'status', 'created_at',
        'received_date', 'effective_value'
    ]
    ordering = ['-donation_date']
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'list':
            return InKindDonationListSerializer
        return InKindDonationDetailSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by value range
        min_value = self.request.query_params.get('min_value')
        max_value = self.request.query_params.get('max_value')
        if min_value:
            queryset = queryset.filter(estimated_value__gte=min_value)
        if max_value:
            queryset = queryset.filter(estimated_value__lte=max_value)
        
        # Filter by receipt status
        receipt_status = self.request.query_params.get('receipt_status')
        if receipt_status == 'pending':
            queryset = queryset.filter(status='received', receipt_sent=False)
        elif receipt_status == 'sent':
            queryset = queryset.filter(receipt_sent=True)
        
        # Filter by logistics
        pickup_required = self.request.query_params.get('pickup_required')
        if pickup_required == 'true':
            queryset = queryset.filter(pickup_required=True)
        
        return queryset

    
    @action(detail=True, methods=['patch'], url_path='payment-status')
    def update_payment_status(self, request, pk=None):
        """Update payment status for in-kind donation (processing fees, etc.)"""
        in_kind_donation = get_object_or_404(InKindDonation, pk=pk)
        
        serializer = PaymentStatusUpdateSerializer(data=request.data)
        if serializer.is_valid():
            # Update in-kind donation status
            new_status = serializer.validated_data['status']
            transaction_data = serializer.validated_data.get('transaction_data', {})
            
            # Map payment status to in-kind donation status
            if new_status == 'completed':
                in_kind_donation.status = 'confirmed'
            elif new_status == 'failed':
                in_kind_donation.status = 'pledged'  # Reset to pledged if payment failed
            
            # Store transaction data
            if transaction_data:
                transaction_notes = f"Processing fee payment: {transaction_data.get('transaction_id', 'N/A')}"
                in_kind_donation.notes = f"{in_kind_donation.notes or ''}\n{transaction_notes}".strip()
            
            in_kind_donation.save()
            
            return Response({
                'message': 'In-kind donation payment status updated successfully',
                'in_kind_donation_id': in_kind_donation.id,
                'status': in_kind_donation.status
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def mark_received(self, request, pk=None):
        """Mark in-kind donation as received"""
        in_kind_donation = self.get_object()
        
        condition_notes = request.data.get('condition_notes')
        actual_value = request.data.get('actual_value')
        
        if actual_value:
            try:
                actual_value = Decimal(str(actual_value))
            except (ValueError, TypeError):
                return Response({'error': 'Invalid actual_value'}, status=400)
        
        in_kind_donation.mark_as_received(
            received_by_user=request.user,
            condition_notes=condition_notes,
            actual_value=actual_value
        )
        
        return Response({
            'message': 'In-kind donation marked as received',
            'status': in_kind_donation.status,
            'received_date': in_kind_donation.received_date,
            'effective_value': in_kind_donation.effective_value
        })

    @action(detail=True, methods=['post'])
    def mark_receipt_sent(self, request, pk=None):
        """Mark receipt as sent"""
        in_kind_donation = self.get_object()
        in_kind_donation.mark_receipt_sent()
        
        return Response({'message': 'Receipt marked as sent'})

    @action(detail=True, methods=['get'])
    def valuation_history(self, request, pk=None):
        """Get valuation history and variance analysis"""
        in_kind_donation = self.get_object()
        
        valuation_data = {
            'estimated_value': in_kind_donation.total_estimated_value,
            'market_value': in_kind_donation.total_market_value,
            'actual_value': in_kind_donation.total_actual_value,
            'effective_value': in_kind_donation.effective_value,
            'value_variance': in_kind_donation.value_variance,
            'value_variance_percentage': in_kind_donation.value_variance_percentage,
            'valuation_method': in_kind_donation.valuation_method,
            'currency': in_kind_donation.valuation_currency.code,
            'quantity': in_kind_donation.quantity,
        }
        
        return Response(valuation_data)

    @action(detail=False, methods=['get'])
    def category_analysis(self, request):
        """Analyze in-kind donations by category"""
        queryset = self.filter_queryset(self.get_queryset())
        
        category_stats = queryset.filter(status='received').values(
            'category'
        ).annotate(
            count=Count('id'),
            total_estimated=Sum('estimated_value'),
            total_actual=Sum('actual_value'),
            avg_estimated=Avg('estimated_value'),
            avg_actual=Avg('actual_value')
        ).order_by('-total_estimated')
        
        return Response(list(category_stats))

    @action(detail=False, methods=['get'])
    def logistics_report(self, request):
        """Get logistics and handling report"""
        queryset = self.filter_queryset(self.get_queryset())
        
        logistics_stats = {
            'total_items': queryset.count(),
            'pickup_required': queryset.filter(pickup_required=True).count(),
            'special_handling': queryset.exclude(special_handling_requirements='').count(),
            'storage_requirements': queryset.exclude(storage_requirements='').count(),
        }
        
        # Status breakdown
        status_breakdown = queryset.values('status').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Overdue items
        overdue_items = queryset.filter(
            status__in=['pledged', 'confirmed'],
            expected_delivery_date__lt=timezone.now().date()
        ).count()
        
        logistics_stats.update({
            'status_breakdown': list(status_breakdown),
            'overdue_items': overdue_items
        })
        
        return Response(logistics_stats)

    @action(detail=False, methods=['get'])
    def valuation_summary(self, request):
        """Get comprehensive valuation summary"""
        queryset = self.filter_queryset(self.get_queryset())
        received_items = queryset.filter(status='received')
        
        valuation_stats = received_items.aggregate(
            total_estimated=Sum('estimated_value'),
            total_actual=Sum('actual_value'),
            avg_estimated=Avg('estimated_value'),
            avg_actual=Avg('actual_value'),
            count=Count('id')
        )
        
        # Calculate variance statistics
        items_with_actual = received_items.exclude(actual_value__isnull=True)
        variance_stats = {
            'items_revalued': items_with_actual.count(),
            'revaluation_rate': (items_with_actual.count() / max(received_items.count(), 1)) * 100
        }
        
        # Value variance analysis
        positive_variance = items_with_actual.filter(
            actual_value__gt=models.F('estimated_value')
        ).count()
        
        negative_variance = items_with_actual.filter(
            actual_value__lt=models.F('estimated_value')
        ).count()
        
        variance_stats.update({
            'positive_variance_count': positive_variance,
            'negative_variance_count': negative_variance,
            'accurate_valuations': items_with_actual.count() - positive_variance - negative_variance
        })
        
        valuation_stats.update(variance_stats)
        
        return Response(valuation_stats)

# ============================================================================
# GRANT VIEWSET
# ============================================================================

class GrantViewSet(viewsets.ModelViewSet):
    """
    Comprehensive ViewSet for Grants
    """
    queryset = Grant.objects.select_related(
        'currency', 'project', 'created_by', 'managed_by'
    )
    
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = GrantFilter
    search_fields = ['title', 'grantor', 'description']
    ordering_fields = [
        'created_at', 'start_date', 'end_date', 'amount', 'submission_date'
    ]
    ordering = ['-created_at']
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'list':
            return GrantListSerializer
        return GrantDetailSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['get'])
    def reports(self, request, pk=None):
        """Get all reports for a grant"""
        grant = self.get_object()
        reports = grant.reports.order_by('-created_at')
        
        serializer = GrantReportListSerializer(reports, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def create_report(self, request, pk=None):
        """Create a new report for the grant"""
        grant = self.get_object()
        
        data = request.data.copy()
        data['grant_id'] = grant.id
        
        serializer = GrantReportDetailSerializer(data=data)
        if serializer.is_valid():
            serializer.save(submitted_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """Get grant dashboard statistics"""
        queryset = self.get_queryset()
        
        # Status breakdown
        status_breakdown = queryset.values('status').annotate(
            count=Count('id'),
            total_amount=Sum('amount')
        ).order_by('-count')
        
        # Upcoming deadlines
        upcoming_deadlines = queryset.filter(
            application_deadline__gte=timezone.now().date(),
            application_deadline__lte=timezone.now().date() + timedelta(days=30)
        ).order_by('application_deadline')
        
        # Recent grants
        recent_grants = queryset.order_by('-created_at')[:5]
        
        return Response({
            'summary': {
                'total_grants': queryset.count(),
                'total_amount': queryset.aggregate(Sum('amount'))['amount__sum'] or 0,
                'active_grants': queryset.filter(status='active').count(),
            },
            'status_breakdown': list(status_breakdown),
            'upcoming_deadlines': GrantListSerializer(upcoming_deadlines, many=True).data,
            'recent_grants': GrantListSerializer(recent_grants, many=True).data,
        })

# ============================================================================
# GRANT REPORT VIEWSET
# ============================================================================

class GrantReportViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Grant Reports
    """
    queryset = GrantReport.objects.select_related('grant', 'submitted_by')
    
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'grant__title']
    ordering_fields = ['created_at', 'due_date', 'submission_date']
    ordering = ['-created_at']
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'list':
            return GrantReportListSerializer
        return GrantReportDetailSerializer

    def perform_create(self, serializer):
        serializer.save(submitted_by=self.request.user)

    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Get overdue reports"""
        overdue_reports = self.get_queryset().filter(
            due_date__lt=timezone.now().date(),
            status__in=['draft', 'in_progress']
        )
        
        serializer = self.get_serializer(overdue_reports, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Get upcoming report deadlines"""
        days = int(request.query_params.get('days', 30))
        
        upcoming_reports = self.get_queryset().filter(
            due_date__gte=timezone.now().date(),
            due_date__lte=timezone.now().date() + timedelta(days=days),
            status__in=['draft', 'in_progress']
        ).order_by('due_date')
        
        serializer = self.get_serializer(upcoming_reports, many=True)
        return Response(serializer.data)

# ============================================================================
# UTILITY VIEWSETS
# ============================================================================

class DonationAnalyticsViewSet(viewsets.ViewSet):
    """
    ViewSet for comprehensive donation analytics
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Get overall donation analytics"""
        # Date range
        days = int(request.query_params.get('days', 30))
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        # All donations in period
        donations = Donation.objects.filter(
            status='completed',
            donation_date__gte=start_date,
            donation_date__lte=end_date
        )
        
        # Basic statistics
        stats = donations.aggregate(
            total_amount=Sum('amount'),
            total_count=Count('id'),
            avg_amount=Avg('amount'),
            max_amount=Max('amount'),
            min_amount=Min('amount')
        )
        
        # Trends
        daily_trends = donations.extra(
            select={'day': 'DATE(donation_date)'}
        ).values('day').annotate(
            count=Count('id'),
            total=Sum('amount')
        ).order_by('day')
        
        return Response({
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': days
            },
            'statistics': stats,
            'daily_trends': list(daily_trends)
        })

    @action(detail=False, methods=['post'])
    def convert_currency(self, request):
        """Convert amounts between currencies"""
        serializer = CurrencyConversionSerializer(data=request.data)
        
        if serializer.is_valid():
            # Implementation would use ExchangeRate model
            # This is a simplified version
            return Response({
                'converted_amount': serializer.validated_data['amount'],
                'message': 'Currency conversion completed'
            })
        
        return Response(serializer.errors, status=400)


def formatCurrency(currency_code, amount):
    """Format currency amount for display in alerts"""
    try:
        if currency_code == 'USD':
            return f"${amount:,.2f}"
        elif currency_code == 'EUR':
            return f"€{amount:,.2f}"
        elif currency_code == 'GBP':
            return f"£{amount:,.2f}"
        else:
            return f"{currency_code} {amount:,.2f}"
    except:
        return f"{currency_code} {amount}"


class BudgetViewSet(ActivityTrackingMixin,viewsets.ModelViewSet):
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
    def departmental_breakdown(self, request):
        """Get detailed departmental budget breakdown with analytics"""
        try:
            # Get query parameters for filtering
            fiscal_year = request.query_params.get('fiscal_year')
            budget_type = request.query_params.get('budget_type')
            status_filter = request.query_params.get('status')
            currency_id = request.query_params.get('currency')
            department_id = request.query_params.get('department')  # Filter by specific department
            
            # Base queryset
            budgets = self.get_queryset()
            
            # Apply filters
            if fiscal_year:
                budgets = budgets.filter(fiscal_year=fiscal_year)
            if budget_type:
                budgets = budgets.filter(budget_type=budget_type)
            if status_filter:
                budgets = budgets.filter(status=status_filter)
            if currency_id:
                budgets = budgets.filter(currency_id=currency_id)
            if department_id:
                budgets = budgets.filter(department_id=department_id)
            
            # Only include budgets with departments
            budgets = budgets.filter(department__isnull=False)
            
            # Group budgets by department and currency
            department_currency_groups = {}
            for budget in budgets.select_related('department', 'currency'):
                dept_id = budget.department.id
                dept_name = budget.department.name
                dept_code = budget.department.code if hasattr(budget.department, 'code') else None
                currency_id = budget.currency.id if budget.currency else 0
                currency_code = budget.currency.code if budget.currency else 'Unknown'
                
                key = f"{dept_id}_{currency_id}"
                
                if key not in department_currency_groups:
                    department_currency_groups[key] = {
                        'department_id': dept_id,
                        'department_name': dept_name,
                        'department_code': dept_code,
                        'currency_id': currency_id,
                        'currency_code': currency_code,
                        'budgets': []
                    }
                department_currency_groups[key]['budgets'].append(budget)
            
            # Helper functions
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
            
            def safe_percentage(numerator, denominator, default=0.0):
                return safe_divide(numerator, denominator, default) * 100
            
            def calculate_department_analytics(dept_budgets, dept_info):
                """Calculate detailed analytics for a department"""
                
                # Get budget IDs for expense calculation
                budget_ids = [b.id for b in dept_budgets]
                
                # Calculate spent amounts by aggregating from OrganizationalExpense
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
                    except Exception:
                        budget_expenses = {}
                
                # Basic metrics
                total_budgets = len(dept_budgets)
                total_allocated = sum(float(b.total_amount) if b.total_amount else 0.0 for b in dept_budgets)
                total_spent = sum(budget_expenses.values()) if budget_expenses else 0.0
                total_remaining = total_allocated - total_spent
                avg_utilization = safe_percentage(total_spent, total_allocated, 0.0)
                
                # Status breakdown
                status_breakdown = {}
                for budget in dept_budgets:
                    status = budget.status
                    spent_amount = budget_expenses.get(budget.id, 0.0)
                    budget_total = float(budget.total_amount) if budget.total_amount else 0.0
                    
                    if status not in status_breakdown:
                        status_breakdown[status] = {
                            'count': 0,
                            'total_amount': 0.0,
                            'spent_amount': 0.0,
                            'avg_utilization': 0.0
                        }
                    
                    status_breakdown[status]['count'] += 1
                    status_breakdown[status]['total_amount'] += budget_total
                    status_breakdown[status]['spent_amount'] += spent_amount
                
                # Calculate utilization for each status
                for status_data in status_breakdown.values():
                    status_data['avg_utilization'] = safe_percentage(
                        status_data['spent_amount'], 
                        status_data['total_amount'], 
                        0.0
                    )
                
                # Budget type breakdown
                type_breakdown = {}
                for budget in dept_budgets:
                    budget_type = budget.budget_type
                    spent_amount = budget_expenses.get(budget.id, 0.0)
                    budget_total = float(budget.total_amount) if budget.total_amount else 0.0
                    
                    if budget_type not in type_breakdown:
                        type_breakdown[budget_type] = {
                            'count': 0,
                            'total_amount': 0.0,
                            'spent_amount': 0.0,
                            'avg_utilization': 0.0
                        }
                    
                    type_breakdown[budget_type]['count'] += 1
                    type_breakdown[budget_type]['total_amount'] += budget_total
                    type_breakdown[budget_type]['spent_amount'] += spent_amount
                
                # Calculate utilization for each type
                for type_data in type_breakdown.values():
                    type_data['avg_utilization'] = safe_percentage(
                        type_data['spent_amount'], 
                        type_data['total_amount'], 
                        0.0
                    )
                
                # Monthly trends (last 12 months)
                monthly_trends = []
                current_date = timezone.now().date()
                
                for i in range(12):
                    month_start = current_date.replace(day=1) - timedelta(days=i*30)
                    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
                    
                    month_budgets = [b for b in dept_budgets if b.created_at.date() >= month_start and b.created_at.date() <= month_end]
                    month_allocated = sum(float(b.total_amount) if b.total_amount else 0.0 for b in month_budgets)
                    month_spent = sum(budget_expenses.get(b.id, 0.0) for b in month_budgets)
                    
                    monthly_trends.append({
                        'month': month_start.strftime('%Y-%m'),
                        'month_name': month_start.strftime('%B %Y'),
                        'budgets_created': len(month_budgets),
                        'total_allocated': month_allocated,
                        'total_spent': month_spent,
                        'net_position': month_allocated - month_spent
                    })
                
                monthly_trends.reverse()  # Oldest to newest
                
                # Budget health analysis
                health_metrics = {
                    'healthy_budgets': 0,
                    'warning_budgets': 0,
                    'critical_budgets': 0,
                    'underutilized_budgets': 0,
                    'overbudget_count': 0,
                    'near_deadline_count': 0
                }
                
                budget_details = []
                for budget in dept_budgets:
                    spent_amount = budget_expenses.get(budget.id, 0.0)
                    budget_total = float(budget.total_amount) if budget.total_amount else 0.0
                    utilization = safe_percentage(spent_amount, budget_total, 0.0)
                    
                    # Health status
                    if utilization > 100:
                        health_status = 'overbudget'
                        health_metrics['overbudget_count'] += 1
                    elif utilization >= 95:
                        health_status = 'critical'
                        health_metrics['critical_budgets'] += 1
                    elif utilization >= 85:
                        health_status = 'warning'
                        health_metrics['warning_budgets'] += 1
                    elif utilization < 50:
                        health_status = 'underutilized'
                        health_metrics['underutilized_budgets'] += 1
                    else:
                        health_status = 'healthy'
                        health_metrics['healthy_budgets'] += 1
                    
                    # Check deadline proximity
                    days_remaining = None
                    if budget.end_date:
                        try:
                            days_remaining = (budget.end_date - timezone.now().date()).days
                            if days_remaining <= 30:
                                health_metrics['near_deadline_count'] += 1
                        except Exception:
                            days_remaining = None
                    
                    budget_details.append({
                        'budget_id': budget.id,
                        'title': budget.title,
                        'budget_type': budget.budget_type,
                        'total_amount': budget_total,
                        'spent_amount': spent_amount,
                        'remaining_amount': budget_total - spent_amount,
                        'utilization_percentage': utilization,
                        'health_status': health_status,
                        'status': budget.status,
                        'start_date': budget.start_date.isoformat() if budget.start_date else None,
                        'end_date': budget.end_date.isoformat() if budget.end_date else None,
                        'days_remaining': days_remaining,
                        'fiscal_year': budget.fiscal_year,
                        'created_at': budget.created_at.isoformat()
                    })
                
                # Performance metrics
                performance_metrics = {
                    'budget_efficiency': min(100, max(0, 100 - abs(avg_utilization - 80))),  # Optimal at 80%
                    'planning_score': min(100, total_budgets * 10),  # More budgets = better planning
                    'execution_rate': safe_percentage(
                        len([b for b in dept_budgets if b.status in ['active', 'completed']]),
                        total_budgets,
                        0.0
                    ),
                    'on_time_delivery': safe_percentage(
                        len([b for b in dept_budgets if b.status == 'completed']),
                        len([b for b in dept_budgets if b.status in ['completed', 'cancelled']]) or 1,
                        0.0
                    ),
                    'resource_optimization': avg_utilization if avg_utilization <= 100 else 100 - (avg_utilization - 100)
                }
                
                # Risk assessment
                risk_assessment = {
                    'financial_risk': safe_percentage(health_metrics['overbudget_count'], total_budgets, 0.0),
                    'timeline_risk': safe_percentage(health_metrics['near_deadline_count'], total_budgets, 0.0),
                    'utilization_risk': safe_percentage(health_metrics['underutilized_budgets'], total_budgets, 0.0),
                    'capacity_risk': safe_percentage(health_metrics['critical_budgets'], total_budgets, 0.0),
                    'overall_risk_score': 0.0
                }
                
                # Calculate overall risk score
                risk_assessment['overall_risk_score'] = (
                    risk_assessment['financial_risk'] * 0.3 +
                    risk_assessment['timeline_risk'] * 0.25 +
                    risk_assessment['utilization_risk'] * 0.2 +
                    risk_assessment['capacity_risk'] * 0.25
                )
                
                return {
                    'department_info': {
                        'id': dept_info['department_id'],
                        'name': dept_info['department_name'],
                        'code': dept_info['department_code'],
                        'currency_id': dept_info['currency_id'],
                        'currency_code': dept_info['currency_code']
                    },
                    'summary': {
                        'total_budgets': total_budgets,
                        'total_allocated': total_allocated,
                        'total_spent': total_spent,
                        'total_remaining': total_remaining,
                        'avg_utilization': round(avg_utilization, 2)
                    },
                    'status_breakdown': [
                        {'status': k, **v} for k, v in status_breakdown.items()
                    ],
                    'type_breakdown': [
                        {'budget_type': k, **v} for k, v in type_breakdown.items()
                    ],
                    'monthly_trends': monthly_trends,
                    'health_metrics': health_metrics,
                    'budget_details': sorted(budget_details, key=lambda x: x['utilization_percentage'], reverse=True),
                    'performance_metrics': performance_metrics,
                    'risk_assessment': risk_assessment
                }
            
            # Calculate analytics for each department-currency combination
            departmental_analytics = []
            for group_key, group_data in department_currency_groups.items():
                if group_data['budgets']:  # Only process groups with budgets
                    analytics = calculate_department_analytics(group_data['budgets'], group_data)
                    departmental_analytics.append(analytics)
            
            # Sort by total allocated amount (descending)
            departmental_analytics.sort(key=lambda x: x['summary']['total_allocated'], reverse=True)
            
            # Calculate cross-department summary
            cross_department_summary = {
                'total_departments': len(departmental_analytics),
                'total_budgets': sum(dept['summary']['total_budgets'] for dept in departmental_analytics),
                'total_allocated': sum(dept['summary']['total_allocated'] for dept in departmental_analytics),
                'total_spent': sum(dept['summary']['total_spent'] for dept in departmental_analytics),
                'avg_utilization': safe_percentage(
                    sum(dept['summary']['total_spent'] for dept in departmental_analytics),
                    sum(dept['summary']['total_allocated'] for dept in departmental_analytics),
                    0.0
                ),
                'departments_at_risk': len([
                    dept for dept in departmental_analytics 
                    if dept['risk_assessment']['overall_risk_score'] > 50
                ]),
                'top_performing_department': departmental_analytics[0]['department_info']['name'] if departmental_analytics else None,
                'currencies_involved': list(set(dept['department_info']['currency_code'] for dept in departmental_analytics))
            }
            
            return Response({
                'cross_department_summary': cross_department_summary,
                'departmental_analytics': departmental_analytics,
                'generated_at': timezone.now().isoformat(),
                'filters_applied': {
                    'fiscal_year': fiscal_year,
                    'budget_type': budget_type,
                    'status': status_filter,
                    'currency': currency_id,
                    'department': department_id
                }
            })
            
        except Exception as e:
            # Return safe fallback response
            return Response({
                'cross_department_summary': {
                    'total_departments': 0,
                    'total_budgets': 0,
                    'total_allocated': 0.0,
                    'total_spent': 0.0,
                    'avg_utilization': 0.0,
                    'departments_at_risk': 0,
                    'top_performing_department': None,
                    'currencies_involved': []
                },
                'departmental_analytics': [],
                'generated_at': timezone.now().isoformat(),
                'error': 'Departmental breakdown calculation failed',
                'filters_applied': {}
            })


    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get comprehensive budget statistics for dashboard - grouped by currency"""
        try:
            # Get query parameters for filtering
            fiscal_year = request.query_params.get('fiscal_year')
            department_id = request.query_params.get('department')
            budget_type = request.query_params.get('budget_type')
            status_filter = request.query_params.get('status')
            currency_id = request.query_params.get('currency')  # Add currency filter
            
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
            if currency_id:
                budgets = budgets.filter(currency_id=currency_id)
            
            # Group budgets by currency
            currency_groups = {}
            for budget in budgets.select_related('currency'):
                currency_code = budget.currency.code if budget.currency else 'Unknown'
                currency_name = budget.currency.name if budget.currency else 'Unknown Currency'
                currency_key = budget.currency.id if budget.currency else 0
                
                if currency_key not in currency_groups:
                    currency_groups[currency_key] = {
                        'currency_id': currency_key,
                        'currency_code': currency_code,
                        'currency_name': currency_name,
                        'budgets': []
                    }
                currency_groups[currency_key]['budgets'].append(budget)
            
            # If specific currency requested, only process that currency
            if currency_id:
                currency_groups = {int(currency_id): currency_groups.get(int(currency_id), {
                    'currency_id': int(currency_id),
                    'currency_code': 'Unknown',
                    'currency_name': 'Unknown Currency',
                    'budgets': []
                })}
            
            # Helper functions
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
            
            def safe_percentage(numerator, denominator, default=0.0):
                return safe_divide(numerator, denominator, default) * 100
            
            def calculate_currency_statistics(currency_budgets, currency_info):
                """Calculate statistics for a specific currency"""
                
                # Get budget IDs for expense calculation
                budget_ids = [b.id for b in currency_budgets]
                
                # Calculate spent amounts by aggregating from OrganizationalExpense
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
                    except Exception:
                        budget_expenses = {}
                
                # Overall Summary for this currency
                total_budgets = len(currency_budgets)
                total_allocated = sum(float(b.total_amount) if b.total_amount else 0.0 for b in currency_budgets)
                total_spent = sum(budget_expenses.values()) if budget_expenses else 0.0
                total_remaining = total_allocated - total_spent
                avg_utilization = safe_percentage(total_spent, total_allocated, 0.0)
                
                # Status counts
                active_budgets = len([b for b in currency_budgets if b.status == 'active'])
                pending_approval = len([b for b in currency_budgets if b.status == 'pending_approval'])
                over_budget_count = 0
                near_limit_count = 0
                
                # Calculate over-budget and near-limit counts
                for budget in currency_budgets:
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
                    'currency_id': currency_info['currency_id'],
                    'currency_code': currency_info['currency_code'],
                    'currency_name': currency_info['currency_name'],
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
                
                # Budget by Type for this currency
                by_type = {}
                for budget in currency_budgets:
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
                
                # Calculate utilization for each type
                for type_data in by_type.values():
                    try:
                        type_data['avg_utilization'] = round(
                            safe_percentage(type_data['spent_amount'], type_data['total_amount'], 0.0), 2
                        )
                    except Exception:
                        type_data['avg_utilization'] = 0.0
                
                by_type = list(by_type.values())
                by_type.sort(key=lambda x: x.get('total_amount', 0), reverse=True)
                
                # Budget by Status for this currency
                by_status = {}
                for budget in currency_budgets:
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
                
                # Budget by Department for this currency
                by_department = {}
                for budget in [b for b in currency_budgets if b.department]:
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
                
                # Calculate utilization for each department
                for dept_data in by_department.values():
                    try:
                        dept_data['avg_utilization'] = round(
                            safe_percentage(dept_data['spent_amount'], dept_data['total_amount'], 0.0), 2
                        )
                    except Exception:
                        dept_data['avg_utilization'] = 0.0
                
                by_department = list(by_department.values())
                by_department.sort(key=lambda x: x.get('total_amount', 0), reverse=True)
                
                # Individual Budget Utilization Summary
                utilization_summary = []
                for budget in currency_budgets:
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
                            'currency_code': currency_info['currency_code'],
                            'status': budget.status,
                            'health_status': health_status,
                            'start_date': budget.start_date.isoformat() if budget.start_date else None,
                            'end_date': budget.end_date.isoformat() if budget.end_date else None,
                            'days_remaining': days_remaining,
                            'created_by': budget.created_by.get_full_name if budget.created_by else 'Unknown',
                        })
                    except Exception:
                        continue
                
                utilization_summary.sort(key=lambda x: x.get('utilization_percentage', 0), reverse=True)
                
                # Performance Metrics
                performance_metrics = {
                    'budget_accuracy': min(100, max(0, 100 - abs(avg_utilization - 85))),
                    'approval_efficiency': safe_percentage(
                        len([b for b in currency_budgets if b.status == 'approved']),
                        max(len([b for b in currency_budgets if b.status in ['pending_approval', 'approved']]), 1),
                        0.0
                    ),
                    'spend_velocity': avg_utilization,
                    'forecast_precision': 85.0,
                    'resource_utilization': avg_utilization,
                }
                
                # Risk Analysis
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
                
                return {
                    'summary': summary,
                    'by_type': by_type,
                    'by_status': by_status,
                    'utilization_summary': utilization_summary,
                    'by_department': by_department,
                    'performance_metrics': performance_metrics,
                    'risk_analysis': risk_analysis,
                }
            
            # Calculate statistics for each currency
            currency_statistics = {}
            for currency_key, currency_data in currency_groups.items():
                if currency_data['budgets']:  # Only process currencies that have budgets
                    currency_statistics[currency_key] = calculate_currency_statistics(
                        currency_data['budgets'], 
                        currency_data
                    )
            
            # If specific currency requested, return only that currency's data
            if currency_id and int(currency_id) in currency_statistics:
                return Response(currency_statistics[int(currency_id)])
            
            # If no specific currency requested, return all currencies
            # For backward compatibility, if only one currency, return its data directly
            if len(currency_statistics) == 1:
                return Response(list(currency_statistics.values())[0])
            
            # Multiple currencies - return grouped data
            return Response({
                'currencies': currency_statistics,
                'generated_at': timezone.now().isoformat(),
                'filters_applied': {
                    'fiscal_year': fiscal_year,
                    'department': department_id,
                    'budget_type': budget_type,
                    'status': status_filter,
                    'currency': currency_id,
                }
            })
            
        except Exception as e:
            # Return a safe fallback response
            return Response({
                'summary': {
                    'currency_id': None,
                    'currency_code': 'Unknown',
                    'currency_name': 'Unknown Currency',
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
    
    
    @action(detail=False, methods=['get'])
    def utilization_matrix(self, request):
        """Get detailed budget utilization metrics for visualization and analysis"""
        try:
            # Get query parameters for filtering
            fiscal_year = request.query_params.get('fiscal_year')
            budget_type = request.query_params.get('budget_type')
            status_filter = request.query_params.get('status')
            currency_id = request.query_params.get('currency')
            department_id = request.query_params.get('department')
            
            # Base queryset
            budgets = self.get_queryset()
            
            # Apply filters EXCEPT currency (we want to see all currencies unless specifically filtered)
            if fiscal_year:
                budgets = budgets.filter(fiscal_year=fiscal_year)
            if budget_type:
                budgets = budgets.filter(budget_type=budget_type)
            if status_filter:
                budgets = budgets.filter(status=status_filter)
            if department_id:
                budgets = budgets.filter(department_id=department_id)
            
            # Only apply currency filter if specifically requested
            # This allows us to see all currencies by default
            if currency_id:
                budgets = budgets.filter(currency_id=currency_id)
            
            # Group budgets by currency
            currency_groups = {}
            for budget in budgets.select_related('currency', 'department'):
                currency_id_key = budget.currency.id if budget.currency else 0
                currency_code = budget.currency.code if budget.currency else 'Unknown'
                currency_name = budget.currency.name if budget.currency else 'Unknown Currency'
                
                if currency_id_key not in currency_groups:
                    currency_groups[currency_id_key] = {
                        'currency_id': currency_id_key,
                        'currency_code': currency_code,
                        'currency_name': currency_name,
                        'budgets': []
                    }
                currency_groups[currency_id_key]['budgets'].append(budget)
            
            # Debug: Log currency groups
            print(f"Found {len(currency_groups)} currency groups:")
            for cid, cdata in currency_groups.items():
                print(f"  Currency {cid} ({cdata['currency_code']}): {len(cdata['budgets'])} budgets")
            
            # Helper functions
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
            
            def safe_percentage(numerator, denominator, default=0.0):
                return safe_divide(numerator, denominator, default) * 100
            
            def calculate_utilization_metrics(currency_budgets, currency_info):
                """Calculate detailed utilization metrics for budgets in a specific currency"""
                
                # Get budget IDs for expense calculation
                budget_ids = [b.id for b in currency_budgets]
                
                # Calculate spent amounts by aggregating from OrganizationalExpense
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
                        print(f"Error calculating expenses: {e}")
                        budget_expenses = {}
                
                # Calculate daily velocity by aggregating recent expenses
                budget_velocity = {}
                if budget_ids:
                    try:
                        # Get expenses from the last 30 days
                        thirty_days_ago = timezone.now() - timedelta(days=30)
                        recent_expenses = OrganizationalExpense.objects.filter(
                            budget_item__budget_id__in=budget_ids,
                            status='paid',
                            payment_date__gte=thirty_days_ago
                        ).values('budget_item__budget_id').annotate(
                            recent_spent=Sum('amount')
                        )
                        
                        for item in recent_expenses:
                            budget_id = item['budget_item__budget_id']
                            recent_spent = item['recent_spent']
                            if recent_spent is not None:
                                # Calculate daily velocity (spending per day)
                                budget_velocity[budget_id] = float(recent_spent) / 30.0
                            else:
                                budget_velocity[budget_id] = 0.0
                    except Exception as e:
                        print(f"Error calculating velocity: {e}")
                        budget_velocity = {}
                
                # Process each budget
                utilization_data = []
                for budget in currency_budgets:
                    try:
                        # Basic metrics
                        budget_id = budget.id
                        budget_name = budget.title or f"Budget #{budget_id}"
                        budget_type = budget.get_budget_type_display() if hasattr(budget, 'get_budget_type_display') else budget.budget_type
                        department_name = budget.department.name if budget.department else "No Department"
                        
                        allocated_amount = float(budget.total_amount) if budget.total_amount else 0.0
                        spent_amount = budget_expenses.get(budget_id, 0.0)
                        remaining_amount = allocated_amount - spent_amount
                        
                        # Calculate utilization percentage
                        utilization = safe_percentage(spent_amount, allocated_amount, 0.0)
                        
                        # Calculate days remaining
                        days_remaining = None
                        if budget.end_date:
                            try:
                                days_remaining = (budget.end_date - timezone.now().date()).days
                                days_remaining = max(0, days_remaining)  # Ensure non-negative
                            except Exception:
                                days_remaining = None
                        
                        # Calculate velocity (spending per day)
                        velocity = budget_velocity.get(budget_id, 0.0)
                        if velocity == 0.0 and days_remaining and days_remaining > 0:
                            # If no recent expenses, estimate based on total spent and time elapsed
                            if budget.start_date:
                                days_elapsed = (timezone.now().date() - budget.start_date).days
                                if days_elapsed > 0:
                                    velocity = safe_divide(spent_amount, days_elapsed, 0.0)
                        
                        # Calculate efficiency score
                        ideal_utilization = 100.0
                        if budget.start_date and budget.end_date and days_remaining is not None:
                            total_days = (budget.end_date - budget.start_date).days
                            days_elapsed = total_days - days_remaining
                            if total_days > 0:
                                ideal_utilization = safe_percentage(days_elapsed, total_days, 0.0)
                        
                        utilization_variance = abs(utilization - ideal_utilization)
                        efficiency_score = max(0, 100 - utilization_variance)
                        
                        # Determine status based on utilization and timeline
                        if utilization > 100:
                            status = "critical"  # Over budget
                        elif utilization >= 95:
                            status = "critical"  # At risk of going over
                        elif utilization >= 85:
                            status = "warning"   # High utilization
                        elif utilization < 50 and ideal_utilization > 75:
                            status = "underutilized"  # Significantly under-utilized
                        else:
                            status = "healthy"   # Healthy utilization
                        
                        # Determine trend based on velocity and remaining budget
                        if velocity > 0 and days_remaining and days_remaining > 0:
                            projected_additional_spend = velocity * days_remaining
                            if (spent_amount + projected_additional_spend) > (allocated_amount * 1.1):
                                trend = "up"  # Trending to exceed budget by 10%+
                            elif (spent_amount + projected_additional_spend) < (allocated_amount * 0.9):
                                trend = "down"  # Trending to underspend by 10%+
                            else:
                                trend = "stable"  # On track to use 90-110% of budget
                        else:
                            trend = "stable"
                        
                        # Calculate risk score (0-100)
                        utilization_risk = 0
                        if utilization > 100:
                            utilization_risk = 100  # Already over budget
                        elif utilization > 90:
                            utilization_risk = 70   # Close to over budget
                        elif utilization < 30 and ideal_utilization > 70:
                            utilization_risk = 60   # Severely under-utilized
                        
                        timeline_risk = 0
                        if days_remaining is not None and days_remaining < 30:
                            if remaining_amount > (allocated_amount * 0.3):
                                timeline_risk = 80  # Significant funds with little time
                            elif remaining_amount > (allocated_amount * 0.15):
                                timeline_risk = 50  # Moderate funds with little time
                        
                        velocity_risk = 0
                        if velocity > 0 and days_remaining and days_remaining > 0:
                            if (velocity * days_remaining) > remaining_amount:
                                velocity_risk = 90  # Will exceed remaining budget at current velocity
                        
                        trend_risk = 0
                        if trend == "up":
                            trend_risk = 60
                        
                        # Combine risk factors with weights
                        risk_score = (
                            utilization_risk * 0.4 +
                            timeline_risk * 0.3 +
                            velocity_risk * 0.2 +
                            trend_risk * 0.1
                        )
                        
                        # Add to utilization data
                        utilization_data.append({
                            'id': budget_id,
                            'name': budget_name,
                            'type': budget_type,
                            'department': department_name,
                            'allocated': allocated_amount,
                            'spent': spent_amount,
                            'remaining': remaining_amount,
                            'utilization': round(utilization, 1),
                            'efficiency': round(efficiency_score, 1),
                            'velocity': round(velocity, 2),
                            'days_remaining': days_remaining,
                            'status': status,
                            'trend': trend,
                            'risk_score': round(risk_score, 1),
                            'start_date': budget.start_date.isoformat() if budget.start_date else None,
                            'end_date': budget.end_date.isoformat() if budget.end_date else None,
                            'fiscal_year': budget.fiscal_year,
                        })
                    except Exception as e:
                        # Log the error but don't skip the budget entirely
                        print(f"Error processing budget {budget.id}: {e}")
                        # Add a minimal entry so we don't lose the budget
                        utilization_data.append({
                            'id': budget.id,
                            'name': budget.title or f"Budget #{budget.id}",
                            'type': budget.budget_type,
                            'department': budget.department.name if budget.department else "No Department",
                            'allocated': float(budget.total_amount) if budget.total_amount else 0.0,
                            'spent': 0.0,
                            'remaining': float(budget.total_amount) if budget.total_amount else 0.0,
                            'utilization': 0.0,
                            'efficiency': 0.0,
                            'velocity': 0.0,
                            'days_remaining': None,
                            'status': 'healthy',
                            'trend': 'stable',
                            'risk_score': 0.0,
                            'start_date': budget.start_date.isoformat() if budget.start_date else None,
                            'end_date': budget.end_date.isoformat() if budget.end_date else None,
                            'fiscal_year': budget.fiscal_year,
                        })
                
                # Sort by risk score (descending)
                utilization_data.sort(key=lambda x: x.get('risk_score', 0), reverse=True)
                
                # Calculate summary metrics
                total_budgets = len(utilization_data)
                if total_budgets > 0:
                    avg_utilization = sum(item['utilization'] for item in utilization_data) / total_budgets
                    avg_efficiency = sum(item['efficiency'] for item in utilization_data) / total_budgets
                    avg_velocity = sum(item['velocity'] for item in utilization_data) / total_budgets
                    high_risk_count = sum(1 for item in utilization_data if item['risk_score'] >= 70)
                else:
                    avg_utilization = 0.0
                    avg_efficiency = 0.0
                    avg_velocity = 0.0
                    high_risk_count = 0
                
                # Prepare scatter data for charts
                scatter_data = [
                    {
                        'x': item['utilization'],
                        'y': item['efficiency'],
                        'z': item['allocated'] / 10000,  # Size of bubble (scaled)
                        'name': item['name'],
                        'status': item['status'],
                        'risk_score': item['risk_score'],
                    }
                    for item in utilization_data
                ]
                
                risk_matrix = [
                    {
                        'name': item['name'],
                        'utilization': item['utilization'],
                        'risk_score': item['risk_score'],
                        'status': item['status'],
                    }
                    for item in utilization_data
                ]
                
                velocity_data = [
                    {
                        'name': item['name'][:15] + ('...' if len(item['name']) > 15 else ''),
                        'velocity': item['velocity'],
                        'utilization': item['utilization'],
                        'efficiency': item['efficiency'],
                        'index': idx,
                    }
                    for idx, item in enumerate(utilization_data)
                ]
                
                return {
                    'currency_info': {
                        'id': currency_info['currency_id'],
                        'code': currency_info['currency_code'],
                        'name': currency_info['currency_name'],
                    },
                    'summary': {
                        'total_budgets': total_budgets,
                        'avg_utilization': round(avg_utilization, 1),
                        'avg_efficiency': round(avg_efficiency, 1),
                        'avg_velocity': round(avg_velocity, 2),
                        'high_risk_count': high_risk_count,
                    },
                    'utilization_data': utilization_data,
                    'scatter_data': scatter_data,
                    'risk_matrix': risk_matrix,
                    'velocity_data': velocity_data,
                }
            
            # Calculate utilization metrics for each currency
            utilization_by_currency = {}
            for currency_id_key, currency_data in currency_groups.items():
                # Process ALL currency groups, even if they have no budgets (for debugging)
                print(f"Processing currency {currency_id_key} with {len(currency_data['budgets'])} budgets")
                
                if currency_data['budgets']:  # Only process currencies with budgets
                    try:
                        utilization_by_currency[str(currency_id_key)] = calculate_utilization_metrics(
                            currency_data['budgets'],
                            currency_data
                        )
                        print(f"Successfully processed currency {currency_id_key}")
                    except Exception as e:
                        print(f"Error processing currency {currency_id_key}: {e}")
                        # Continue processing other currencies
                        continue
                else:
                    print(f"Skipping currency {currency_id_key} - no budgets")
            
            print(f"Final result: {len(utilization_by_currency)} currencies processed")
            
            # If specific currency requested AND it exists, return only that currency's data
            if currency_id and currency_id in utilization_by_currency:
                print(f"Returning single currency data for {currency_id}")
                return Response(utilization_by_currency[currency_id])
            
            # If only one currency exists, return it directly (not wrapped in currencies object)
            if len(utilization_by_currency) == 1:
                single_currency_data = list(utilization_by_currency.values())[0]
                print(f"Returning single currency data (only one available)")
                return Response(single_currency_data)
            
            # Return all currencies
            print(f"Returning multi-currency data with {len(utilization_by_currency)} currencies")
            return Response({
                'currencies': utilization_by_currency,
                'generated_at': timezone.now().isoformat(),
                'filters_applied': {
                    'fiscal_year': fiscal_year,
                    'budget_type': budget_type,
                    'status': status_filter,
                    'currency': currency_id,
                    'department': department_id,
                }
            })
            
        except Exception as e:
            print(f"Major error in utilization_matrix: {e}")
            # Return a safe fallback response
            return Response({
                'currencies': {},
                'generated_at': timezone.now().isoformat(),
                'error': f'Utilization calculation failed: {str(e)}',
                'filters_applied': {}
            })
    @action(detail=False, methods=['get'])
    def health_indicators(self, request):
        """Get comprehensive budget health indicators and alerts"""
        try:
            # Get query parameters for filtering
            fiscal_year = request.query_params.get('fiscal_year')
            budget_type = request.query_params.get('budget_type')
            status_filter = request.query_params.get('status')
            currency_id = request.query_params.get('currency')
            department_id = request.query_params.get('department')
            
            # Base queryset
            budgets = self.get_queryset()
            
            # Apply filters (except currency to see all currencies by default)
            if fiscal_year:
                budgets = budgets.filter(fiscal_year=fiscal_year)
            if budget_type:
                budgets = budgets.filter(budget_type=budget_type)
            if status_filter:
                budgets = budgets.filter(status=status_filter)
            if department_id:
                budgets = budgets.filter(department_id=department_id)
            
            # Only apply currency filter if specifically requested
            if currency_id:
                budgets = budgets.filter(currency_id=currency_id)
            
            # Group budgets by currency
            currency_groups = {}
            for budget in budgets.select_related('currency', 'department'):
                currency_id_key = budget.currency.id if budget.currency else 0
                currency_code = budget.currency.code if budget.currency else 'Unknown'
                currency_name = budget.currency.name if budget.currency else 'Unknown Currency'
                
                if currency_id_key not in currency_groups:
                    currency_groups[currency_id_key] = {
                        'currency_id': currency_id_key,
                        'currency_code': currency_code,
                        'currency_name': currency_name,
                        'budgets': []
                    }
                currency_groups[currency_id_key]['budgets'].append(budget)
            
            # Helper functions
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
            
            def safe_percentage(numerator, denominator, default=0.0):
                return safe_divide(numerator, denominator, default) * 100
            
            def calculate_health_indicators(currency_budgets, currency_info):
                """Calculate comprehensive health indicators for budgets in a specific currency"""
                
                # Get budget IDs for expense calculation
                budget_ids = [b.id for b in currency_budgets]
                
                # Calculate spent amounts by aggregating from OrganizationalExpense
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
                    except Exception:
                        budget_expenses = {}
                
                # Calculate recent spending trends (last 6 months)
                monthly_trends = []
                current_date = timezone.now().date()
                
                for i in range(6):
                    month_start = current_date.replace(day=1) - timedelta(days=i*30)
                    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
                    
                    # Get budgets created in this month
                    month_budgets = [b for b in currency_budgets if b.created_at.date() >= month_start and b.created_at.date() <= month_end]
                    
                    # Calculate health metrics for this month
                    month_health_scores = []
                    month_issues = 0
                    month_warnings = 0
                    
                    for budget in month_budgets:
                        allocated = float(budget.total_amount) if budget.total_amount else 0.0
                        spent = budget_expenses.get(budget.id, 0.0)
                        utilization = safe_percentage(spent, allocated, 0.0)
                        
                        # Calculate health score
                        if utilization > 100:
                            health_score = max(0, 100 - (utilization - 100) * 2)  # Penalize overruns heavily
                            month_issues += 1
                        elif utilization >= 95:
                            health_score = 60  # At risk
                            month_issues += 1
                        elif utilization >= 85:
                            health_score = 75  # Warning
                            month_warnings += 1
                        elif utilization < 50:
                            # Check if budget should be more utilized based on timeline
                            if budget.start_date and budget.end_date:
                                total_days = (budget.end_date - budget.start_date).days
                                days_elapsed = (current_date - budget.start_date).days
                                if total_days > 0:
                                    expected_utilization = safe_percentage(days_elapsed, total_days, 0.0)
                                    if expected_utilization > 75 and utilization < 50:
                                        health_score = 65  # Underutilized
                                        month_warnings += 1
                                    else:
                                        health_score = 85  # Normal early stage
                                else:
                                    health_score = 85
                            else:
                                health_score = 85
                        else:
                            health_score = 90  # Healthy
                        
                        month_health_scores.append(health_score)
                    
                    avg_health = sum(month_health_scores) / len(month_health_scores) if month_health_scores else 0
                    
                    monthly_trends.append({
                        'month': month_start.strftime('%b'),
                        'score': round(avg_health, 1),
                        'issues': month_issues,
                        'warnings': month_warnings,
                    })
                
                monthly_trends.reverse()  # Oldest to newest
                
                # Process each budget for detailed health analysis
                budget_health_data = []
                health_alerts = []
                overall_health_scores = []
                critical_issues = 0
                warnings = 0
                healthy_budgets = 0
                risk_distribution = {'low': 0, 'medium': 0, 'high': 0}
                
                for budget in currency_budgets:
                    try:
                        # Basic metrics
                        budget_id = budget.id
                        budget_name = budget.title or f"Budget #{budget_id}"
                        budget_type = budget.get_budget_type_display() if hasattr(budget, 'get_budget_type_display') else budget.budget_type
                        department_name = budget.department.name if budget.department else "No Department"
                        
                        allocated_amount = float(budget.total_amount) if budget.total_amount else 0.0
                        spent_amount = budget_expenses.get(budget_id, 0.0)
                        remaining_amount = allocated_amount - spent_amount
                        
                        # Calculate utilization percentage
                        utilization = safe_percentage(spent_amount, allocated_amount, 0.0)
                        
                        # Calculate days remaining
                        days_remaining = None
                        if budget.end_date:
                            try:
                                days_remaining = (budget.end_date - timezone.now().date()).days
                                days_remaining = max(0, days_remaining)
                            except Exception:
                                days_remaining = None
                        
                        # Calculate efficiency score
                        ideal_utilization = 100.0
                        if budget.start_date and budget.end_date and days_remaining is not None:
                            total_days = (budget.end_date - budget.start_date).days
                            days_elapsed = total_days - days_remaining
                            if total_days > 0:
                                ideal_utilization = safe_percentage(days_elapsed, total_days, 0.0)
                        
                        utilization_variance = abs(utilization - ideal_utilization)
                        efficiency_score = max(0, 100 - utilization_variance)
                        
                        # Calculate health score (0-100)
                        health_score = 100
                        
                        # Utilization health factor
                        if utilization > 100:
                            health_score -= (utilization - 100) * 2  # Heavy penalty for overruns
                        elif utilization >= 95:
                            health_score -= 25  # At risk
                        elif utilization >= 85:
                            health_score -= 10  # Minor concern
                        elif utilization < 50 and ideal_utilization > 75:
                            health_score -= 20  # Underutilization concern
                        
                        # Timeline health factor
                        if days_remaining is not None:
                            if days_remaining < 7 and remaining_amount > (allocated_amount * 0.2):
                                health_score -= 30  # Critical timeline issue
                            elif days_remaining < 30 and remaining_amount > (allocated_amount * 0.3):
                                health_score -= 15  # Timeline concern
                        
                        # Efficiency health factor
                        if efficiency_score < 60:
                            health_score -= 15
                        elif efficiency_score < 80:
                            health_score -= 5
                        
                        health_score = max(0, min(100, health_score))
                        overall_health_scores.append(health_score)
                        
                        # Determine status and risk level
                        if health_score >= 80:
                            status = "healthy"
                            risk_level = "low"
                            healthy_budgets += 1
                            risk_distribution['low'] += 1
                        elif health_score >= 60:
                            status = "warning"
                            risk_level = "medium"
                            warnings += 1
                            risk_distribution['medium'] += 1
                        else:
                            status = "critical"
                            risk_level = "high"
                            critical_issues += 1
                            risk_distribution['high'] += 1
                        
                        # Generate health alerts
                        alert_timestamp = timezone.now()
                        
                        if utilization > 100:
                            health_alerts.append({
                                'id': f"overrun_{budget_id}",
                                'type': 'critical',
                                'title': 'Budget Overrun',
                                'description': f'{budget_name} has exceeded budget by {formatCurrency(currency_info["currency_code"], spent_amount - allocated_amount)}',
                                'budget': budget_name,
                                'severity': 'high',
                                'action': 'Budget reallocation needed',
                                'timestamp': alert_timestamp.isoformat(),
                                'budget_id': budget_id,
                            })
                        elif utilization >= 95:
                            health_alerts.append({
                                'id': f"atrisk_{budget_id}",
                                'type': 'critical',
                                'title': 'Budget Depletion Risk',
                                'description': f'{budget_name} is {utilization:.1f}% utilized with {days_remaining or "unknown"} days remaining',
                                'budget': budget_name,
                                'severity': 'high',
                                'action': 'Immediate review required',
                                'timestamp': alert_timestamp.isoformat(),
                                'budget_id': budget_id,
                            })
                        elif utilization >= 85:
                            health_alerts.append({
                                'id': f"warning_{budget_id}",
                                'type': 'warning',
                                'title': 'High Utilization Warning',
                                'description': f'{budget_name} is {utilization:.1f}% utilized',
                                'budget': budget_name,
                                'severity': 'medium',
                                'action': 'Monitor spending patterns',
                                'timestamp': alert_timestamp.isoformat(),
                                'budget_id': budget_id,
                            })
                        elif utilization < 50 and ideal_utilization > 75:
                            health_alerts.append({
                                'id': f"underutil_{budget_id}",
                                'type': 'warning',
                                'title': 'Underutilization Alert',
                                'description': f'{budget_name} is only {utilization:.1f}% utilized',
                                'budget': budget_name,
                                'severity': 'low',
                                'action': 'Accelerate spending or reallocate',
                                'timestamp': alert_timestamp.isoformat(),
                                'budget_id': budget_id,
                            })
                        
                        if efficiency_score >= 95:
                            health_alerts.append({
                                'id': f"efficient_{budget_id}",
                                'type': 'info',
                                'title': 'High Efficiency Achievement',
                                'description': f'{budget_name} showing {efficiency_score:.1f}% efficiency rating',
                                'budget': budget_name,
                                'severity': 'low',
                                'action': 'Share best practices',
                                'timestamp': alert_timestamp.isoformat(),
                                'budget_id': budget_id,
                            })
                        
                        # Add to budget health data
                        budget_health_data.append({
                            'id': budget_id,
                            'name': budget_name,
                            'health': round(health_score, 1),
                            'utilization': round(utilization, 1),
                            'efficiency': round(efficiency_score, 1),
                            'risk': round(100 - health_score, 1),  # Inverse of health score
                            'status': status,
                            'risk_level': risk_level,
                            'allocated': allocated_amount,
                            'spent': spent_amount,
                            'remaining': remaining_amount,
                            'days_remaining': days_remaining,
                            'department': department_name,
                            'type': budget_type,
                        })
                        
                    except Exception as e:
                        print(f"Error processing budget {budget.id} for health: {e}")
                        continue
                
                # Sort alerts by severity and timestamp
                health_alerts.sort(key=lambda x: (
                    {'critical': 0, 'warning': 1, 'info': 2}[x['type']],
                    x['timestamp']
                ), reverse=True)
                
                # Limit alerts to most recent 10
                health_alerts = health_alerts[:10]
                
                # Sort budget health data by health score (worst first)
                budget_health_data.sort(key=lambda x: x['health'])
                
                # Calculate overall health score
                overall_score = sum(overall_health_scores) / len(overall_health_scores) if overall_health_scores else 0
                
                # Risk distribution data for charts
                risk_distribution_data = [
                    {'name': 'Low Risk', 'value': risk_distribution['low'], 'color': '#10b981'},
                    {'name': 'Medium Risk', 'value': risk_distribution['medium'], 'color': '#f59e0b'},
                    {'name': 'High Risk', 'value': risk_distribution['high'], 'color': '#ef4444'},
                ]
                
                return {
                    'currency_info': {
                        'id': currency_info['currency_id'],
                        'code': currency_info['currency_code'],
                        'name': currency_info['currency_name'],
                    },
                    'health_metrics': {
                        'overall_score': round(overall_score, 1),
                        'critical_issues': critical_issues,
                        'warnings': warnings,
                        'healthy_budgets': healthy_budgets,
                        'total_budgets': len(currency_budgets),
                        'risk_distribution': risk_distribution,
                        'trends': {
                            'improving': len([b for b in budget_health_data if b['health'] >= 80]),
                            'stable': len([b for b in budget_health_data if 60 <= b['health'] < 80]),
                            'declining': len([b for b in budget_health_data if b['health'] < 60]),
                        }
                    },
                    'health_alerts': health_alerts,
                    'health_trends': monthly_trends,
                    'risk_distribution_data': risk_distribution_data,
                    'budget_health_data': budget_health_data,
                }
            
            # Calculate health indicators for each currency
            health_by_currency = {}
            for currency_id_key, currency_data in currency_groups.items():
                if currency_data['budgets']:  # Only process currencies with budgets
                    try:
                        health_by_currency[str(currency_id_key)] = calculate_health_indicators(
                            currency_data['budgets'],
                            currency_data
                        )
                    except Exception as e:
                        print(f"Error processing health for currency {currency_id_key}: {e}")
                        continue
            
            # If specific currency requested AND it exists, return only that currency's data
            if currency_id and currency_id in health_by_currency:
                return Response(health_by_currency[currency_id])
            
            # If only one currency exists, return it directly
            if len(health_by_currency) == 1:
                single_currency_data = list(health_by_currency.values())[0]
                return Response(single_currency_data)
            
            # Return all currencies
            return Response({
                'currencies': health_by_currency,
                'generated_at': timezone.now().isoformat(),
                'filters_applied': {
                    'fiscal_year': fiscal_year,
                    'budget_type': budget_type,
                    'status': status_filter,
                    'currency': currency_id,
                    'department': department_id,
                }
            })
            
        except Exception as e:
            print(f"Major error in health_indicators: {e}")
            # Return a safe fallback response
            return Response({
                'currencies': {},
                'generated_at': timezone.now().isoformat(),
                'error': f'Health calculation failed: {str(e)}',
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


class BudgetFundingViewSet(ActivityTrackingMixin,viewsets.ModelViewSet):
    queryset = BudgetFunding.objects.all()
    serializer_class = BudgetFundingSerializer
    

    def get_queryset(self):
        queryset = super().get_queryset()
        budget_id = self.request.query_params.get('budget')
        if budget_id:
            queryset = queryset.filter(budget_id=budget_id)
        return queryset

    
class OrganizationalExpenseViewSet(ActivityTrackingMixin,viewsets.ModelViewSet):
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
        expense.currency=expense.budget_item.budget.currency
        expense.save()
        
        # Auto-send notification for submission
        if expense.status == 'pending':
            send_expense_notification(expense, 'submitted')
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve an expense"""
        expense = self.get_object()
        
        if expense.status not in [ 'pending','draft' ] :
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
                budget = expense.budget_item.budget
                spent_percentage = budget.spent_percentage
                if spent_percentage >= 100:
                    send_budget_notification(budget, 'exceeded')
                elif spent_percentage >= 90:
                    send_budget_notification(budget, 'alert_90')
                elif spent_percentage >= 80:
                    send_budget_notification(budget, 'alert_80')
            self.log_activity(
                user=request.user,
                action='APPROVE',
                instance=expense,
                details={
                    'approved_by': request.user.username,
                    'approval_date': timezone.now().isoformat(),
                    **self.get_request_metadata(request)
                }
            )
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
class DashboardViewSet(ActivityTrackingMixin,viewsets.ViewSet):
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

class GrantReportViewSet(ActivityTrackingMixin,viewsets.ModelViewSet):
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

class FundingSourceViewSet(ActivityTrackingMixin,viewsets.ModelViewSet):
    queryset = FundingSource.objects.select_related('currency', 'created_by')
    serializer_class = FundingSourceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['funding_type', 'currency', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'total_amount', 'created_at']
    ordering = ['name']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        exclude_ids_raw = self.request.query_params.getlist('exclude_ids')

        exclude_ids = []
        for item in exclude_ids_raw:
            if ',' in item:
                exclude_ids.extend(item.split(','))
            else:
                exclude_ids.append(item)

        try:
            exclude_ids = [int(i) for i in exclude_ids if i.strip().isdigit()]
        except ValueError:
            exclude_ids = []

        if exclude_ids:
            queryset = queryset.exclude(id__in=exclude_ids)

        return queryset



    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['get'])
    def allocation_history(self, request, pk=None):
        """Get allocation history for funding source"""
        funding_source = self.get_object()
        allocations = funding_source.allocations.select_related('budget').order_by('-allocation_date')
        
        allocation_data = []
        for allocation in allocations:
            allocation_data.append({
                'budget_title': allocation.budget.title,
                'budget_id': allocation.budget.id,
                'amount_allocated': float(allocation.amount_allocated),
                'allocation_date': allocation.allocation_date.date(),
                'budget_status': allocation.budget.status
            })
        
        return Response({
            'funding_source': funding_source.name,
            'total_amount': float(funding_source.amount_available),
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

class BudgetItemViewSet(ActivityTrackingMixin,viewsets.ModelViewSet,):

    queryset = BudgetItem.objects.select_related('budget', 'created_by')
    serializer_class = BudgetItemSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['budget', 'category']
    search_fields = [ 'description']
    ordering_fields = [ 'allocated_amount', 'spent_amount', 'created_at']
    # ordering = ['title']

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

class AccountTransactionViewSet(ActivityTrackingMixin,viewsets.ModelViewSet):
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

class FundAllocationViewSet(ActivityTrackingMixin,viewsets.ModelViewSet):
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
        serializer.save(allocated_by=self.request.user,)
    
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
