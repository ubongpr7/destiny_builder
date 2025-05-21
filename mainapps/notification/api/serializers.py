from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from ..models import (
    Notification, NotificationType, NotificationPreference,
    NotificationBatch, ScheduledNotification
)

User = get_user_model()

class NotificationTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationType
        fields = [
            'id', 'name', 'description', 'category', 
            'title_template', 'body_template', 'icon', 'color',
            'default_priority', 'send_email', 'send_sms', 'send_push',
            'is_active', 'can_disable', 'created_at', 'updated_at'
        ]

class NotificationSerializer(serializers.ModelSerializer):
    notification_type_name = serializers.CharField(source='notification_type.name', read_only=True)
    notification_type_category = serializers.CharField(source='notification_type.category', read_only=True)
    recipient_name = serializers.SerializerMethodField()
    related_object_type = serializers.SerializerMethodField()
    related_object_id = serializers.SerializerMethodField()
    time_ago = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = [
            'id', 'recipient', 'recipient_name', 'notification_type', 
            'notification_type_name', 'notification_type_category',
            'title', 'body', 'priority', 'icon', 'color', 'action_url',
            'related_object_type', 'related_object_id', 'data',
            'is_read', 'read_at', 'is_email_sent', 'is_sms_sent', 'is_push_sent',
            'created_at', 'updated_at', 'time_ago'
        ]
    
    def get_recipient_name(self, obj):
        if obj.recipient.first_name or obj.recipient.last_name:
            return f"{obj.recipient.first_name} {obj.recipient.last_name}".strip()
        return obj.recipient.username
    
    def get_related_object_type(self, obj):
        if obj.content_type:
            return obj.content_type.model
        return None
    
    def get_related_object_id(self, obj):
        if obj.object_id:
            return obj.object_id
        return None
    
    def get_time_ago(self, obj):
        from django.utils import timezone
        from django.utils.timesince import timesince
        return timesince(obj.created_at, timezone.now())

class NotificationPreferenceSerializer(serializers.ModelSerializer):
    notification_type_name = serializers.CharField(source='notification_type.name', read_only=True)
    notification_type_category = serializers.CharField(source='notification_type.category', read_only=True)
    
    class Meta:
        model = NotificationPreference
        fields = [
            'id', 'user', 'notification_type', 'notification_type_name',
            'notification_type_category', 'receive_in_app', 'receive_email',
            'receive_sms', 'receive_push', 'created_at', 'updated_at'
        ]

class NotificationBatchSerializer(serializers.ModelSerializer):
    notification_type_name = serializers.CharField(source='notification_type.name', read_only=True)
    
    class Meta:
        model = NotificationBatch
        fields = [
            'id', 'name', 'notification_type', 'notification_type_name',
            'template_data', 'status', 'error_message', 'notifications_count',
            'created_at', 'updated_at', 'processed_at'
        ]

class ScheduledNotificationSerializer(serializers.ModelSerializer):
    notification_type_name = serializers.CharField(source='notification_type.name', read_only=True)
    recipient_name = serializers.SerializerMethodField()
    
    class Meta:
        model = ScheduledNotification
        fields = [
            'id', 'notification_type', 'notification_type_name', 'recipient',
            'recipient_name', 'template_data', 'scheduled_time', 'is_recurring',
            'recurrence_pattern', 'status', 'notification', 'created_at', 'updated_at'
        ]
    
    def get_recipient_name(self, obj):
        if obj.recipient.first_name or obj.recipient.last_name:
            return f"{obj.recipient.first_name} {obj.recipient.last_name}".strip()
        return obj.recipient.username

