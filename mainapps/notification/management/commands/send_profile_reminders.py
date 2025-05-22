from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from django.conf import settings
from datetime import timedelta

from ...services import NotificationService
from mainapps.accounts.models import UserProfile

User = get_user_model()

class Command(BaseCommand):
    help = 'Send reminders to users with incomplete profiles'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=2,
            help='Days since registration to send reminder'
        )

    def handle(self, *args, **options):
        days = options['days']
        # Get users who registered more than X days ago but haven't completed KYC
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Find users who:
        # 1. Registered before the cutoff date
        # 2. Have a profile
        # 3. Profile KYC status is still pending
        # 4. Haven't received a reminder in the last week
        incomplete_users = User.objects.filter(
            date_joined__lt=cutoff_date,
            profile__isnull=False,
            profile__kyc_status='pending',
            # Add a filter for users who haven't received a reminder recently
            # This would require tracking when reminders were sent
        ).distinct()
        
        count = 0
        for user in incomplete_users:
            try:
                # Check if profile has minimal required fields
                profile = user.profile
                
                # Skip if profile is reasonably complete
                if self._is_profile_reasonably_complete(profile):
                    continue
                
                # Create context data for the notification
                context_data = {
                    'app_name': settings.SITE_NAME,
                    'user_first_name': user.first_name or 'there',
                    'profile_url': f"{settings.SITE_URL}{reverse('profile-update')}"
                }
                
                # Send the notification
                NotificationService.create_notification(
                    recipient=user,
                    notification_type_name='profile_incomplete',
                    context_data=context_data,
                    action_url=reverse('profile-update'),
                    priority='normal',
                    icon='user-check',
                    color='#FFC107',  # Yellow/amber color
                    send_email=True
                )
                
                count += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Error sending reminder to user {user.id}: {e}"))
        
        self.stdout.write(self.style.SUCCESS(f'Successfully sent {count} profile completion reminders'))
    
    def _is_profile_reasonably_complete(self, profile):
        """Check if a profile has the minimum required fields completed"""
        # Define the minimum fields required for a "reasonably complete" profile
        # This is a simplified check - adjust based on your requirements
        
        # Check basic profile fields
        basic_fields_complete = all([
            profile.phone_number,
            profile.date_of_birth,
        ])
        
        # Check address if it exists
        address_complete = False
        if profile.address:
            address_complete = all([
                profile.address.street,
                profile.address.city,
                profile.address.country,
            ])
        
        # Check KYC document fields
        kyc_fields_complete = all([
            profile.id_document_type,
            profile.id_document_number,
            profile.id_document_image_front,
            profile.selfie_image,
        ])
        
        return basic_fields_complete and address_complete and kyc_fields_complete
