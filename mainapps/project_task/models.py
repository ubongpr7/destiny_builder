from django.db import models
from django.contrib.auth import get_user_model
from mainapps.project.models import Project, ProjectMilestone
from mptt.models import MPTTModel, TreeForeignKey
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.core.exceptions import ValidationError

User = get_user_model()

class TaskStatus(models.TextChoices):
    TODO = 'todo', 'To Do'
    IN_PROGRESS = 'in_progress', 'In Progress'
    REVIEW = 'review', 'Under Review'
    COMPLETED = 'completed', 'Completed'
    BLOCKED = 'blocked', 'Blocked'
    CANCELLED = 'cancelled', 'Cancelled'

class TaskPriority(models.TextChoices):
    LOW = 'low', 'Low'
    MEDIUM = 'medium', 'Medium'
    HIGH = 'high', 'High'
    URGENT = 'urgent', 'Urgent'

class TaskType(models.TextChoices):
    FEATURE = 'feature', 'Feature'
    BUG = 'bug', 'Bug'
    IMPROVEMENT = 'improvement', 'Improvement'
    DOCUMENTATION = 'documentation', 'Documentation'
    RESEARCH = 'research', 'Research'
    OTHER = 'other', 'Other'

class Task(MPTTModel):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Direct link to project for easier querying
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='tasks',
        null=True,  # Null if it's a subtask and inherits project from parent
    )

    milestone = models.ForeignKey(
        ProjectMilestone,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tasks'
    )

    parent = TreeForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subtasks'
    )

    assigned_to = models.ManyToManyField(
        User,
        blank=True,
        related_name='assigned_tasks'
    )

    created_by = models.ForeignKey(
        User,
        null=True,
        on_delete=models.SET_NULL,
        related_name='created_tasks'
    )

    status = models.CharField(
        max_length=20,
        choices=TaskStatus.choices,
        default=TaskStatus.TODO
    )

    priority = models.CharField(
        max_length=20,
        choices=TaskPriority.choices,
        default=TaskPriority.MEDIUM
    )
    
    task_type = models.CharField(
        max_length=20,
        choices=TaskType.choices,
        default=TaskType.FEATURE
    )

    # Changed to DateTimeField for both start and due dates
    start_date = models.DateTimeField(null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    completion_date = models.DateTimeField(null=True, blank=True)

    estimated_hours = models.PositiveIntegerField(null=True, blank=True)
    actual_hours = models.PositiveIntegerField(null=True, blank=True)
    
    # Track time spent on task
    time_spent = models.PositiveIntegerField(default=0, help_text="Time spent in minutes")
    
    # Manual completion percentage for tasks without subtasks
    completion_percentage_manual = models.PositiveIntegerField(
        default=0, 
    )

    dependencies = models.ManyToManyField(
        'self',
        symmetrical=False,
        blank=True,
        related_name='dependents'
    )

    notes = models.TextField(blank=True, null=True)
    
    # Tags for better categorization
    tags = models.CharField(max_length=255, blank=True, help_text="Comma-separated tags")
    
    # Tracking fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # For recurring tasks
    is_recurring = models.BooleanField(default=False)
    recurrence_pattern = models.CharField(max_length=50, blank=True, null=True, 
                                         help_text="Pattern like 'daily', 'weekly', 'monthly', etc.")
    recurrence_end_date = models.DateTimeField(null=True, blank=True)

    class MPTTMeta:
        order_insertion_by = ['created_at']

    def __str__(self):
        if self.project:
            return f"{self.title} ({self.project.title})"
        return self.title

    def clean(self):
        # Validate that start_date is before due_date
        if self.start_date and self.due_date and self.start_date > self.due_date:
            raise ValidationError("Start date cannot be after due date")
        
        # Validate that recurrence_end_date is after start_date
        if self.is_recurring and self.recurrence_end_date and self.start_date and self.recurrence_end_date < self.start_date:
            raise ValidationError("Recurrence end date cannot be before start date")
            
        super().clean()

    def save(self, *args, **kwargs):
        # Run validation
        self.clean()
        
        # If this is a subtask, inherit project from parent
        if self.parent and not self.project:
            self.project = self.parent.project
            
        # If milestone is set, ensure project matches milestone's project
        if self.milestone and not self.project:
            self.project = self.milestone.project
            
        # If status is changed to completed, set completion date
        if self.status == TaskStatus.COMPLETED and not self.completion_date:
            self.completion_date = timezone.now()
            
        # If status is changed from completed, clear completion date
        if self.status != TaskStatus.COMPLETED and self.completion_date:
            self.completion_date = None
            
        super().save(*args, **kwargs)

    # ---------------------------
    # ✅ Helper Properties
    # ---------------------------

    @property
    def is_completed(self):
        return self.status == TaskStatus.COMPLETED

    @property
    def is_overdue(self):
        return self.due_date and not self.is_completed and self.due_date < timezone.now()

    @property
    def has_subtasks(self):
        return self.subtasks.exists()

    @property
    def completion_percentage(self):
        if not self.has_subtasks:
            return self.completion_percentage_manual if self.status != TaskStatus.COMPLETED else 100
        
        total = self.subtasks.count()
        if not total:
            return 0
            
        completed = self.subtasks.filter(status=TaskStatus.COMPLETED).count()
        in_progress = self.subtasks.exclude(status=TaskStatus.COMPLETED).exclude(status=TaskStatus.TODO).count()
        
        # Calculate weighted percentage
        completed_weight = 100 if completed == total else (completed / total) * 100
        in_progress_weight = 0 if in_progress == 0 else (in_progress / total) * 50
        
        # Get average completion percentage of in-progress subtasks
        in_progress_tasks = self.subtasks.exclude(status=TaskStatus.COMPLETED).exclude(status=TaskStatus.TODO)
        if in_progress_tasks.exists():
            avg_progress = sum(task.completion_percentage for task in in_progress_tasks) / in_progress_tasks.count()
            in_progress_weight = (in_progress / total) * (avg_progress / 100) * 100
            
        return int(completed_weight + in_progress_weight)

    @property
    def blocked_by(self):
        """Tasks that are not completed and this task depends on"""
        return self.dependencies.exclude(status=TaskStatus.COMPLETED)

    @property
    def is_unblocked(self):
        """Check if all dependencies are completed"""
        return not self.blocked_by.exists()
        
    @property
    def time_spent_formatted(self):
        """Return time spent in hours and minutes format"""
        hours = self.time_spent // 60
        minutes = self.time_spent % 60
        return f"{hours}h {minutes}m"
        
    @property
    def days_until_due(self):
        """Return number of days until due date"""
        if not self.due_date:
            return None
        return (self.due_date.date() - timezone.now().date()).days
        
    @property
    def is_late_starting(self):
        """Check if task should have started but hasn't"""
        return (
            self.start_date and 
            self.start_date < timezone.now() and 
            self.status == TaskStatus.TODO
        )

    def mark_completed(self):
        self.status = TaskStatus.COMPLETED
        self.completion_date = timezone.now()
        self.completion_percentage_manual = 100
        self.save(update_fields=['status', 'completion_date', 'completion_percentage_manual'])
        
        # Check if parent task should be marked as completed
        if self.parent and self.parent.subtasks.exclude(status=TaskStatus.COMPLETED).count() == 0:
            self.parent.mark_completed()

    def assign_user(self, user):
        self.assigned_to.add(user)
        self.save()

    def unassign_user(self, user):
        self.assigned_to.remove(user)
        self.save()
        
    def add_time_spent(self, minutes):
        """Add time spent to the task"""
        self.time_spent += minutes
        self.save(update_fields=['time_spent'])
    def update_status(self, status, cascade=True, update_parent=True):
        """Update task status with proper handling and cascading updates"""
        old_status = self.status
        self.status = status
        
        if status == TaskStatus.COMPLETED and old_status != TaskStatus.COMPLETED:
            self.completion_date = timezone.now()
            self.completion_percentage_manual = 100
        elif status != TaskStatus.COMPLETED and old_status == TaskStatus.COMPLETED:
            self.completion_date = None
            
        self.save()
        
        if cascade and status == TaskStatus.COMPLETED:
            for subtask in self.subtasks.all():
                subtask.update_status(status, cascade=True, update_parent=False)
        
        if update_parent and self.parent:
            self._update_parent_status()
        
    def _update_parent_status(self):
        """Check if all siblings are completed and update parent accordingly"""
        parent = self.parent
        siblings = parent.subtasks.all()
        
        # If all siblings (including self) are completed, mark parent as completed
        all_completed = all(sibling.status == TaskStatus.COMPLETED for sibling in siblings)
        
        if all_completed and parent.status != TaskStatus.COMPLETED:
            parent.update_status(TaskStatus.COMPLETED, cascade=False, update_parent=True)
   
    def create_subtask(self, title, **kwargs):
        """Helper method to create a subtask"""
        return Task.objects.create(
            title=title,
            parent=self,
            project=self.project,
            milestone=self.milestone,
            created_by=kwargs.get('created_by', self.created_by),
            **kwargs
        )

class TaskComment(models.Model):
    """Model for task comments"""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"Comment by {self.user.username} on {self.task.title}"


class TaskAttachment(models.Model):
    """Model for task attachments"""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='task_attachments/')
    filename = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.filename


class TaskTimeLog(models.Model):
    """Model for tracking time spent on tasks"""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='time_logs')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    minutes = models.PositiveIntegerField()
    description = models.TextField(blank=True)
    logged_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.minutes} minutes on {self.task.title} by {self.user.username}"
        
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update the task's total time spent
        self.task.add_time_spent(self.minutes)