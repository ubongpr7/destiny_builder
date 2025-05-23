from django.core.management.base import BaseCommand
from mainapps.notification.models import NotificationType

class Command(BaseCommand):
    help = 'Set up notification types for finance app'

    def handle(self, *args, **options):
        notification_types = [
            {
                'name': 'donation_received',
                'description': 'Notification when a donation is received',
                'category': 'finance'
            },
            {
                'name': 'campaign_milestone',
                'description': 'Notification when campaign reaches milestones',
                'category': 'finance'
            },
            {
                'name': 'grant_status_change',
                'description': 'Notification when grant status changes',
                'category': 'finance'
            },
            {
                'name': 'budget_alert',
                'description': 'Notification for budget alerts and approvals',
                'category': 'finance'
            },
            {
                'name': 'expense_approval',
                'description': 'Notification when expense is approved/rejected',
                'category': 'finance'
            },
            {
                'name': 'recurring_donation_created',
                'description': 'Notification when recurring donation is created',
                'category': 'finance'
            },
            {
                'name': 'recurring_donation_cancelled',
                'description': 'Notification when recurring donation is cancelled',
                'category': 'finance'
            },
        ]

        for nt_data in notification_types:
            notification_type, created = NotificationType.objects.get_or_create(
                name=nt_data['name'],
                defaults={
                    'description': nt_data['description'],
                    'category': nt_data['category']
                }
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created notification type: {notification_type.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Notification type already exists: {notification_type.name}')
                )

        self.stdout.write(
            self.style.SUCCESS('Finance notification types setup completed!')
        )
