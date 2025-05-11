from django.db import models
from django.contrib.auth import get_user_model
from mainapps.project.models import Project, ProjectMilestone
from mptt.models import MPTTModel, TreeForeignKey
from django.utils import timezone

User = get_user_model()

class TaskStatus(models.TextChoices):
    TODO = 'todo', 'To Do'
    IN_PROGRESS = 'in_progress', 'In Progress'
    REVIEW = 'review', 'Under Review'
    COMPLETED = 'completed', 'Completed'
    BLOCKED = 'blocked', 'Blocked'

class TaskPriority(models.TextChoices):
    LOW = 'low', 'Low'
    MEDIUM = 'medium', 'Medium'
    HIGH = 'high', 'High'
    URGENT = 'urgent', 'Urgent'

class Task(MPTTModel):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='tasks'
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

    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    completion_date = models.DateField(null=True, blank=True)

    estimated_hours = models.PositiveIntegerField(null=True, blank=True)
    actual_hours = models.PositiveIntegerField(null=True, blank=True)

    dependencies = models.ManyToManyField(
        'self',
        symmetrical=False,
        blank=True,
        related_name='dependents'
    )

    notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class MPTTMeta:
        order_insertion_by = ['created_at']

    def __str__(self):
        return f"{self.title} ({self.project.title})"

    # ---------------------------
    # ✅ Helper Properties
    # ---------------------------

    @property
    def is_completed(self):
        return self.status == TaskStatus.COMPLETED

    @property
    def is_overdue(self):
        return self.due_date and not self.is_completed and self.due_date < timezone.now().date()

    @property
    def has_subtasks(self):
        return self.subtasks.exists()

    @property
    def completion_percentage(self):
        if not self.has_subtasks:
            return 100 if self.is_completed else 0
        total = self.subtasks.count()
        completed = self.subtasks.filter(status=TaskStatus.COMPLETED).count()
        return int((completed / total) * 100) if total else 0

    @property
    def blocked_by(self):
        """Tasks that are not completed and this task depends on"""
        return self.dependencies.exclude(status=TaskStatus.COMPLETED)

    @property
    def is_unblocked(self):
        """Check if all dependencies are completed"""
        return not self.blocked_by.exists()

    def mark_completed(self):
        self.status = TaskStatus.COMPLETED
        self.completion_date = timezone.now().date()
        self.save(update_fields=['status', 'completion_date'])

    def assign_user(self, user):
        self.assigned_to.add(user)
        self.save()

    def unassign_user(self, user):
        self.assigned_to.remove(user)
        self.save()