from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import (
    DonationCampaign, Donation, RecurringDonation, InKindDonation,
    Grant, GrantReport, Budget, BudgetItem, OrganizationalExpense
)

@admin.register(RecurringDonation)
class RecurringDonationAdmin(admin.ModelAdmin):
    list_display = [
        'donor', 'amount', 'frequency', 'status', 'next_payment_date',
        'payment_count', 'total_donated', 'created_at', 'actions'
    ]
    list_filter = ['status', 'frequency', 'created_at', 'next_payment_date']
    search_fields = ['donor__username', 'donor__email', 'donor__first_name', 'donor__last_name']
    readonly_fields = ['total_donated', 'payment_count', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Donor Information', {
            'fields': ('donor', 'is_anonymous')
        }),
        ('Donation Details', {
            'fields': ('amount', 'frequency', 'campaign', 'project')
        }),
        ('Payment Information', {
            'fields': ('payment_method', 'subscription_id', 'status')
        }),
        ('Schedule', {
            'fields': ('start_date', 'end_date', 'next_payment_date')
        }),
        ('Statistics', {
            'fields': ('total_donated', 'payment_count'),
            'classes': ('collapse',)
        }),
        ('Additional Information', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def actions(self, obj):
        """Custom actions for each recurring donation"""
        actions = []
        
        if obj.status == 'active':
            pause_url = reverse('admin:finance_recurringdonation_pause', args=[obj.pk])
            actions.append(f'<a href="{pause_url}" class="button">Pause</a>')
        elif obj.status == 'paused':
            resume_url = reverse('admin:finance_recurringdonation_resume', args=[obj.pk])
            actions.append(f'<a href="{resume_url}" class="button">Resume</a>')
        
        cancel_url = reverse('admin:finance_recurringdonation_cancel', args=[obj.pk])
        actions.append(f'<a href="{cancel_url}" class="button">Cancel</a>')
        
        history_url = reverse('admin:finance_donation_changelist') + f'?donor__id__exact={obj.donor.id}&donation_type__exact=recurring'
        actions.append(f'<a href="{history_url}" class="button">View History</a>')
        
        return format_html(' '.join(actions))
    
    actions.short_description = 'Actions'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('donor', 'campaign', 'project')

@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    list_display = [
        'donor_display', 'amount', 'donation_type', 'status', 
        'donation_date', 'campaign', 'payment_method'
    ]
    list_filter = ['status', 'donation_type', 'donation_date', 'campaign']
    search_fields = ['donor__username', 'donor_name', 'transaction_id', 'reference_number']
    readonly_fields = ['created_at', 'updated_at']
    
    def donor_display(self, obj):
        if obj.is_anonymous:
            return "Anonymous"
        return obj.donor.get_full_name() if obj.donor else obj.donor_name
    donor_display.short_description = 'Donor'

@admin.register(DonationCampaign)
class DonationCampaignAdmin(admin.ModelAdmin):
    list_display = ['title', 'target_amount', 'current_amount', 'progress_percentage', 'is_active', 'start_date', 'end_date']
    list_filter = ['is_active', 'is_featured', 'start_date', 'end_date']
    search_fields = ['title', 'description']
    readonly_fields = ['current_amount', 'progress_percentage', 'created_at', 'updated_at']

# Register other models
admin.site.register(InKindDonation)
admin.site.register(Grant)
admin.site.register(GrantReport)
admin.site.register(Budget)
admin.site.register(BudgetItem)
admin.site.register(OrganizationalExpense)
