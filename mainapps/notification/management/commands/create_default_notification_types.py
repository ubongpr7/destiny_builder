from django.core.management.base import BaseCommand
from ...models import NotificationType, NotificationCategory, NotificationPriority

class Command(BaseCommand):
    help = 'Create default notification types'
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Creating default notification types...'))
        
        default_types = [
            {
                'name': 'project_assigned',
                'description': 'Sent when a user is assigned to a project',
                'category': NotificationCategory.PROJECT,
                'title_template': 'You have been assigned to a project',
                'body_template': 'You have been assigned to the project "${project_title}".',
                'icon': 'briefcase',
                'color': 'blue',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
            },
            {
                'name': 'project_completed',
                'description': 'Sent when a project is marked as completed',
                'category': NotificationCategory.PROJECT,
                'title_template': 'Project completed',
                'body_template': 'The project "${project_title}" has been marked as completed.',
                'icon': 'check-circle',
                'color': 'green',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
            },
            {
                'name': 'project_updated',
                'description': 'Sent when a project is updated',
                'category': NotificationCategory.PROJECT,
                'title_template': 'Project updated',
                'body_template': 'The project "${project_title}" has been updated.',
                'icon': 'refresh-cw',
                'color': 'blue',
                'default_priority': NotificationPriority.LOW,
                'send_email': False,
            },
            
            # Milestone notifications
            {
                'name': 'milestone_assigned',
                'description': 'Sent when a user is assigned to a milestone',
                'category': NotificationCategory.MILESTONE,
                'title_template': 'You have been assigned to a milestone',
                'body_template': 'You have been assigned to the milestone "${milestone_title}" in project "${project_title}".',
                'icon': 'flag',
                'color': 'purple',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
            },
            {
                'name': 'milestone_completed',
                'description': 'Sent when a milestone is marked as completed',
                'category': NotificationCategory.MILESTONE,
                'title_template': 'Milestone completed',
                'body_template': 'The milestone "${milestone_title}" in project "${project_title}" has been marked as completed.',
                'icon': 'check-circle',
                'color': 'green',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
            },
            {
                'name': 'milestone_approaching',
                'description': 'Sent when a milestone due date is approaching',
                'category': NotificationCategory.MILESTONE,
                'title_template': 'Milestone due soon',
                'body_template': 'The milestone "${milestone_title}" in project "${project_title}" is due in ${days_remaining} days.',
                'icon': 'clock',
                'color': 'orange',
                'default_priority': NotificationPriority.HIGH,
                'send_email': True,
            },
            
            # Task notifications
            {
                'name': 'task_assigned',
                'description': 'Sent when a user is assigned to a task',
                'category': NotificationCategory.TASK,
                'title_template': 'You have been assigned a task',
                'body_template': 'You have been assigned the task "${task_title}" in project "${project_title}".',
                'icon': 'check-square',
                'color': 'blue',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
            },
            {
                'name': 'task_completed',
                'description': 'Sent when a task is marked as completed',
                'category': NotificationCategory.TASK,
                'title_template': 'Task completed',
                'body_template': 'The task "${task_title}" in project "${project_title}" has been marked as completed.',
                'icon': 'check-circle',
                'color': 'green',
                'default_priority': NotificationPriority.LOW,
                'send_email': False,
            },
            {
                'name': 'task_approaching',
                'description': 'Sent when a task due date is approaching',
                'category': NotificationCategory.TASK,
                'title_template': 'Task due soon',
                'body_template': 'The task "${task_title}" in project "${project_title}" is due in ${days_remaining} days.',
                'icon': 'clock',
                'color': 'orange',
                'default_priority': NotificationPriority.HIGH,
                'send_email': True,
            },
            {
                'name': 'task_overdue',
                'description': 'Sent when a task is overdue',
                'category': NotificationCategory.TASK,
                'title_template': 'Task overdue',
                'body_template': 'The task "${task_title}" in project "${project_title}" is overdue by ${days_overdue} days.',
                'icon': 'alert-circle',
                'color': 'red',
                'default_priority': NotificationPriority.URGENT,
                'send_email': True,
                'send_sms': True,
            },
            
            # Expense notifications
            {
                'name': 'expense_approved',
                'description': 'Sent when an expense is approved',
                'category': NotificationCategory.EXPENSE,
                'title_template': 'Expense approved',
                'body_template': 'Your expense "${expense_title}" for ${expense_amount} has been approved.',
                'icon': 'check-circle',
                'color': 'green',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
            },
            {
                'name': 'expense_rejected',
                'description': 'Sent when an expense is rejected',
                'category': NotificationCategory.EXPENSE,
                'title_template': 'Expense rejected',
                'body_template': 'Your expense "${expense_title}" for ${expense_amount} has been rejected. Reason: ${rejection_reason}',
                'icon': 'x-circle',
                'color': 'red',
                'default_priority': NotificationPriority.HIGH,
                'send_email': True,
            },
            {
                'name': 'expense_disbursed',
                'description': 'Sent when an expense is disbursed',
                'category': NotificationCategory.EXPENSE,
                'title_template': 'Expense disbursed',
                'body_template': 'Your expense "${expense_title}" for ${expense_amount} has been disbursed.',
                'icon': 'credit-card',
                'color': 'green',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
            },
            
            # KYC notifications
            {
                'name': 'kyc_reminder',
                'description': 'Reminder to complete KYC verification',
                'category': NotificationCategory.KYC,
                'title_template': 'Complete your KYC verification',
                'body_template': 'Please complete your KYC verification to access all features of the platform.',
                'icon': 'user-check',
                'color': 'orange',
                'default_priority': NotificationPriority.HIGH,
                'send_email': True,
            },
            {
                'name': 'kyc_approved',
                'description': 'Sent when KYC verification is approved',
                'category': NotificationCategory.KYC,
                'title_template': 'KYC verification approved',
                'body_template': 'Your KYC verification has been approved. You now have full access to the platform.',
                'icon': 'check-circle',
                'color': 'green',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
            },
            {
                'name': 'kyc_rejected',
                'description': 'Sent when KYC verification is rejected',
                'category': NotificationCategory.KYC,
                'title_template': 'KYC verification rejected',
                'body_template': 'Your KYC verification has been rejected. Reason: ${rejection_reason}. Please update your information and try again.',
                'icon': 'x-circle',
                'color': 'red',
                'default_priority': NotificationPriority.HIGH,
                'send_email': True,
            },
            
            # Document notifications
            {
                'name': 'document_uploaded',
                'description': 'Sent when a document is uploaded',
                'category': NotificationCategory.DOCUMENT,
                'title_template': 'New document uploaded',
                'body_template': 'A new document "${document_title}" has been uploaded to project "${project_title}".',
                'icon': 'file-text',
                'color': 'blue',
                'default_priority': NotificationPriority.LOW,
                'send_email': False,
            },
            
            # System notifications
            {
                'name': 'system_maintenance',
                'description': 'Sent when system maintenance is scheduled',
                'category': NotificationCategory.SYSTEM,
                'title_template': 'System maintenance scheduled',
                'body_template': 'System maintenance is scheduled for ${maintenance_time}. The platform may be unavailable during this time.',
                'icon': 'tool',
                'color': 'orange',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
                'can_disable': False,
            },
        ]
        
        # Create notification types
        created_count = 0
        for nt_data in default_types:
            nt, created = NotificationType.objects.get_or_create(
                name=nt_data['name'],
                defaults=nt_data
            )
            if created:
                created_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'Created {created_count} notification types.'))
