from datetime import datetime
from django.db import models
from django.utils.translation import gettext_lazy as _
from mainapps.inventory.models import Asset
from mptt.models import MPTTModel, TreeForeignKey
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.db.models import Sum
from decimal import Decimal
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

User=get_user_model()



class ProjectCategory(MPTTModel):
    """Categories for projects"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='subcategories')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Project Categories"
    
    def __str__(self):
        return self.name

class Project(models.Model):
    """Projects undertaken by the organization"""
    PROJECT_TYPE_CHOICES = [
        ('profit', 'Profit'),
        ('non_profit', 'Non-Profit'),
        ('community', 'Community'),
        ('internal', 'Internal'),
    ]
    
    STATUS_CHOICES = [
        ('planning', 'Planning'),
        ('submitted', 'Submitted'),
        ('approved', 'Planning'),
        ('active', 'Active'),
        ('on_hold', 'On Hold'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    project_type = models.CharField(max_length=20, choices=PROJECT_TYPE_CHOICES)
    category = models.ForeignKey(ProjectCategory, on_delete=models.SET_NULL, null=True, related_name='projects')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_projects')
    manager = models.ForeignKey(User, on_delete=models.SET_NULL,null=True, related_name='managed_projects')
    officials = models.ManyToManyField(User, help_text='Destiny builders officials responsible for the project', related_name='monitored_projects')
    start_date = models.DateField()
    target_end_date = models.DateField()
    full_budget_disbursed = models.BooleanField(default=False)
    actual_end_date = models.DateField(blank=True, null=True)
    budget = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planning')
    location = models.CharField(max_length=200, blank=True, null=True)
    beneficiaries = models.TextField(blank=True, null=True)
    success_criteria = models.TextField(blank=True, null=True)
    risks = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.title
    @property
    def funds_allocated(self):
        """
        Calculate funds allocated on demand:
        - If full_budget_disbursed is True, return the full budget
        - Otherwise, sum all reimbursed expenses
        """
        if self.full_budget_disbursed:
            return self.budget
        
        # Sum all reimbursed expenses
        reimbursed_sum = self.expenses.filter(status='reimbursed').aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        return reimbursed_sum
    
    @property
    def funds_spent(self):
        """
        Calculate funds spent on demand:
        - Sum of all reimbursed expenses
        """
        # Sum all reimbursed expenses
        reimbursed_sum = self.expenses.filter(status='reimbursed').aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        return reimbursed_sum

class ProjectTeamMember(models.Model):
    """Team members assigned to projects"""
    ROLE_CHOICES = [
        ('manager', 'Project Manager'),
        ('coordinator', 'Coordinator'),
        ('member', 'Team Member'),
        ('advisor', 'Advisor'),
        ('volunteer', 'Volunteer'),
        ('monitoring', 'Monitoring/Reporting Officer'),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='team_members')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='project_roles')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    responsibilities = models.TextField(blank=True, null=True)
    join_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('project', 'user')
    
    def __str__(self):
        return f"{self.project.title} - {self.user.username} ({self.role})"

class ProjectAsset(models.Model):
    """Assets assigned to projects"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='assigned_assets')
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='project_assignments')
    assigned_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='asset_assignments')
    assigned_date = models.DateField()
    return_date = models.DateField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('project', 'asset')
    
    def __str__(self):
        return f"{self.project.title} - {self.asset.name}"

class ProjectMilestone(models.Model):
    """Milestones for projects with enhanced tracking capabilities"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('delayed', 'Delayed'),
        ('cancelled', 'Cancelled'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    project = models.ForeignKey('Project', on_delete=models.CASCADE, related_name='milestones')
    title = models.CharField(max_length=200)
    description = models.TextField()
    due_date = models.DateField()
    completion_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    completion_percentage = models.IntegerField(default=0, validators=[
        MinValueValidator(0),
        MaxValueValidator(100)
    ])
    assigned_to = models.ManyToManyField(User, related_name='assigned_milestones', blank=True)
    dependencies = models.ManyToManyField('self', symmetrical=False, related_name='dependent_milestones', blank=True)
    deliverables = models.TextField(blank=True, null=True, help_text="Expected deliverables for this milestone")
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_milestones')
       
    class Meta:
        ordering = ['due_date', 'priority']
    
    def __str__(self):
        return f"{self.project.title} - {self.title}"
    
    def days_remaining(self):
        """Calculate days remaining until due date"""
        if self.status == 'completed':
            return 0
        
        today = timezone.now().date()
        if self.due_date < today:
            return 0
        return (self.due_date - today).days
    
    def is_overdue(self):
        """Check if milestone is overdue"""
        if self.status == 'completed' and self.completion_date:
            return self.completion_date > self.due_date
        
        if self.status != 'completed':
            return timezone.now().date() > self.due_date
        
        return False
    
    def complete_milestone(self, completion_date=None):
        """Mark milestone as completed"""
        self.status = 'completed'
        self.completion_percentage = 100
        self.completion_date = completion_date or timezone.now().date()
        self.save()
        
        # Check if all project milestones are completed
        if all(m.status == 'completed' for m in self.project.milestones.all()):
            # Maybe trigger some project completion logic
            pass

class DailyProjectUpdate(models.Model):
    """Daily updates for project progress monitoring"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='daily_updates')
    date = models.DateField()
    submitted_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='submitted_updates')
    summary = models.TextField()
    challenges = models.TextField(blank=True, null=True)
    achievements = models.TextField(blank=True, null=True)
    next_steps = models.TextField(blank=True, null=True)
    funds_spent_today = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('project', 'date')
    
    def __str__(self):
        return f"{self.project.title} - {self.date}"




