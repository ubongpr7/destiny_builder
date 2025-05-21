from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import (
    Notification, NotificationType, NotificationPreference,
    NotificationBatch, ScheduledNotification
)
from .services import NotificationService

User = get_user_model()

@receiver(post_save, sender=User)
def create_default_notification_preferences(sender, instance, created, **kwargs):
    """Create default notification preferences for new users"""
    if created:
        # Get all notification types
        notification_types = NotificationType.objects.filter(is_active=True)
        
        # Create default preferences
        for nt in notification_types:
            NotificationPreference.objects.create(
                user=instance,
                notification_type=nt,
                receive_in_app=True,
                receive_email=nt.send_email,
                receive_sms=nt.send_sms,
                receive_push=nt.send_push
            )

@receiver(post_save, sender=NotificationType)
def create_missing_notification_preferences(sender, instance, created, **kwargs):
    """Create notification preferences for existing users when a new notification type is created"""
    if created:
        # Get all users
        users = User.objects.all()
        
        # Create preferences for all users
        preferences = []
        for user in users:
            preferences.append(NotificationPreference(
                user=user,
                notification_type=instance,
                receive_in_app=True,
                receive_email=instance.send_email,
                receive_sms=instance.send_sms,
                receive_push=instance.send_push
            ))
        
        # Bulk create
        if preferences:
            NotificationPreference.objects.bulk_create(preferences)
