import json
import hashlib
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
 
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Sum, Avg, Max, Min
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
import csv
from django.http import HttpResponse
from django.core.cache import cache

from .models import (
    DonationCampaign, Donation, RecurringDonation, InKindDonation, 
    Grant, GrantReport, ExchangeRate
)
from .api.serializers import (
    DonationCampaignListSerializer, DonationCampaignDetailSerializer,
    DonationListSerializer, DonationDetailSerializer,
    RecurringDonationListSerializer, RecurringDonationDetailSerializer,
    InKindDonationListSerializer, InKindDonationDetailSerializer,
    GrantListSerializer, GrantDetailSerializer,
    GrantReportListSerializer, GrantReportDetailSerializer,
    CurrencyConversionSerializer, DonationStatsSerializer
)
from .filters import (
    DonationCampaignFilter, DonationFilter, RecurringDonationFilter,
    InKindDonationFilter, GrantFilter
)
from .permissions import DonationPermissions

# ============================================================================
# DONATION CAMPAIGN VIEWSET
# ============================================================================

class DonationCampaignViewSet(viewsets.ModelViewSet):
    """
    Comprehensive ViewSet for Donation Campaigns with enhanced analytics
    """
    queryset = DonationCampaign.objects.select_related(
        'target_currency', 'project', 'created_by'
    ).prefetch_related('managed_by')
    
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = DonationCampaignFilter
    search_fields = ['title', 'description', 'campaign_type']
    ordering_fields = [
        'created_at', 'start_date', 'end_date', 'target_amount', 
        'progress_percentage', 'current_amount'
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

    @action(detail=True, methods=['get'])
    def donation_trends(self, request, pk=None):
        """Get donation trends over time"""
        campaign = self.get_object()
        period = request.query_params.get('period', '30')  # days
        
        try:
            days = int(period)
        except ValueError:
            days = 30
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Daily donation totals
        daily_donations = campaign.donations.filter(
            status='completed',
            donation_date__date__gte=start_date,
            donation_date__date__lte=end_date
        ).extra(
            select={'day': 'DATE(donation_date)'}
        ).values('day').annotate(
            count=Count('id'),
            total=Sum('amount'),
            avg=Avg('amount')
        ).order_by('day')
        
        # Weekly aggregations
        weekly_donations = []
        current_week_start = start_date
        while current_week_start <= end_date:
            week_end = min(current_week_start + timedelta(days=6), end_date)
            week_data = campaign.donations.filter(
                status='completed',
                donation_date__date__gte=current_week_start,
                donation_date__date__lte=week_end
            ).aggregate(
                count=Count('id'),
                total=Sum('amount'),
                avg=Avg('amount')
            )
            week_data['week_start'] = current_week_start
            week_data['week_end'] = week_end
            weekly_donations.append(week_data)
            current_week_start = week_end + timedelta(days=1)
        
        return Response({
            'daily_trends': list(daily_donations),
            'weekly_trends': weekly_donations,
            'period_summary': {
                'start_date': start_date,
                'end_date': end_date,
                'total_days': days,
            }
        })

    @action(detail=True, methods=['get'])
    def donor_analysis(self, request, pk=None):
        """Analyze donor patterns and segments"""
        campaign = self.get_object()
        
        # Donor segments by amount
        donations = campaign.donations.filter(status='completed')
        
        segments = {
            'micro': donations.filter(amount__lt=50),
            'small': donations.filter(amount__gte=50, amount__lt=250),
            'medium': donations.filter(amount__gte=250, amount__lt=1000),
            'large': donations.filter(amount__gte=1000, amount__lt=5000),
            'major': donations.filter(amount__gte=5000),
        }
        
        segment_analysis = {}
        for segment_name, segment_qs in segments.items():
            segment_analysis[segment_name] = {
                'count': segment_qs.count(),
                'total': segment_qs.aggregate(Sum('amount'))['amount__sum'] or 0,
                'avg': segment_qs.aggregate(Avg('amount'))['amount__avg'] or 0,
                'unique_donors': segment_qs.values('donor').distinct().count(),
            }
        
        # Repeat donors
        repeat_donors = donations.values('donor').annotate(
            donation_count=Count('id'),
            total_donated=Sum('amount')
        ).filter(donation_count__gt=1).order_by('-total_donated')
        
        # New vs returning donors
        first_time_donors = donations.filter(
            donor__donations__campaign=campaign
        ).values('donor').annotate(
            first_donation=Min('donation_date')
        ).filter(first_donation__gte=campaign.start_date)
        
        return Response({
            'segments': segment_analysis,
            'repeat_donors': list(repeat_donors[:20]),  # Top 20
            'donor_retention': {
                'total_donors': campaign.total_donors_count,
                'repeat_donors_count': repeat_donors.count(),
                'first_time_donors_count': first_time_donors.count(),
                'retention_rate': (repeat_donors.count() / max(campaign.total_donors_count, 1)) * 100
            }
        })

    @action(detail=True, methods=['get'])
    def payment_analysis(self, request, pk=None):
        """Analyze payment methods and processing"""
        campaign = self.get_object()
        
        # Payment method breakdown
        payment_methods = campaign.donations.filter(status='completed').values(
            'payment_method'
        ).annotate(
            count=Count('id'),
            total=Sum('amount'),
            avg=Avg('amount'),
            total_fees=Sum('processor_fee')
        ).order_by('-total')
        
        # Processing efficiency
        processing_stats = campaign.donations.aggregate(
            total_gross=Sum('amount'),
            total_fees=Sum('processor_fee'),
            total_net=Sum('amount') - Sum('processor_fee'),
            avg_fee_percentage=Avg('processor_fee') / Avg('amount') * 100
        )
        
        # Status breakdown
        status_breakdown = campaign.donations.values('status').annotate(
            count=Count('id'),
            total=Sum('amount')
        ).order_by('-count')
        
        return Response({
            'payment_methods': list(payment_methods),
            'processing_efficiency': processing_stats,
            'status_breakdown': list(status_breakdown),
            'fee_analysis': {
                'total_fees': processing_stats['total_fees'] or 0,
                'fee_percentage': processing_stats['avg_fee_percentage'] or 0,
                'net_efficiency': ((processing_stats['total_net'] or 0) / max(processing_stats['total_gross'] or 1, 1)) * 100
            }
        })

    @action(detail=False, methods=['get'])
    def dashboard_stats(self, request):
        """Get dashboard statistics for all campaigns"""
        # Active campaigns
        active_campaigns = self.get_queryset().filter(
            status='active',
            start_date__lte=timezone.now().date(),
            end_date__gte=timezone.now().date()
        )
        
        # Campaign health distribution
        health_distribution = {}
        for campaign in active_campaigns:
            health = campaign.fundraising_health
            health_distribution[health] = health_distribution.get(health, 0) + 1
        
        # Top performing campaigns
        top_campaigns = active_campaigns.order_by('-progress_percentage')[:5]
        
        # Recent campaigns
        recent_campaigns = self.get_queryset().order_by('-created_at')[:5]
        
        return Response({
            'summary': {
                'total_campaigns': self.get_queryset().count(),
                'active_campaigns': active_campaigns.count(),
                'completed_campaigns': self.get_queryset().filter(status='completed').count(),
            },
            'health_distribution': health_distribution,
            'top_performing': DonationCampaignListSerializer(top_campaigns, many=True).data,
            'recent_campaigns': DonationCampaignListSerializer(recent_campaigns, many=True).data,
        })

    @action(detail=True, methods=['post'])
    def update_monetary_fields(self, request, pk=None):
        """Trigger recalculation of monetary fields"""
        campaign = self.get_object()
        campaign.update_monetary_fields()
        
        # Clear related caches
        cache_pattern = f"campaign_analytics_{pk}_*"
        # Implementation would depend on your cache backend
        
        return Response({'message': 'Monetary fields updated successfully'})

    @action(detail=True, methods=['get'])
    def export_data(self, request, pk=None):
        """Export campaign data to CSV"""
        campaign = self.get_object()
        format_type = request.query_params.get('format', 'csv')
        
        if format_type == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="campaign_{pk}_data.csv"'
            
            writer = csv.writer(response)
            
            # Campaign summary
            writer.writerow(['Campaign Summary'])
            writer.writerow(['Title', campaign.title])
            writer.writerow(['Target Amount', campaign.formatted_target_amount])
            writer.writerow(['Current Amount', campaign.formatted_current_amount])
            writer.writerow(['Progress', f"{campaign.progress_percentage:.2f}%"])
            writer.writerow(['Status', campaign.campaign_status])
            writer.writerow([])
            
            # Donations
            writer.writerow(['Donations'])
            writer.writerow([
                'Date', 'Donor', 'Amount', 'Currency', 'Payment Method', 'Status'
            ])
            
            for donation in campaign.donations.all():
                writer.writerow([
                    donation.donation_date,
                    donation.donor_name_display,
                    donation.amount,
                    donation.currency.code,
                    donation.payment_method,
                    donation.status
                ])
            
            return response
        
        return Response({'error': 'Unsupported format'}, status=400)

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
    permission_classes = [DonationPermissions]

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
    filterset_class = RecurringDonationFilter
    search_fields = ['donor__username', 'donor__email', 'subscription_id']
    ordering_fields = [
        'created_at', 'start_date', 'next_payment_date', 'amount',
        'total_donated', 'payment_count'
    ]
    ordering = ['-created_at']
    permission_classes = [DonationPermissions]

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
    filterset_class = InKindDonationFilter
    search_fields = ['item_description', 'donor_name', 'donor_email', 'brand_model']
    ordering_fields = [
        'donation_date', 'estimated_value', 'status', 'created_at',
        'received_date', 'effective_value'
    ]
    ordering = ['-donation_date']
    permission_classes = [DonationPermissions]

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
@csrf_exempt
def flutterwave_webhook(request):
    if request.method == 'POST':
        try:
            signature = request.headers.get('X-FLW-SIGNATURE')
            body = request.body.decode('utf-8')
            secret_hash = settings.FLUTTERWAVE_SECRET_HASH  
            
            generated_signature = hashlib.sha256((body + secret_hash).encode('utf-8')).hexdigest()
            
            if generated_signature != signature:
                return HttpResponse('Invalid signature', status=400)
            
            data = json.loads(body)
            event_type = data.get('event')
            
            # Process the webhook data based on the event_type
            if event_type == 'charge.success':
                # Handle successful payment
                print("Payment successful:", data)
            elif event_type == 'charge.failed':
                # Handle failed payment
                print("Payment failed:", data)
            
            return HttpResponse('Webhook received', status=200)
        except Exception as e:
            print(f"Error processing webhook: {e}")
            return HttpResponse('Error processing webhook', status=500)
    else:
        return HttpResponse('Method not allowed', status=405)