from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Count, Avg, Q, F, Case, When, Value, DecimalField
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import calendar
from django.db import transaction
from django.core.exceptions import ValidationError

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
    queryset = FinancialInstitution.objects.all()
    serializer_class = FinancialInstitutionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'code', 'branch_name']
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
        
        if start_date:
            transactions = transactions.filter(transaction_date__gte=start_date)
        if end_date:
            transactions = transactions.filter(transaction_date__lte=end_date)
        if transaction_type:
            transactions = transactions.filter(transaction_type=transaction_type)
        if status_filter:
            transactions = transactions.filter(status=status_filter)
        
        # Pagination
        page = self.paginate_queryset(transactions)
        if page is not None:
            serializer = AccountTransactionSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = AccountTransactionSerializer(transactions, many=True)
        return Response(serializer.data)
    
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
        
        return Response(balance_history)
    
    @action(detail=True, methods=['post'])
    def check_low_balance(self, request, pk=None):
        """Check and alert for low balance"""
        account = self.get_object()
        threshold = Decimal(request.data.get('threshold', '1000.00'))
        
        if account.current_balance < threshold:
            send_account_notification(account, 'low_balance', threshold=threshold)
            return Response({
                'alert': True,
                'message': f'Low balance alert sent for {account.name}',
                'balance': account.current_balance,
                'threshold': threshold
            })
        
        return Response({
            'alert': False,
            'message': 'Balance is above threshold',
            'balance': account.current_balance,
            'threshold': threshold
        })
    
    @action(detail=True, methods=['post'])
    def freeze(self, request, pk=None):
        """Freeze account (prevent new transactions)"""
        account = self.get_object()
        account.is_active = False
        account.save()
        
        return Response({
            'message': f'Account {account.name} has been frozen',
            'status': 'frozen'
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
        
        # Apply filters
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        min_amount = request.query_params.get('min_amount')
        max_amount = request.query_params.get('max_amount')
        
        if start_date:
            donations = donations.filter(donation_date__gte=start_date)
        if end_date:
            donations = donations.filter(donation_date__lte=end_date)
        if min_amount:
            donations = donations.filter(amount__gte=min_amount)
        if max_amount:
            donations = donations.filter(amount__lte=max_amount)
        
        page = self.paginate_queryset(donations)
        if page is not None:
            serializer = DonationSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = DonationSerializer(donations, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def detailed_statistics(self, request, pk=None):
        """Get comprehensive statistics for a campaign"""
        campaign = self.get_object()
        donations = campaign.donations.filter(status='completed')
        
        # Basic stats
        total_donations = donations.count()
        total_raised = campaign.current_amount_in_target_currency
        unique_donors = donations.values('donor').distinct().count()
        anonymous_donations = donations.filter(is_anonymous=True).count()
        
        # Payment method breakdown
        payment_methods = donations.values('payment_method').annotate(
            count=Count('id'),
            total=Sum('amount')
        ).order_by('-total')
        
        # Daily donation trends (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        daily_donations = donations.filter(
            donation_date__gte=thirty_days_ago
        ).extra(
            select={'day': 'date(donation_date)'}
        ).values('day').annotate(
            count=Count('id'),
            total=Sum('amount')
        ).order_by('day')
        
        # Donor segments
        donor_segments = {
            'small': donations.filter(amount__lt=100).count(),
            'medium': donations.filter(amount__gte=100, amount__lt=1000).count(),
            'large': donations.filter(amount__gte=1000, amount__lt=5000).count(),
            'major': donations.filter(amount__gte=5000).count(),
        }
        
        # Time-based analysis
        days_active = (timezone.now().date() - campaign.start_date).days + 1
        days_remaining = (campaign.end_date - timezone.now().date()).days
        avg_daily_raised = total_raised / days_active if days_active > 0 else 0
        projected_total = avg_daily_raised * (days_active + max(days_remaining, 0))
        
        stats = {
            'campaign_info': {
                'id': campaign.id,
                'title': campaign.title,
                'target_amount': campaign.target_amount,
                'currency': campaign.target_currency.code,
                'start_date': campaign.start_date,
                'end_date': campaign.end_date,
                'days_active': days_active,
                'days_remaining': days_remaining,
                'is_active': campaign.is_active
            },
            'financial_summary': {
                'total_raised': total_raised,
                'target_amount': campaign.target_amount,
                'progress_percentage': campaign.progress_percentage,
                'amount_remaining': campaign.target_amount - total_raised,
                'avg_daily_raised': avg_daily_raised,
                'projected_total': projected_total,
                'is_on_track': projected_total >= campaign.target_amount
            },
            'donation_summary': {
                'total_donations': total_donations,
                'unique_donors': unique_donors,
                'anonymous_donations': anonymous_donations,
                'repeat_donors': total_donations - unique_donors,
                'average_donation': donations.aggregate(avg=Avg('amount'))['avg'] or 0,
                'largest_donation': donations.aggregate(max=Sum('amount'))['max'] or 0,
                'smallest_donation': donations.aggregate(min=Sum('amount'))['min'] or 0
            },
            'donor_segments': donor_segments,
            'payment_methods': list(payment_methods),
            'daily_trends': list(daily_donations),
            'milestones': {
                '25_percent': total_raised >= (campaign.target_amount * Decimal('0.25')),
                '50_percent': total_raised >= (campaign.target_amount * Decimal('0.50')),
                '75_percent': total_raised >= (campaign.target_amount * Decimal('0.75')),
                '100_percent': total_raised >= campaign.target_amount
            }
        }
        
        return Response(stats)
    
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
            'progress_percentage': progress,
            'milestones_reached': milestones_reached,
            'notifications_sent': len(milestones_reached)
        })
    
    @action(detail=True, methods=['post'])
    def extend_deadline(self, request, pk=None):
        """Extend campaign deadline"""
        campaign = self.get_object()
        new_end_date = request.data.get('new_end_date')
        
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
            campaign.save()
            
            return Response({
                'message': f'Campaign deadline extended from {old_date} to {new_date}',
                'old_end_date': old_date,
                'new_end_date': new_date
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
        
        send_budget_notification(budget, 'approved')
        
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
            send_budget_notification(budget, 'exceeded')
            alerts_sent.append('exceeded')
        elif spent_percentage >= 90:
            send_budget_notification(budget, 'alert_90')
            alerts_sent.append('90_percent')
        elif spent_percentage >= 80:
            send_budget_notification(budget, 'alert_80')
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
        
        # Check if funding source has enough remaining funds
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
        budgets_qs = Budget.objects.filter(status='active')
        
        # Apply date filters
        if start_date:
            donations_qs = donations_qs.filter(donation_date__gte=start_date)
            expenses_qs = expenses_qs.filter(expense_date__gte=start_date)
        
        # Calculate totals
        total_donations = donations_qs.aggregate(total=Sum('amount'))['total'] or 0
        total_grants_received = grants_qs.aggregate(total=Sum('amount_received'))['total'] or 0
        total_expenses = expenses_qs.aggregate(total=Sum('amount'))['total'] or 0
        total_budget_allocated = budgets_qs.aggregate(total=Sum('total_amount'))['total'] or 0
        total_budget_spent = budgets_qs.aggregate(total=Sum('spent_amount'))['total'] or 0
        
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
        payment_methods = donations.values('payment_method').annotate(
            count=Count('id'),
            total=Sum('amount'),
            percentage=Count('id') * 100.0 / donations.count()
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
    def budget_performance(self, request):
        """Get budget performance analytics"""
        fiscal_year = request.query_params.get('fiscal_year')
        
        budgets = Budget.objects.filter(status__in=['active', 'completed'])
        if fiscal_year:
            budgets = budgets.filter(fiscal_year=fiscal_year)
        
        # Budget utilization by type
        budget_by_type = budgets.values('budget_type').annotate(
            count=Count('id'),
            total_allocated=Sum('total_amount'),
            total_spent=Sum('spent_amount'),
            avg_utilization=Avg(
                Case(
                    When(total_amount__gt=0, then=F('spent_amount') * 100.0 / F('total_amount')),
                    default=Value(0),
                    output_field=DecimalField()
                )
            )
        ).order_by('-total_allocated')
        
        # Department budget analysis
        dept_budgets = budgets.filter(department__isnull=False).values(
            'department__name'
        ).annotate(
            total_allocated=Sum('total_amount'),
            total_spent=Sum('spent_amount'),
            utilization=Sum('spent_amount') * 100.0 / Sum('total_amount')
        ).order_by('-total_allocated')
        
        # Budget alerts
        over_budget = budgets.filter(spent_amount__gt=F('total_amount')).count()
        near_limit = budgets.annotate(
            utilization=F('spent_amount') * 100.0 / F('total_amount')
        ).filter(utilization__gte=90, utilization__lt=100).count()
        
        # Monthly spending trends
        monthly_spending = OrganizationalExpense.objects.filter(
            status='paid',
            expense_date__gte=timezone.now() - timedelta(days=365)
        ).extra(
            select={'month': "date_trunc('month', expense_date)"}
        ).values('month').annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('month')
        
        performance = {
            'summary': {
                'total_budgets': budgets.count(),
                'total_allocated': budgets.aggregate(total=Sum('total_amount'))['total'] or 0,
                'total_spent': budgets.aggregate(total=Sum('spent_amount'))['total'] or 0,
                'overall_utilization': budgets.aggregate(
                    utilization=Sum('spent_amount') * 100.0 / Sum('total_amount')
                )['utilization'] or 0
            },
            'alerts': {
                'over_budget_count': over_budget,
                'near_limit_count': near_limit,
                'total_alerts': over_budget + near_limit
            },
            'by_type': list(budget_by_type),
            'by_department': list(dept_budgets),
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
        
        # Disbursement tracking
        active_grants = grants.filter(status='active')
        disbursement_summary = {
            'total_approved': active_grants.aggregate(total=Sum('amount'))['total'] or 0,
            'total_received': active_grants.aggregate(total=Sum('amount_received'))['total'] or 0,
            'pending_disbursement': active_grants.aggregate(
                pending=Sum(F('amount') - F('amount_received'))
            )['pending'] or 0
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
        days_ahead = int(request.query_params.get('days', 90))
        
        # Current balance
        current_balance = sum(
            account.current_balance 
            for account in BankAccount.objects.filter(is_active=True)
        )
        
        # Projected income
        # Recurring donations
        recurring_income = RecurringDonation.objects.filter(
            status='active',
            next_payment_date__lte=timezone.now().date() + timedelta(days=days_ahead)
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Expected grant disbursements
        expected_grants = Grant.objects.filter(
            status='active'
        ).aggregate(
            pending=Sum(F('amount') - F('amount_received'))
        )['pending'] or 0
        
        # Projected expenses
        # Approved but unpaid expenses
        pending_expenses = OrganizationalExpense.objects.filter(
            status='approved'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Monthly recurring expenses (estimate based on last 3 months)
        avg_monthly_expenses = OrganizationalExpense.objects.filter(
            status='paid',
            expense_date__gte=timezone.now().date() - timedelta(days=90)
        ).aggregate(avg=Avg('amount'))['avg'] or 0
        
        projected_monthly_expenses = avg_monthly_expenses * (days_ahead / 30)
        
        # Calculate forecast
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
                'healthy' if projected_balance > current_balance * 0.5 
                else 'concerning' if projected_balance > 0 
                else 'critical'
            )
        }
        
        return Response(forecast)
