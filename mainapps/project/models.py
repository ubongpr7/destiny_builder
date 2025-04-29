from django.db import models
from django.utils.translation import gettext_lazy as _
from mainapps.inventory.models import Asset
from mptt.models import MPTTModel, TreeForeignKey
from django.contrib.auth import get_user_model
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
    manager = models.ForeignKey(User, on_delete=models.CASCADE, related_name='managed_projects')
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
    """Milestones for projects"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('delayed', 'Delayed'),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='milestones')
    title = models.CharField(max_length=200)
    description = models.TextField()
    due_date = models.DateField()
    completion_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
       
    def __str__(self):
        return f"{self.project.title} - {self.title}"

class ProjectTask(models.Model):
    """Tasks within project milestones"""
    STATUS_CHOICES = [
        ('todo', 'To Do'),
        ('in_progress', 'In Progress'),
        ('review', 'Under Review'),
        ('completed', 'Completed'),
        ('blocked', 'Blocked'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
    milestone = models.ForeignKey(ProjectMilestone, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks')
    title = models.CharField(max_length=200)
    description = models.TextField()
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tasks')
    start_date = models.DateField()
    due_date = models.DateField()
    completion_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='todo')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    estimated_hours = models.PositiveIntegerField(blank=True, null=True)
    actual_hours = models.PositiveIntegerField(blank=True, null=True)
    dependencies = models.ManyToManyField('self', symmetrical=False, blank=True, related_name='dependent_tasks')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.project.title} - {self.title}"

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