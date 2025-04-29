from django.db import models
from django.contrib.auth import get_user_model
from mainapps.project.models import Project
from django.utils.translation import gettext_lazy as _

User = get_user_model()

class Report(models.Model):
    """General reports generated in the system"""
    REPORT_TYPE_CHOICES = [
        ('project', 'Project Report'),
        ('financial', 'Financial Report'),
        ('inventory', 'Inventory Report'),
        ('membership', 'Membership Report'),
        ('activity', 'Activity Report'),
        ('impact', 'Impact Report'),
        ('custom', 'Custom Report'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ]
    
    title = models.CharField(max_length=200)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES)
    description = models.TextField(blank=True, null=True)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_reports')
    reporting_period_start = models.DateField(blank=True, null=True)
    reporting_period_end = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    content = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to='reports/', blank=True, null=True)
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.title} - {self.report_type}"

class ReportSection(models.Model):
    """Sections within a report"""
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name='sections')
    title = models.CharField(max_length=200)
    content = models.TextField()
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return f"{self.report.title} - {self.title}"

class ReportAttachment(models.Model):
    """Attachments for reports"""
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name='attachments')
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to='report_attachments/')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='report_attachments')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.report.title} - {self.title}"

class ImpactMetric(models.Model):
    """Metrics for measuring project impact"""
    name = models.CharField(max_length=100)
    description = models.TextField()
    unit_of_measurement = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name

class ProjectImpact(models.Model):
    """Impact measurements for projects"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='impact_metrics')
    metric = models.ForeignKey(ImpactMetric, on_delete=models.CASCADE, related_name='project_impacts')
    value = models.DecimalField(max_digits=10, decimal_places=2)
    measurement_date = models.DateField()
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recorded_impacts')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.project.title} - {self.metric.name}: {self.value}"

class DailyReport(models.Model):
    """Daily project reports with detailed information"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='daily_reports')
    date = models.DateField()
    submitted_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='submitted_daily_reports')
    weather_conditions = models.CharField(max_length=100, blank=True, null=True)
    work_completed = models.TextField()
    materials_used = models.TextField(blank=True, null=True)
    equipment_used = models.TextField(blank=True, null=True)
    labor_hours = models.PositiveIntegerField(default=0)
    safety_incidents = models.TextField(blank=True, null=True)
    quality_issues = models.TextField(blank=True, null=True)
    delays = models.TextField(blank=True, null=True)
    next_day_plan = models.TextField(blank=True, null=True)
    additional_notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('project', 'date')
    
    def __str__(self):
        return f"{self.project.title} - Daily Report {self.date}"

class DailyReportMedia(models.Model):
    """Media files attached to daily reports"""
    MEDIA_TYPE_CHOICES = [
        ('image', 'Image'),
        ('video', 'Video'),
        ('document', 'Document'),
        ('audio', 'Audio'),
    ]
    
    report = models.ForeignKey(DailyReport, on_delete=models.CASCADE, related_name='media_files')
    media_type = models.CharField(max_length=20, choices=MEDIA_TYPE_CHOICES)
    file = models.FileField(upload_to='daily_reports/')
    caption = models.CharField(max_length=255, blank=True, null=True)
    location_data = models.CharField(max_length=255, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.report.project.title} - {self.report.date} - {self.media_type}"

class DailyExpenseReport(models.Model):
    """Daily expense tracking for projects"""
    daily_report = models.OneToOneField(DailyReport, on_delete=models.CASCADE, related_name='expense_report')
    total_expenses = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    budget_variance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.daily_report.project.title} - Expenses for {self.daily_report.date}"

class ExpenseItem(models.Model):
    """Individual expense items in daily expense reports"""
    expense_report = models.ForeignKey(DailyExpenseReport, on_delete=models.CASCADE, related_name='expense_items')
    category = models.CharField(max_length=100)
    description = models.TextField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    receipt = models.FileField(upload_to='expense_receipts/', blank=True, null=True)
    
    def __str__(self):
        return f"{self.expense_report.daily_report.project.title} - {self.category} (${self.amount})"