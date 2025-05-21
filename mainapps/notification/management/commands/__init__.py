from django.core.management.base import BaseCommand
from django.utils import timezone
from notification.services import NotificationService

class Command(BaseCommand):
    help = 'Process scheduled notifications that are due'
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Processing scheduled notifications...'))
        
        # Process scheduled notifications
        NotificationService.process_scheduled_notifications()
        
        self.stdout.write(self.style.SUCCESS('Scheduled notifications processed successfully.'))
