from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Count, Avg, Q, F
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import pytz

from ..models import (
    DonationCampaign, Donation, RecurringDonation, InKindDonation,
    Grant, GrantReport, Budget, BudgetItem, OrganizationalExpense
)
from .serializers import (
    DonationCampaignSerializer, DonationSerializer, RecurringDonationSerializer,
    InKindDonationSerializer, GrantSerializer, GrantReportSerializer,
    BudgetSerializer, BudgetItemSerializer, OrganizationalExpenseSerializer,
    FinanceSummarySerializer, DonationStatsSerializer, ProjectExpenseBudgetLinkSerializer
)
from .notification_utils import (
    send_donation_received_notification, send_campaign_milestone_notification,
    send_grant_status_notification, send_budget_alert_notification,
    send_expense_approval_notification, send_recurring_donation_notification
)

class DonationCampaignViewSet(viewsets.ModelViewSet):
    queryset = DonationCampaign.objects.all()
    serializer_class = DonationCampaignSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'is_featured', 'project']
    search_fields = ['title', 'description', 'grantor']
    ordering_fields = ['created_at', 'start_date', 'end_date', 'target_amount']
    ordering = ['-created_at']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get active campaigns"""
        active_campaigns = self.queryset.filter(
            is_active=True,
            start_date__lte=timezone.now().date(),
            end_date__gte=timezone.now().date()
        )
        serializer = self.get_serializer(active_campaigns, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured campaigns"""
        featured_campaigns = self.queryset.filter(is_featured=True, is_active=True)
        serializer = self.get_serializer(featured_campaigns, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def donations(self, request, pk=None):
        """Get donations for a specific campaign"""
        campaign = self.get_object()
        donations = campaign.donations.filter(status='completed')
        serializer = DonationSerializer(donations, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Get campaign statistics"""
        campaign = self.get_object()
        donations = campaign.donations.filter(status='completed')
        
        stats = {
            'total_raised': donations.aggregate(total=Sum('amount'))['total'] or 0,
            'donations_count': donations.count(),
            'average_donation': donations.aggregate(avg=Avg('amount'))['avg'] or 0,
            'progress_percentage': campaign.progress_percentage,
            'days_remaining': (campaign.end_date - timezone.now().date()).days if campaign.end_date > timezone.now().date() else 0,
            'unique_donors': donations.values('donor').distinct().count(),
        }
        
        return Response(stats)

class DonationViewSet(viewsets.ModelViewSet):
    queryset = Donation.objects.all()
    serializer_class = DonationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'donation_type', 'campaign', 'project', 'donor']
    search_fields = ['donor_name', 'notes', 'transaction_id']
    ordering_fields = ['donation_date', 'amount', 'created_at']
    ordering = ['-donation_date']

    def perform_create(self, serializer):
        donation = serializer.save(processed_by=self.request.user)
        
        # Send notification for completed donations
        if donation.status == 'completed':
            send_donation_received_notification(donation)
            
            # Update campaign current amount if applicable
            if donation.campaign:
                campaign = donation.campaign
                campaign.current_amount += donation.amount
                campaign.save()
                
                # Check for milestones
                progress = campaign.progress_percentage
                if progress >= 100:
                    send_campaign_milestone_notification(campaign, 'target_reached')
                elif progress >= 75:
                    send_campaign_milestone_notification(campaign, '75_percent')
                elif progress >= 50:
                    send_campaign_milestone_notification(campaign, '50_percent')

    def perform_update(self, serializer):
        old_status = self.get_object().status
        donation = serializer.save()
        
        # Handle status changes
        if old_status != donation.status and donation.status == 'completed':
            send_donation_received_notification(donation)

    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recent donations"""
        recent_donations = self.queryset.filter(
            donation_date__gte=timezone.now() - timedelta(days=30)
        ).order_by('-donation_date')[:10]
        serializer = self.get_serializer(recent_donations, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get donation statistics"""
        donations = self.queryset.filter(status='completed')
        
        # Get date range from query params
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if start_date:
            donations = donations.filter(donation_date__gte=start_date)
        if end_date:
            donations = donations.filter(donation_date__lte=end_date)
        
        # Get top donors (add this section)
        top_donors = []
        if not donations.filter(is_anonymous=True).exists():
            donor_stats = donations.values('donor', 'donor_name').annotate(
                total=Sum('amount'),
                count=Count('id')
            ).order_by('-total')[:5]
            
            top_donors = [
                {
                    'donor_id': item['donor'],
                    'donor_name': item['donor_name'] or 'Unknown',
                    'total': item['total'],
                    'count': item['count']
                } for item in donor_stats if item['donor'] or item['donor_name']
            ]
        
        stats = {
            'total_amount': donations.aggregate(total=Sum('amount'))['total'] or 0,
            'total_count': donations.count(),
            'average_amount': donations.aggregate(avg=Avg('amount'))['avg'] or 0,
            'unique_donors': donations.values('donor').distinct().count(),
            'by_type': donations.values('donation_type').annotate(
                count=Count('id'),
                total=Sum('amount')
            ),
            'monthly_trend': self._get_monthly_trend(donations),
            'top_donors': top_donors,  # Make sure this is included
        }
        
        serializer = DonationStatsSerializer(stats)
        return Response(serializer.data)

    def _get_monthly_trend(self, donations):
        """Get monthly donation trend for the last 12 months"""
        trend = []
        for i in range(12):
            month_start = timezone.now().replace(day=1) - timedelta(days=30*i)
            month_end = month_start.replace(day=28) + timedelta(days=4)
            month_end = month_end - timedelta(days=month_end.day)
            
            month_donations = donations.filter(
                donation_date__gte=month_start,
                donation_date__lte=month_end
            )
            
            trend.append({
                'month': month_start.strftime('%Y-%m'),
                'amount': month_donations.aggregate(total=Sum('amount'))['total'] or 0,
                'count': month_donations.count()
            })
        
        return list(reversed(trend))

class RecurringDonationViewSet(viewsets.ModelViewSet):
    queryset = RecurringDonation.objects.all()
    serializer_class = RecurringDonationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'frequency', 'donor', 'campaign', 'project']
    search_fields = ['donor__first_name', 'donor__last_name', 'notes']
    ordering_fields = ['start_date', 'amount', 'created_at']
    ordering = ['-created_at']

    def perform_create(self, serializer):
        recurring_donation = serializer.save()
        send_recurring_donation_notification(recurring_donation, 'recurring_donation_created')

    def perform_update(self, serializer):
        old_status = self.get_object().status
        recurring_donation = serializer.save()
        
        if old_status != recurring_donation.status and recurring_donation.status == 'cancelled':
            send_recurring_donation_notification(recurring_donation, 'recurring_donation_cancelled')

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get active recurring donations"""
        active_donations = self.queryset.filter(status='active')
        serializer = self.get_serializer(active_donations, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """Pause a recurring donation"""
        recurring_donation = self.get_object()
        recurring_donation.status = 'paused'
        recurring_donation.save()
        return Response({'status': 'paused'})

    @action(detail=True, methods=['post'])
    def resume(self, request, pk=None):
        """Resume a paused recurring donation"""
        recurring_donation = self.get_object()
        if recurring_donation.status == 'paused':
            recurring_donation.status = 'active'
            recurring_donation.save()
            return Response({'status': 'resumed'})
        return Response({'error': 'Can only resume paused donations'}, status=status.HTTP_400_BAD_REQUEST)

class InKindDonationViewSet(viewsets.ModelViewSet):
    queryset = InKindDonation.objects.all()
    serializer_class = InKindDonationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'category', 'donor', 'campaign', 'project']
    search_fields = ['item_description', 'donor_name', 'notes']
    ordering_fields = ['donation_date', 'estimated_value', 'created_at']
    ordering = ['-donation_date']

    @action(detail=True, methods=['post'])
    def mark_received(self, request, pk=None):
        """Mark in-kind donation as received"""
        donation = self.get_object()
        donation.status = 'received'
        donation.received_date = timezone.now().date()
        donation.received_by = request.user
        donation.save()
        return Response({'status': 'received'})

class GrantViewSet(viewsets.ModelViewSet):
    queryset = Grant.objects.all()
    serializer_class = GrantSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'grantor_type', 'project']
    search_fields = ['title', 'description', 'grantor']
    ordering_fields = ['created_at', 'submission_date', 'amount']
    ordering = ['-created_at']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        old_status = self.get_object().status
        grant = serializer.save()
        
        if old_status != grant.status:
            send_grant_status_notification(grant, old_status, grant.status)

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get active grants"""
        active_grants = self.queryset.filter(status='active')
        serializer = self.get_serializer(active_grants, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Get pending grants"""
        pending_grants = self.queryset.filter(status__in=['submitted', 'under_review'])
        serializer = self.get_serializer(pending_grants, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def reports(self, request, pk=None):
        """Get reports for a specific grant"""
        grant = self.get_object()
        reports = grant.reports.all()
        serializer = GrantReportSerializer(reports, many=True)
        return Response(serializer.data)

class GrantReportViewSet(viewsets.ModelViewSet):
    queryset = GrantReport.objects.all()
    serializer_class = GrantReportSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'report_type', 'grant']
    search_fields = ['title', 'narrative']
    ordering_fields = ['created_at', 'due_date', 'submission_date']
    ordering = ['-created_at']

    def perform_create(self, serializer):
        serializer.save(submitted_by=self.request.user)

    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Get overdue reports"""
        overdue_reports = self.queryset.filter(
            due_date__lt=timezone.now().date(),
            status__in=['draft', 'revision_required']
        )
        serializer = self.get_serializer(overdue_reports, many=True)
        return Response(serializer.data)

class BudgetViewSet(viewsets.ModelViewSet):
    queryset = Budget.objects.all()
    serializer_class = BudgetSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['budget_type', 'status', 'project', 'campaign', 'grant']
    search_fields = ['title', 'notes']
    ordering_fields = ['created_at', 'start_date', 'total_amount']
    ordering = ['-created_at']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        old_status = self.get_object().status
        budget = serializer.save()
        
        if old_status != budget.status and budget.status == 'approved':
            budget.approved_by = self.request.user
            budget.approved_at = timezone.now()
            budget.save()
            send_budget_alert_notification(budget, 'approved')
        
        # Check for spending alerts
        if budget.spent_percentage >= 90:
            send_budget_alert_notification(budget, '90_percent')
        elif budget.spent_percentage >= 80:
            send_budget_alert_notification(budget, '80_percent')
        elif budget.spent_amount > budget.total_amount:
            send_budget_alert_notification(budget, 'overspent')

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get active budgets"""
        active_budgets = self.queryset.filter(status='active')
        serializer = self.get_serializer(active_budgets, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a budget"""
        budget = self.get_object()
        budget.status = 'approved'
        budget.approved_by = request.user
        budget.approved_at = timezone.now()
        budget.save()
        send_budget_alert_notification(budget, 'approved')
        return Response({'status': 'approved'})

class BudgetItemViewSet(viewsets.ModelViewSet):
    queryset = BudgetItem.objects.all()
    serializer_class = BudgetItemSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['budget', 'category']
    search_fields = ['description', 'category', 'subcategory']
    ordering_fields = ['budgeted_amount', 'spent_amount', 'created_at']
    ordering = ['category', 'subcategory']

    @action(detail=False, methods=['get'])
    def by_budget(self, request):
        """Get budget items by budget ID"""
        budget_id = request.query_params.get('budget_id')
        if budget_id:
            items = self.queryset.filter(budget_id=budget_id)
            serializer = self.get_serializer(items, many=True)
            return Response(serializer.data)
        return Response({'error': 'budget_id parameter required'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def link_project_expense(self, request, pk=None):
        """Link a project expense to this budget item"""
        budget_item = self.get_object()
        serializer = ProjectExpenseBudgetLinkSerializer(data=request.data)
        
        if serializer.is_valid():
            from mainapps.project.models import ProjectExpense
            try:
                project_expense = ProjectExpense.objects.get(
                    id=serializer.validated_data['project_expense_id']
                )
                budget_item.project_expenses.add(project_expense)
                
                # Update budget item spent amount
                total_project_expenses = budget_item.project_expenses.filter(
                    status='reimbursed'
                ).aggregate(total=Sum('amount'))['total'] or 0
                
                total_org_expenses = budget_item.organizational_expenses.filter(
                    status='approved'
                ).aggregate(total=Sum('amount'))['total'] or 0
                
                budget_item.spent_amount = total_project_expenses + total_org_expenses
                budget_item.save()
                
                return Response({'status': 'linked'})
            except ProjectExpense.DoesNotExist:
                return Response({'error': 'Project expense not found'}, status=404)
        
        return Response(serializer.errors, status=400)

class OrganizationalExpenseViewSet(viewsets.ModelViewSet):
    queryset = OrganizationalExpense.objects.all()
    serializer_class = OrganizationalExpenseSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'expense_type', 'submitted_by']
    search_fields = ['title', 'description', 'vendor']
    ordering_fields = ['expense_date', 'amount', 'created_at']
    ordering = ['-expense_date']

    def perform_create(self, serializer):
        serializer.save(submitted_by=self.request.user)

    def perform_update(self, serializer):
        old_status = self.get_object().status
        expense = serializer.save()
        
        if old_status != expense.status and expense.status in ['approved', 'rejected']:
            expense.approved_by = self.request.user
            expense.approved_at = timezone.now()
            expense.save()
            send_expense_approval_notification(expense, self.request.user)

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Get pending organizational expenses"""
        pending_expenses = self.queryset.filter(status='pending')
        serializer = self.get_serializer(pending_expenses, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve an organizational expense"""
        expense = self.get_object()
        expense.status = 'approved'
        expense.approved_by = request.user
        expense.approved_at = timezone.now()
        expense.save()
        
        # Update budget item spent amount
        if expense.budget_item:
            expense.budget_item.spent_amount += expense.amount
            expense.budget_item.save()
            
            # Update budget spent amount
            budget = expense.budget_item.budget
            budget.spent_amount = budget.items.aggregate(
                total=Sum('spent_amount')
            )['total'] or 0
            budget.save()
        
        send_expense_approval_notification(expense, request.user)
        return Response({'status': 'approved'})

# Dashboard and summary views
class FinanceDashboardViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get finance summary for dashboard"""
        # Get date range from query params
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        # Default to current year if no dates provided
        if not start_date:
            start_date = timezone.now().replace(month=1, day=1).date()
        if not end_date:
            end_date = timezone.now().date()
        
        # Calculate totals
        donations = Donation.objects.filter(
            status='completed',
            donation_date__range=[start_date, end_date]
        )
        grants = Grant.objects.filter(
            status__in=['approved', 'active', 'completed'],
            approval_date__range=[start_date, end_date]
        )
        expenses = OrganizationalExpense.objects.filter(
            status='approved',
            expense_date__range=[start_date, end_date]
        )
        
        # Monthly data for current year
        current_month_start = timezone.now().replace(day=1).date()
        monthly_donations = donations.filter(donation_date__gte=current_month_start)
        monthly_expenses = expenses.filter(expense_date__gte=current_month_start)
        
        summary_data = {
            'total_donations': donations.aggregate(total=Sum('amount'))['total'] or 0,
            'total_grants': grants.aggregate(total=Sum('amount'))['total'] or 0,
            'total_expenses': expenses.aggregate(total=Sum('amount'))['total'] or 0,
            'active_campaigns': DonationCampaign.objects.filter(is_active=True).count(),
            'pending_expenses': OrganizationalExpense.objects.filter(status='pending').count(),
            'monthly_donations': monthly_donations.aggregate(total=Sum('amount'))['total'] or 0,
            'monthly_expenses': monthly_expenses.aggregate(total=Sum('amount'))['total'] or 0,
        }
        
        serializer = FinanceSummarySerializer(summary_data)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def charts(self, request):
        """Get chart data for dashboard"""
        # Monthly trend for the last 12 months
        monthly_data = []
        for i in range(12):
            month_start = timezone.now().replace(day=1) - timedelta(days=30*i)
            month_end = month_start.replace(day=28) + timedelta(days=4)
            month_end = month_end - timedelta(days=month_end.day)
            
            month_donations = Donation.objects.filter(
                status='completed',
                donation_date__range=[month_start, month_end]
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            month_expenses = OrganizationalExpense.objects.filter(
                status='approved',
                expense_date__range=[month_start, month_end]
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            monthly_data.append({
                'month': month_start.strftime('%Y-%m'),
                'donations': float(month_donations),
                'expenses': float(month_expenses),
                'net': float(month_donations - month_expenses)
            })
        
        # Donation by type
        donation_types = Donation.objects.filter(status='completed').values('donation_type').annotate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        # Campaign performance
        campaign_performance = DonationCampaign.objects.filter(is_active=True).annotate(
            raised=Sum('donations__amount', filter=Q(donations__status='completed'))
        ).values('title', 'target_amount', 'raised')[:10]
        
        return Response({
            'monthly_trend': list(reversed(monthly_data)),
            'donation_types': list(donation_types),
            'campaign_performance': list(campaign_performance)
        })
        
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get comprehensive finance statistics for dashboard"""
        # Get date range from query params
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        
        # Default to current year if no dates provided
        default_tz = timezone.get_current_timezone()
        
        if not start_date_str:
            start_date = timezone.now().replace(month=1, day=1)
        else:
            # Parse the date string and make it timezone-aware
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            start_date = default_tz.localize(start_date)
            
        if not end_date_str:
            end_date = timezone.now()
        else:
            # Parse the date string and make it timezone-aware
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            # Set to end of day
            end_date = default_tz.localize(end_date.replace(hour=23, minute=59, second=59))
            
        # Previous period for comparison (same length as selected period)
        period_length = (end_date - start_date).days
        prev_end_date = start_date - timedelta(days=1)
        prev_start_date = prev_end_date - timedelta(days=period_length)
        
        # Filter data based on date range
        donations = Donation.objects.filter(
            status='completed',
            donation_date__gte=start_date,
            donation_date__lte=end_date
        )
        prev_donations = Donation.objects.filter(
            status='completed',
            donation_date__gte=prev_start_date,
            donation_date__lte=prev_end_date
        )
        
        campaigns = DonationCampaign.objects.filter(
            is_active=True,
            start_date__lte=end_date.date(),
            end_date__gte=start_date.date()
        )
        
        expenses = OrganizationalExpense.objects.filter(
            expense_date__gte=start_date,
            expense_date__lte=end_date
        )
        prev_expenses = OrganizationalExpense.objects.filter(
            expense_date__gte=prev_start_date,
            expense_date__lte=prev_end_date
        )
        
        budgets = Budget.objects.filter(
            start_date__lte=end_date.date(),
            end_date__gte=start_date.date()
        )
        
        # Calculate donation statistics
        donation_total = donations.aggregate(total=Sum('amount'))['total'] or 0
        prev_donation_total = prev_donations.aggregate(total=Sum('amount'))['total'] or 0
        donation_growth = 0
        if prev_donation_total > 0:
            donation_growth = ((donation_total - prev_donation_total) / prev_donation_total) * 100
            
        # Get recent donations
        recent_donations = donations.order_by('-donation_date')[:5].values(
            'id', 'amount', 'donation_date', 'donor_name', 'is_anonymous',
            'donor', 'status'
        )
        
        # Add donor details to recent donations
        for donation in recent_donations:
            if donation['donor']:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    user = User.objects.get(id=donation['donor'])
                    donation['donor_details'] = {
                        'name': user.get_full_name() or user.username,
                        'email': user.email
                    }
                except User.DoesNotExist:
                    donation['donor_details'] = None
            else:
                donation['donor_details'] = None
            
            # Convert date to string for JSON serialization
            donation['date'] = donation['donation_date'].isoformat()
            
        # Calculate campaign statistics
        active_campaigns = campaigns.count()
        total_raised = campaigns.annotate(
            raised=Sum('donations__amount', filter=Q(donations__status='completed'))
        ).aggregate(total=Sum('raised'))['total'] or 0
        total_target = campaigns.aggregate(total=Sum('target_amount'))['total'] or 0
        success_rate = 0
        if active_campaigns > 0:
            completed_campaigns = campaigns.filter(current_amount__gte=F('target_amount')).count()
            success_rate = (completed_campaigns / active_campaigns) * 100
            
        # Calculate expense statistics
        expense_total = expenses.filter(status='approved').aggregate(total=Sum('amount'))['total'] or 0
        pending_amount = expenses.filter(status='pending').aggregate(total=Sum('amount'))['total'] or 0
        prev_expense_total = prev_expenses.filter(status='approved').aggregate(total=Sum('amount'))['total'] or 0
        expense_growth = 0
        if prev_expense_total > 0:
            expense_growth = ((expense_total - prev_expense_total) / prev_expense_total) * 100
            
        approval_rate = 0
        total_expenses = expenses.count()
        if total_expenses > 0:
            approved_expenses = expenses.filter(status='approved').count()
            approval_rate = (approved_expenses / total_expenses) * 100
            
        # Get recent expenses
        recent_expenses = expenses.order_by('-expense_date')[:5].values(
            'id', 'amount', 'expense_date', 'title', 'description', 'status'
        )
        
        # Convert date to string for JSON serialization
        for expense in recent_expenses:
            expense['date'] = expense['expense_date'].isoformat()
            
        # Calculate budget statistics
        total_budget = budgets.aggregate(total=Sum('total_amount'))['total'] or 0
        spent_budget = budgets.aggregate(spent=Sum('spent_amount'))['spent'] or 0
        remaining_budget = total_budget - spent_budget
        utilization_rate = 0
        if total_budget > 0:
            utilization_rate = (spent_budget / total_budget) * 100
            
        # Compile all statistics
        statistics = {
            'donation_stats': {
                'total_amount': donation_total,
                'donor_count': donations.values('donor').distinct().count(),
                'growth_rate': donation_growth,
                'average_amount': donations.aggregate(avg=Avg('amount'))['avg'] or 0,
            },
            'campaign_stats': {
                'active_count': active_campaigns,
                'total_raised': total_raised,
                'total_target': total_target,
                'success_rate': success_rate,
            },
            'expense_stats': {
                'total_amount': expense_total,
                'pending_amount': pending_amount,
                'growth_rate': expense_growth,
                'approval_rate': approval_rate,
            },
            'budget_stats': {
                'total_budget': total_budget,
                'total_spent': spent_budget,
                'total_remaining': remaining_budget,
                'utilization_rate': utilization_rate,
            },
            'recent_donations': list(recent_donations),
            'recent_expenses': list(recent_expenses),
            'date_range': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'period_days': period_length,
            }
        }
        
        return Response(statistics)
