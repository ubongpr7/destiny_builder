from django.db import models
from django.utils.translation import gettext_lazy as _
from mainapps.inventory.models import Asset
from mptt.models import MPTTModel, TreeForeignKey
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
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
    actual_end_date = models.DateField(blank=True, null=True)
    budget = models.DecimalField(max_digits=12, decimal_places=2)
    funds_allocated = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    funds_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0)
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

class ProjectUpdateMedia(models.Model):
    """Media files attached to daily project updates"""
    MEDIA_TYPE_CHOICES = [
        ('image', 'Image'),
        ('video', 'Video'),
        ('document', 'Document'),
        ('audio', 'Audio'),
    ]
    
    update = models.ForeignKey(DailyProjectUpdate, on_delete=models.CASCADE, related_name='media_files')
    media_type = models.CharField(max_length=20, choices=MEDIA_TYPE_CHOICES)
    file = models.FileField(upload_to='project_updates/')
    caption = models.CharField(max_length=255, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.update.project.title} - {self.update.date} - {self.media_type}"

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