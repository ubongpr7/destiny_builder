import json
from string import Template
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.db.models import Q
from django.conf import settings
from django.urls import reverse
from django.core.mail import send_mail
from django.template.loader import render_to_string

from .models import (
    Notification, NotificationType, NotificationPreference,
    NotificationBatch, ScheduledNotification
)

User = get_user_model()

class NotificationService:
    """Service for creating and managing notifications"""
    
    @classmethod
    def create_notification(cls, 
                           recipient, 
                           notification_type_name, 
                           context_data=None, 
                           related_object=None,
                           action_url=None,
                           priority=None,
                           icon=None,
                           color=None,
                           send_email=None,
                           send_sms=None,
                           send_push=None):
        """
        Create a notification for a user
        
        Args:
            recipient: User object or user ID
            notification_type_name: String name of the notification type
            context_data: Dict of data to use in templates
            related_object: Object this notification is about
            action_url: URL to redirect to when clicked
            priority: Override default priority
            icon: Override default icon
            color: Override default color
            send_email: Override whether to send email
            send_sms: Override whether to send SMS
            send_push: Override whether to send push notification
            
        Returns:
            Notification object
        """
        # Get user if ID was passed
        if isinstance(recipient, int):
            try:
                recipient = User.objects.get(id=recipient)
            except User.DoesNotExist:
                return None
        
        # Get notification type
        try:
            notification_type = NotificationType.objects.get(name=notification_type_name)
        except NotificationType.DoesNotExist:
            return None
        
        # Check if user has disabled this notification type
        try:
            preference = NotificationPreference.objects.get(
                user=recipient,
                notification_type=notification_type
            )
            if not preference.receive_in_app:
                return None
        except NotificationPreference.DoesNotExist:
            # No preference set, use defaults
            pass
        
        # Prepare context data
        if context_data is None:
            context_data = {}
            
        # Add user data to context
        context_data['user_first_name'] = recipient.first_name
        context_data['user_last_name'] = recipient.last_name
        context_data['user_full_name'] = f"{recipient.first_name} {recipient.last_name}".strip() or recipient.username
        context_data['user_email'] = recipient.email
        
        # Add related object data if available
        if related_object:
            # Get object type name
            model_name = related_object.__class__.__name__.lower()
            context_data[f'{model_name}_id'] = related_object.id
            
            # Add common fields if they exist
            for field in ['name', 'title', 'subject', 'description']:
                if hasattr(related_object, field):
                    context_data[f'{model_name}_{field}'] = getattr(related_object, field)
        
        # Process templates
        title_template = Template(notification_type.title_template)
        body_template = Template(notification_type.body_template)
        
        try:
            title = title_template.substitute(**context_data)
            body = body_template.substitute(**context_data)
        except KeyError as e:
            # Log the error and use fallback
            print(f"Missing template variable: {e}")
            title = notification_type.title_template
            body = notification_type.body_template
        
        # Create notification
        notification = Notification(
            recipient=recipient,
            notification_type=notification_type,
            title=title,
            body=body,
            priority=priority or notification_type.default_priority,
            icon=icon or notification_type.icon,
            color=color or notification_type.color,
            action_url=action_url or '',
            data=context_data
        )
        
        # Set related object if provided
        if related_object:
            content_type = ContentType.objects.get_for_model(related_object)
            notification.content_type = content_type
            notification.object_id = related_object.id
        
        notification.save()
        
        # Handle email notification
        should_send_email = send_email if send_email is not None else notification_type.send_email
        if should_send_email and recipient.email:
            cls._send_email_notification(notification)
            
        # Handle SMS notification
        should_send_sms = send_sms if send_sms is not None else notification_type.send_sms
        if should_send_sms and hasattr(recipient, 'phone_number') and recipient.phone_number:
            cls._send_sms_notification(notification)
            
        # Handle push notification
        should_send_push = send_push if send_push is not None else notification_type.send_push
        if should_send_push:
            cls._send_push_notification(notification)
            
        return notification
    
    @classmethod
    def create_notification_for_many(cls, 
                                    recipients, 
                                    notification_type_name, 
                                    context_data=None, 
                                    related_object=None,
                                    action_url=None,
                                    priority=None,
                                    icon=None,
                                    color=None,
                                    send_email=None,
                                    send_sms=None,
                                    send_push=None):
        """Create notifications for multiple users"""
        notifications = []
        for recipient in recipients:
            notification = cls.create_notification(
                recipient=recipient,
                notification_type_name=notification_type_name,
                context_data=context_data,
                related_object=related_object,
                action_url=action_url,
                priority=priority,
                icon=icon,
                color=color,
                send_email=send_email,
                send_sms=send_sms,
                send_push=send_push
            )
            if notification:
                notifications.append(notification)
        return notifications
    
    @classmethod
    def create_batch(cls, notification_type_name, template_data, name=None):
        """Create a notification batch for processing"""
        try:
            notification_type = NotificationType.objects.get(name=notification_type_name)
        except NotificationType.DoesNotExist:
            return None
            
        batch = NotificationBatch(
            name=name or f"Batch {notification_type_name} {timezone.now().strftime('%Y-%m-%d %H:%M')}",
            notification_type=notification_type,
            template_data=template_data,
            status='pending'
        )
        batch.save()
        return batch
    
    @classmethod
    def process_batch(cls, batch_id):
        """Process a notification batch"""
        try:
            batch = NotificationBatch.objects.get(id=batch_id)
        except NotificationBatch.DoesNotExist:
            return False
            
        if batch.status != 'pending':
            return False
            
        batch.status = 'processing'
        batch.save(update_fields=['status', 'updated_at'])
        
        try:
            # Get all users who haven't disabled this notification type
            users = User.objects.filter(
                Q(notification_preferences__notification_type=batch.notification_type, 
                  notification_preferences__receive_in_app=True) |
                ~Q(notification_preferences__notification_type=batch.notification_type)
            ).distinct()
            
            count = 0
            for user in users:
                notification = cls.create_notification(
                    recipient=user,
                    notification_type_name=batch.notification_type.name,
                    context_data=batch.template_data
                )
                if notification:
                    count += 1
            
            batch.notifications_count = count
            batch.status = 'completed'
            batch.processed_at = timezone.now()
            batch.save(update_fields=['notifications_count', 'status', 'processed_at', 'updated_at'])
            return True
            
        except Exception as e:
            batch.status = 'failed'
            batch.error_message = str(e)
            batch.save(update_fields=['status', 'error_message', 'updated_at'])
            return False
    
    @classmethod
    def schedule_notification(cls, 
                             recipient, 
                             notification_type_name, 
                             scheduled_time,
                             context_data=None,
                             is_recurring=False,
                             recurrence_pattern=''):
        """Schedule a notification to be sent at a future time"""
        # Get user if ID was passed
        if isinstance(recipient, int):
            try:
                recipient = User.objects.get(id=recipient)
            except User.DoesNotExist:
                return None
        
        # Get notification type
        try:
            notification_type = NotificationType.objects.get(name=notification_type_name)
        except NotificationType.DoesNotExist:
            return None
            
        scheduled = ScheduledNotification(
            notification_type=notification_type,
            recipient=recipient,
            template_data=context_data or {},
            scheduled_time=scheduled_time,
            is_recurring=is_recurring,
            recurrence_pattern=recurrence_pattern,
            status='pending'
        )
        scheduled.save()
        return scheduled
    
    @classmethod
    def process_scheduled_notifications(cls):
        """Process all scheduled notifications that are due"""
        now = timezone.now()
        due_notifications = ScheduledNotification.objects.filter(
            scheduled_time__lte=now,
            status='pending'
        )
        
        for scheduled in due_notifications:
            try:
                # Create the notification
                notification = cls.create_notification(
                    recipient=scheduled.recipient,
                    notification_type_name=scheduled.notification_type.name,
                    context_data=scheduled.template_data
                )
                
                if notification:
                    scheduled.notification = notification
                    scheduled.status = 'sent'
                else:
                    scheduled.status = 'failed'
                    
                # Handle recurring notifications
                if scheduled.is_recurring and scheduled.recurrence_pattern:
                    # Create the next occurrence
                    next_time = cls._calculate_next_occurrence(
                        scheduled.scheduled_time, 
                        scheduled.recurrence_pattern
                    )
                    if next_time:
                        cls.schedule_notification(
                            recipient=scheduled.recipient,
                            notification_type_name=scheduled.notification_type.name,
                            scheduled_time=next_time,
                            context_data=scheduled.template_data,
                            is_recurring=True,
                            recurrence_pattern=scheduled.recurrence_pattern
                        )
                
                scheduled.save()
                
            except Exception as e:
                scheduled.status = 'failed'
                scheduled.save()
                print(f"Error processing scheduled notification {scheduled.id}: {e}")
    
    @classmethod
    def _calculate_next_occurrence(cls, current_time, pattern):
        """Calculate the next occurrence based on recurrence pattern"""
        from dateutil.relativedelta import relativedelta
        
        if pattern == 'daily':
            return current_time + timezone.timedelta(days=1)
        elif pattern == 'weekly':
            return current_time + timezone.timedelta(weeks=1)
        elif pattern == 'monthly':
            return current_time + relativedelta(months=1)
        elif pattern == 'yearly':
            return current_time + relativedelta(years=1)
        elif pattern.startswith('every_'):
            # Format: every_N_days, every_N_weeks, etc.
            parts = pattern.split('_')
            if len(parts) == 3 and parts[1].isdigit():
                n = int(parts[1])
                unit = parts[2]
                
                if unit == 'days':
                    return current_time + timezone.timedelta(days=n)
                elif unit == 'weeks':
                    return current_time + timezone.timedelta(weeks=n)
                elif unit == 'months':
                    return current_time + relativedelta(months=n)
                elif unit == 'years':
                    return current_time + relativedelta(years=n)
        
        return None
    
    @classmethod
    def _send_email_notification(cls, notification):
        """Send an email notification"""
        try:
            # Get user's email preference
            try:
                preference = NotificationPreference.objects.get(
                    user=notification.recipient,
                    notification_type=notification.notification_type
                )
                if not preference.receive_email:
                    return False
            except NotificationPreference.DoesNotExist:
                # No preference set, use defaults
                pass
                
            # Prepare email content
            context = {
                'notification': notification,
                'recipient': notification.recipient,
                'site_name': settings.SITE_NAME,
                'site_url': settings.SITE_URL,
            }
            
            # Add notification data to context
            context.update(notification.data)
            
            # Render email templates
            subject = notification.title
            html_message = render_to_string('notifications/email_notification.html', context)
            plain_message = render_to_string('notifications/email_notification_plain.txt', context)
            
            # Send email
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[notification.recipient.email],
                html_message=html_message,
                fail_silently=False
            )
            
            # Mark as sent
            notification.is_email_sent = True
            notification.save(update_fields=['is_email_sent', 'updated_at'])
            return True
            
        except Exception as e:
            print(f"Error sending email notification: {e}")
            return False
    
    @classmethod
    def _send_sms_notification(cls, notification):
        """Send an SMS notification"""
        # This is a placeholder - implement with your SMS provider
        try:
            # Get user's SMS preference
            try:
                preference = NotificationPreference.objects.get(
                    user=notification.recipient,
                    notification_type=notification.notification_type
                )
                if not preference.receive_sms:
                    return False
            except NotificationPreference.DoesNotExist:
                # No preference set, use defaults
                pass
                
            # Get user's phone number
            if not hasattr(notification.recipient, 'phone_number') or not notification.recipient.phone_number:
                return False
                
            # Implement SMS sending logic here
            # For example, using Twilio:
            # from twilio.rest import Client
            # client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            # message = client.messages.create(
            #     body=notification.body,
            #     from_=settings.TWILIO_PHONE_NUMBER,
            #     to=notification.recipient.phone_number
            # )
            
            # For now, just mark as sent
            notification.is_sms_sent = True
            notification.save(update_fields=['is_sms_sent', 'updated_at'])
            return True
            
        except Exception as e:
            print(f"Error sending SMS notification: {e}")
            return False
    
    @classmethod
    def _send_push_notification(cls, notification):
        """Send a push notification"""
        # This is a placeholder - implement with your push notification provider
        try:
            # Get user's push preference
            try:
                preference = NotificationPreference.objects.get(
                    user=notification.recipient,
                    notification_type=notification.notification_type
                )
                if not preference.receive_push:
                    return False
            except NotificationPreference.DoesNotExist:
                # No preference set, use defaults
                pass
                
            # Implement push notification logic here
            # For example, using Firebase Cloud Messaging:
            # from firebase_admin import messaging
            # message = messaging.Message(
            #     notification=messaging.Notification(
            #         title=notification.title,
            #         body=notification.body,
            #     ),
            #     token=notification.recipient.fcm_token,
            # )
            # response = messaging.send(message)
            
            # For now, just mark as sent
            notification.is_push_sent = True
            notification.save(update_fields=['is_push_sent', 'updated_at'])
            return True
            
        except Exception as e:
            print(f"Error sending push notification: {e}")
            return False