class BaseMedia(models.Model):
    """Abstract base model for all media files"""
    MEDIA_TYPE_CHOICES = [
        ('image', 'Image'),
        ('video', 'Video'),
        ('document', 'Document'),
        ('audio', 'Audio'),
        ('blueprint', 'Blueprint'),
        ('contract', 'Contract'),
        ('diagram', 'Diagram'),
        ('report', 'Report'),
    ]
    
    media_type = models.CharField(max_length=20, choices=MEDIA_TYPE_CHOICES)
    file = models.FileField(upload_to='media/', null=True, blank=True)
    title = models.CharField(max_length=255,null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    caption = models.CharField(max_length=255, blank=True, null=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='%(class)s_uploads')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True
        ordering = ['-uploaded_at']
    def get_upload_path(instance, filename):
        """Dynamic path based on the model class and related object"""
        model_name = instance.__class__.__name__.lower()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f'{model_name}/{timestamp}/{filename}'

class ProjectMedia(BaseMedia):
    """Media files attached directly to projects"""
    project = models.ForeignKey('Project', on_delete=models.CASCADE, related_name='media_files')
    is_featured = models.BooleanField(default=False, help_text="Featured media appears prominently in project views")
    
    class Meta:
        verbose_name_plural = "Project Media"
        ordering = ['-is_featured', '-uploaded_at']
    
    def __str__(self):
        return f"{self.project.title} - {self.title}"
    
    
class MilestoneMedia(BaseMedia):
    """Media files attached to project milestones"""
    milestone = models.ForeignKey('ProjectMilestone', on_delete=models.CASCADE, related_name='media_files')
    represents_deliverable = models.BooleanField(default=False, help_text="This media represents a milestone deliverable")
    
    class Meta:
        verbose_name_plural = "Milestone Media"
        ordering = ['-represents_deliverable', '-uploaded_at']
    
    def __str__(self):
        return f"{self.milestone.title} - {self.title}"
    
    
class ProjectUpdateMedia(BaseMedia):
    """Media files attached to daily project updates"""
    update = models.ForeignKey('DailyProjectUpdate', on_delete=models.CASCADE, related_name='media_files')
    
    class Meta:
        verbose_name_plural = "Project Update Media"
    
    def __str__(self):
        return f"{self.update.project.title} - {self.update.date} - {self.title}"
    
class GenericMedia(models.Model):
    """Generic media that can be attached to any model"""
    MEDIA_TYPE_CHOICES = [
        ('image', 'Image'),
        ('video', 'Video'),
        ('document', 'Document'),
        ('audio', 'Audio'),
        ('blueprint', 'Blueprint'),
        ('contract', 'Contract'),
        ('diagram', 'Diagram'),
        ('report', 'Report'),
    ]
    
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    media_type = models.CharField(max_length=20, choices=MEDIA_TYPE_CHOICES)
    file = models.FileField(upload_to='generic_media/')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    caption = models.CharField(max_length=255, blank=True, null=True)
    is_featured = models.BooleanField(default=False)
    represents_deliverable = models.BooleanField(default=False)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='uploaded_media')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "Media Files"
        ordering = ['-is_featured', '-uploaded_at']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
        ]
    
    def __str__(self):
        return f"{self.content_object} - {self.title}"
    
    def get_upload_path(instance, filename):
        """Dynamic path based on the related object"""
        ct = instance.content_type
        model = ct.model_class()._meta.model_name
        return f'{model}/{instance.object_id}/{filename}'

class ProjectExpense(models.Model):
    """Expenses incurred during project execution"""
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('reimbursed', 'Reimbursed'),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='expenses')
    update = models.ForeignKey(DailyProjectUpdate, on_delete=models.SET_NULL, null=True, blank=True, related_name='expenses')
    title = models.CharField(max_length=200)
    description = models.TextField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date_incurred = models.DateField()
    incurred_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='project_expenses')
    receipt = models.FileField(upload_to='expense_receipts/', blank=True, null=True)
    category = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_expenses')
    approval_date = models.DateField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_expenses')
    
    def __str__(self):
        return f"{self.project.title} - {self.title} (${self.amount})"

class ProjectComment(MPTTModel):
    """Comments on projects and updates with threaded replies"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='comments')
    update = models.ForeignKey(DailyProjectUpdate, on_delete=models.SET_NULL, null=True, blank=True, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='project_comments')
    content = models.TextField()
    parent = TreeForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class MPTTMeta:
        order_insertion_by = ['created_at']
    def __str__(self):
        return f"Comment by {self.user.username} on {self.project.title}"