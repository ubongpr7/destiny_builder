from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.urls import reverse
from django.conf import settings

User = get_user_model()

class NotificationCategory(models.TextChoices):
    PROJECT = 'project', 'Project'
    MILESTONE = 'milestone', 'Milestone'
    TASK = 'task', 'Task'
    EXPENSE = 'expense', 'Expense'
    TEAM = 'team', 'Team'
    SYSTEM = 'system', 'System'
    KYC = 'kyc', 'KYC Verification'
    PAYMENT = 'payment', 'Payment'
    DOCUMENT = 'document', 'Document'
    OTHER = 'other', 'Other'

class NotificationPriority(models.TextChoices):
    LOW = 'low', 'Low'
    NORMAL = 'normal', 'Normal'
    HIGH = 'high', 'High'
    URGENT = 'urgent', 'Urgent'

class NotificationType(models.Model):
    """Defines different types of notifications that can be sent"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    category = models.CharField(
        max_length=20, 
        choices=NotificationCategory.choices,
        default=NotificationCategory.SYSTEM
    )
    title_template = models.CharField(max_length=255)
    body_template = models.TextField()
    icon = models.CharField(max_length=50, default='bell')
    color = models.CharField(max_length=20, default='primary')
    default_priority = models.CharField(
        max_length=10,
        choices=NotificationPriority.choices,
        default=NotificationPriority.NORMAL
    )
    send_email = models.BooleanField(default=False)
    send_sms = models.BooleanField(default=False)
    send_push = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    can_disable = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['category', 'name']

class Notification(models.Model):
    """Individual notification instances sent to users"""
    recipient = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='notifications'
    )
    notification_type = models.ForeignKey(
        NotificationType,
        on_delete=models.CASCADE,
        related_name='instances'
    )
    title = models.CharField(max_length=255)
    body = models.TextField()
    priority = models.CharField(
        max_length=10,
        choices=NotificationPriority.choices,
        default=NotificationPriority.NORMAL
    )
    icon = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=20, blank=True)
    action_url = models.CharField(max_length=255, blank=True)
    
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    related_object = GenericForeignKey('content_type', 'object_id')
    
    data = models.JSONField(default=dict, blank=True)
    
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    is_email_sent = models.BooleanField(default=False)
    is_sms_sent = models.BooleanField(default=False)
    is_push_sent = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.recipient.username} - {self.title}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=['is_read', 'read_at'])
    
    def mark_as_unread(self):
        """Mark notification as unread"""
        self.is_read = False
        self.read_at = None
        self.save(update_fields=['is_read', 'read_at'])
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', '-created_at']),
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['content_type', 'object_id']),
        ]

class NotificationPreference(models.Model):
    """User preferences for receiving notifications"""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )
    notification_type = models.ForeignKey(
        NotificationType,
        on_delete=models.CASCADE,
        related_name='user_preferences'
    )
    
    receive_in_app = models.BooleanField(default=True)
    receive_email = models.BooleanField(default=True)
    receive_sms = models.BooleanField(default=True)
    receive_push = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'notification_type']
        ordering = ['user', 'notification_type']
    
    def __str__(self):
        return f"{self.user.username} - {self.notification_type.name}"

class NotificationBatch(models.Model):
    """Batch of notifications for bulk processing"""
    name = models.CharField(max_length=255)
    notification_type = models.ForeignKey(
        NotificationType,
        on_delete=models.CASCADE,
        related_name='batches'
    )
    # Template data as JSON
    template_data = models.JSONField(default=dict)
    # Status of the batch
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    # Error message if failed
    error_message = models.TextField(blank=True)
    # Number of notifications created
    notifications_count = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.name} ({self.status})"
    
    class Meta:
        ordering = ['-created_at']

class ScheduledNotification(models.Model):
    """Notifications scheduled to be sent at a future time"""
    notification_type = models.ForeignKey(
        NotificationType,
        on_delete=models.CASCADE,
        related_name='scheduled'
    )
    # The user this notification is for
    recipient = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='scheduled_notifications'
    )
    template_data = models.JSONField(default=dict)
    scheduled_time = models.DateTimeField()
    is_recurring = models.BooleanField(default=False)
    recurrence_pattern = models.CharField(max_length=50, blank=True)
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('cancelled', 'Cancelled'),
        ('failed', 'Failed'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notification = models.ForeignKey(
        Notification,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='scheduled_source'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.recipient.username} - {self.notification_type.name} ({self.scheduled_time})"
    
    class Meta:
        ordering = ['scheduled_time']
        indexes = [
            models.Index(fields=['scheduled_time', 'status']),
        ]
