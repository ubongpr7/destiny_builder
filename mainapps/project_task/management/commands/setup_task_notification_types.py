from django.core.management.base import BaseCommand
from mainapps.notification.models import NotificationType

class Command(BaseCommand):
    help = 'Sets up notification types for the task management system'

    def handle(self, *args, **options):
        # Define notification types
        notification_types = [
            {
                'name': 'task_created',
                'description': 'A new task has been created',
                'send_email': True,
                'send_push': False,
                'can_disable': True,
            },
            {
                'name': 'task_assigned',
                'description': 'You have been assigned to a task',
                'send_email': True,
                'send_push': True,
                'can_disable': True,
            },
            {
                'name': 'task_unassigned',
                'description': 'You have been unassigned from a task',
                'send_email': True,
                'send_push': False,
                'can_disable': True,
            },
            {
                'name': 'task_status_changed',
                'description': 'A task status has been changed',
                'send_email': True,
                'send_push': False,
                'can_disable': True,
            },
            {
                'name': 'task_completed',
                'description': 'A task has been completed',
                'send_email': True,
                'send_push': False,
                'can_disable': True,
            },
            {
                'name': 'task_approaching_due',
                'description': 'A task is approaching its due date',
                'send_email': True,
                'send_push': True,
                'can_disable': True,
            },
            {
                'name': 'task_overdue',
                'description': 'A task is overdue',
                'send_email': True,
                'send_push': True,
                'can_disable': True,
            },
            {
                'name': 'task_comment_added',
                'description': 'A comment has been added to a task',
                'send_email': True,
                'send_push': False,
                'can_disable': True,
            },
            {
                'name': 'task_attachment_added',
                'description': 'An attachment has been added to a task',
                'send_email': True,
                'send_push': False,
                'can_disable': True,
            },
            {
                'name': 'task_time_logged',
                'description': 'Time has been logged on a task',
                'send_email': False,
                'send_push': False,
                'can_disable': True,
            },
            {
                'name': 'task_dependency_completed',
                'description': 'A task dependency has been completed',
                'send_email': True,
                'send_push': False,
                'can_disable': True,
            },
            {
                'name': 'task_priority_changed',
                'description': 'A task priority has been changed',
                'send_email': True,
                'send_push': False,
                'can_disable': True,
            },
            {
                'name': 'subtask_created',
                'description': 'A subtask has been created',
                'send_email': True,
                'send_push': False,
                'can_disable': True,
            },
        ]

        # Create or update notification types
        for nt in notification_types:
            obj, created = NotificationType.objects.update_or_create(
                name=nt['name'],
                defaults={
                    'description': nt['description'],
                    'send_email': nt['send_email'],
                    'send_push': nt['send_push'],
                    'can_disable': nt['can_disable'],
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created notification type: {nt['name']}"))
            else:
                self.stdout.write(self.style.SUCCESS(f"Updated notification type: {nt['name']}"))

        self.stdout.write(self.style.SUCCESS('Successfully set up task notification types'))
