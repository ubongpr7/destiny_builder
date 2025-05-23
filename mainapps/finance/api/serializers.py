from rest_framework import serializers
from django.contrib.auth import get_user_model
from ..models import (
    DonationCampaign, Donation, RecurringDonation, InKindDonation,
    Grant, GrantReport, Budget, BudgetItem, Expense, OrganizationalExpense
)
from mainapps.project.models import Project
from django.db import models


User = get_user_model()

class DonationCampaignSerializer(serializers.ModelSerializer):
    progress_percentage = serializers.ReadOnlyField()
    is_completed = serializers.ReadOnlyField()
    project_name = serializers.CharField(source='project.title', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    donations_count = serializers.SerializerMethodField()
    total_raised = serializers.SerializerMethodField()
    
    class Meta:
        model = DonationCampaign
        fields = '__all__'
        read_only_fields = ('current_amount', 'created_at', 'updated_at')
    
    def get_donations_count(self, obj):
        return obj.donations.filter(status='completed').count()
    
    def get_total_raised(self, obj):
        return obj.donations.filter(status='completed').aggregate(
            total=models.Sum('amount')
        )['total'] or 0

class DonationSerializer(serializers.ModelSerializer):
    donor_name_display = serializers.SerializerMethodField()
    campaign_title = serializers.CharField(source='campaign.title', read_only=True)
    project_title = serializers.CharField(source='project.title', read_only=True)
    processed_by_name = serializers.CharField(source='processed_by.get_full_name', read_only=True)
    
    class Meta:
        model = Donation
        fields = '__all__'
        read_only_fields = ('receipt_number', 'created_at', 'updated_at')
    
    def get_donor_name_display(self, obj):
        if obj.is_anonymous:
            return "Anonymous"
        if obj.donor:
            return obj.donor.get_full_name() or obj.donor.username
        return obj.donor_name or "Unknown"

class RecurringDonationSerializer(serializers.ModelSerializer):
    donor_name = serializers.CharField(source='donor.get_full_name', read_only=True)
    campaign_title = serializers.CharField(source='campaign.title', read_only=True)
    project_title = serializers.CharField(source='project.title', read_only=True)
    
    class Meta:
        model = RecurringDonation
        fields = '__all__'
        read_only_fields = ('total_donated', 'payment_count', 'created_at', 'updated_at')

class InKindDonationSerializer(serializers.ModelSerializer):
    donor_name_display = serializers.SerializerMethodField()
    campaign_title = serializers.CharField(source='campaign.title', read_only=True)
    project_title = serializers.CharField(source='project.title', read_only=True)
    received_by_name = serializers.CharField(source='received_by.get_full_name', read_only=True)
    
    class Meta:
        model = InKindDonation
        fields = '__all__'
        read_only_fields = ('receipt_number', 'created_at', 'updated_at')
    
    def get_donor_name_display(self, obj):
        if obj.is_anonymous:
            return "Anonymous"
        if obj.donor:
            return obj.donor.get_full_name() or obj.donor.username
        return obj.donor_name or "Unknown"

class GrantSerializer(serializers.ModelSerializer):
    project_title = serializers.CharField(source='project.title', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    managed_by_name = serializers.CharField(source='managed_by.get_full_name', read_only=True)
    reports_count = serializers.SerializerMethodField()
    remaining_amount = serializers.SerializerMethodField()
    
    class Meta:
        model = Grant
        fields = '__all__'
        read_only_fields = ('amount_received', 'created_at', 'updated_at')
    
    def get_reports_count(self, obj):
        return obj.reports.count()
    
    def get_remaining_amount(self, obj):
        return obj.amount - obj.amount_received

class GrantReportSerializer(serializers.ModelSerializer):
    grant_title = serializers.CharField(source='grant.title', read_only=True)
    submitted_by_name = serializers.CharField(source='submitted_by.get_full_name', read_only=True)
    grantor = serializers.CharField(source='grant.grantor', read_only=True)
    
    class Meta:
        model = GrantReport
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')

class BudgetItemSerializer(serializers.ModelSerializer):
    remaining_amount = serializers.ReadOnlyField()
    spent_percentage = serializers.ReadOnlyField()
    
    class Meta:
        model = BudgetItem
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')

class BudgetSerializer(serializers.ModelSerializer):
    items = BudgetItemSerializer(many=True, read_only=True)
    remaining_amount = serializers.ReadOnlyField()
    spent_percentage = serializers.ReadOnlyField()
    project_title = serializers.CharField(source='project.title', read_only=True)
    campaign_title = serializers.CharField(source='campaign.title', read_only=True)
    grant_title = serializers.CharField(source='grant.title', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    items_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Budget
        fields = '__all__'
        read_only_fields = ('spent_amount', 'approved_at', 'created_at', 'updated_at')
    
    def get_items_count(self, obj):
        return obj.items.count()

class OrganizationalExpenseSerializer(serializers.ModelSerializer):
    budget_item_description = serializers.CharField(source='budget_item.description', read_only=True)
    submitted_by_name = serializers.CharField(source='submitted_by.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    
    class Meta:
        model = OrganizationalExpense
        fields = '__all__'
        read_only_fields = ('approved_at', 'created_at', 'updated_at')

class ProjectExpenseBudgetLinkSerializer(serializers.Serializer):
    project_expense_id = serializers.IntegerField()
    budget_item_id = serializers.IntegerField()

# Summary serializers for dashboard
class FinanceSummarySerializer(serializers.Serializer):
    total_donations = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_grants = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_expenses = serializers.DecimalField(max_digits=12, decimal_places=2)
    active_campaigns = serializers.IntegerField()
    pending_expenses = serializers.IntegerField()
    monthly_donations = serializers.DecimalField(max_digits=12, decimal_places=2)
    monthly_expenses = serializers.DecimalField(max_digits=12, decimal_places=2)

class DonationStatsSerializer(serializers.Serializer):
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_count = serializers.IntegerField()
    average_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    top_donors = serializers.ListField()
    monthly_trend = serializers.ListField()