class CreateNotificationSerializer(serializers.Serializer):
    recipients = serializers.ListField(
        child=serializers.IntegerField(),
        required=True,
        help_text="List of user IDs to send notification to"
    )
    notification_type = serializers.CharField(
        required=True,
        help_text="Name of the notification type"
    )
    context_data = serializers.JSONField(
        required=False,
        default=dict,
        help_text="Data to use in notification templates"
    )
    related_object_type = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Content type of related object (e.g., 'project.project')"
    )
    related_object_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="ID of related object"
    )
    action_url = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="URL to redirect to when notification is clicked"
    )
    priority = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Priority of notification"
    )
    icon = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Icon to use for notification"
    )
    color = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Color to use for notification"
    )
    send_email = serializers.BooleanField(
        required=False,
        allow_null=True,
        help_text="Whether to send email notification"
    )
    send_sms = serializers.BooleanField(
        required=False,
        allow_null=True,
        help_text="Whether to send SMS notification"
    )
    send_push = serializers.BooleanField(
        required=False,
        allow_null=True,
        help_text="Whether to send push notification"
    )
    
    def validate(self, data):
        # Validate notification type
        notification_type = data.get('notification_type')
        try:
            NotificationType.objects.get(name=notification_type)
        except NotificationType.DoesNotExist:
            raise serializers.ValidationError(f"Notification type '{notification_type}' does not exist")
        
        # Validate recipients
        recipients = data.get('recipients', [])
        if not recipients:
            raise serializers.ValidationError("At least one recipient is required")
        
        valid_recipients = []
        for recipient_id in recipients:
            try:
                User.objects.get(id=recipient_id)
                valid_recipients.append(recipient_id)
            except User.DoesNotExist:
                pass
        
        if not valid_recipients:
            raise serializers.ValidationError("No valid recipients found")
        
        data['recipients'] = valid_recipients
        
        # Validate related object if provided
        related_object_type = data.get('related_object_type')
        related_object_id = data.get('related_object_id')
        
        if related_object_type and related_object_id:
            try:
                app_label, model = related_object_type.split('.')
                content_type = ContentType.objects.get(app_label=app_label, model=model)
                model_class = content_type.model_class()
                model_class.objects.get(id=related_object_id)
            except (ValueError, ContentType.DoesNotExist):
                raise serializers.ValidationError(f"Invalid related object type: {related_object_type}")
            except Exception:
                raise serializers.ValidationError(f"Related object not found: {related_object_type} {related_object_id}")
        
        return data

class ScheduleNotificationSerializer(serializers.Serializer):
    recipient = serializers.IntegerField(
        required=True,
        help_text="User ID to send notification to"
    )
    notification_type = serializers.CharField(
        required=True,
        help_text="Name of the notification type"
    )
    scheduled_time = serializers.DateTimeField(
        required=True,
        help_text="When to send the notification"
    )
    context_data = serializers.JSONField(
        required=False,
        default=dict,
        help_text="Data to use in notification templates"
    )
    is_recurring = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Whether this is a recurring notification"
    )
    recurrence_pattern = serializers.CharField(
        required=False,
        default='',
        help_text="Recurrence pattern (daily, weekly, monthly, etc.)"
    )
    
    def validate(self, data):
        # Validate notification type
        notification_type = data.get('notification_type')
        try:
            NotificationType.objects.get(name=notification_type)
        except NotificationType.DoesNotExist:
            raise serializers.ValidationError(f"Notification type '{notification_type}' does not exist")
        
        # Validate recipient
        recipient_id = data.get('recipient')
        try:
            User.objects.get(id=recipient_id)
        except User.DoesNotExist:
            raise serializers.ValidationError(f"User with ID {recipient_id} does not exist")
        
        # Validate recurrence pattern if recurring
        is_recurring = data.get('is_recurring', False)
        recurrence_pattern = data.get('recurrence_pattern', '')
        
        if is_recurring and not recurrence_pattern:
            raise serializers.ValidationError("Recurrence pattern is required for recurring notifications")
        
        valid_patterns = ['daily', 'weekly', 'monthly', 'yearly']
        if is_recurring and recurrence_pattern not in valid_patterns and not recurrence_pattern.startswith('every_'):
            raise serializers.ValidationError(f"Invalid recurrence pattern. Valid patterns are: {', '.join(valid_patterns)} or 'every_N_days/weeks/months/years'")
        
        return data
