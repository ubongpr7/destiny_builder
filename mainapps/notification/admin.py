from django.contrib import admin
from .models import (
    NotificationType, Notification, NotificationPreference,
    NotificationBatch, ScheduledNotification
)

@admin.register(NotificationType)
class NotificationTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'is_active', 'can_disable', 'default_priority')
    list_filter = ('category', 'is_active', 'can_disable', 'default_priority')
    search_fields = ('name', 'description')
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'category', 'is_active', 'can_disable')
        }),
        ('Templates', {
            'fields': ('title_template', 'body_template')
        }),
        ('Appearance', {
            'fields': ('icon', 'color', 'default_priority')
        }),
        ('Delivery Methods', {
            'fields': ('send_email', 'send_sms', 'send_push')
        }),
    )

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'notification_type', 'title', 'is_read', 'created_at')
    list_filter = ('is_read', 'priority', 'notification_type__category', 'created_at')
    search_fields = ('recipient__username', 'recipient__email', 'title', 'body')
    raw_id_fields = ('recipient', 'notification_type')
    readonly_fields = ('created_at', 'updated_at', 'read_at')
    fieldsets = (
        (None, {
            'fields': ('recipient', 'notification_type', 'title', 'body')
        }),
        ('Status', {
            'fields': ('is_read', 'read_at')
        }),
        ('Appearance', {
            'fields': ('priority', 'icon', 'color', 'action_url')
        }),
        ('Related Object', {
            'fields': ('content_type', 'object_id')
        }),
        ('Delivery Status', {
            'fields': ('is_email_sent', 'is_sms_sent', 'is_push_sent')
        }),
        ('Additional Data', {
            'fields': ('data',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )

@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'notification_type', 'receive_in_app', 'receive_email', 'receive_sms', 'receive_push')
    list_filter = ('receive_in_app', 'receive_email', 'receive_sms', 'receive_push', 'notification_type__category')
    search_fields = ('user__username', 'user__email', 'notification_type__name')
    raw_id_fields = ('user', 'notification_type')

@admin.register(NotificationBatch)
class NotificationBatchAdmin(admin.ModelAdmin):
    list_display = ('name', 'notification_type', 'status', 'notifications_count', 'created_at', 'processed_at')
    list_filter = ('status', 'notification_type__category', 'created_at')
    search_fields = ('name', 'notification_type__name')
    raw_id_fields = ('notification_type',)
    readonly_fields = ('created_at', 'updated_at', 'processed_at')

@admin.register(ScheduledNotification)
class ScheduledNotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'notification_type', 'scheduled_time', 'status', 'is_recurring')
    list_filter = ('status', 'is_recurring', 'notification_type__category', 'scheduled_time')
    search_fields = ('recipient__username', 'recipient__email', 'notification_type__name')
    raw_id_fields = ('recipient', 'notification_type', 'notification')
    readonly_fields = ('created_at', 'updated_at')
