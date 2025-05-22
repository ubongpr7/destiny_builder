from django.core.management.base import BaseCommand
from ...models import NotificationType, NotificationCategory

class Command(BaseCommand):
    help = 'Set up notification types for the application'

    def handle(self, *args, **options):
        # Define notification types
        notification_types = [
            # Existing notification types
            {
                'name': 'welcome_message',
                'description': 'Welcome message for new users',
                'category': 'account',
                'title_template': 'Welcome to $app_name!',
                'body_template': 'Thank you for joining $app_name, $user_first_name! Complete your profile to get verified and access all features.',
                'icon': 'user-plus',
                'color': '#4CAF50',
                'default_priority': 'normal',
                'send_email': True,
                'send_sms': False,
                'send_push': True,
                'is_active': True,
                'can_disable': False,
            },
            {
                'name': 'profile_incomplete',
                'description': 'Reminder to complete profile',
                'category': 'account',
                'title_template': 'Complete your profile',
                'body_template': '$user_first_name, your profile is incomplete. Complete it to get verified and access all features.',
                'icon': 'user-check',
                'color': '#FFC107',
                'default_priority': 'normal',
                'send_email': True,
                'send_sms': False,
                'send_push': True,
                'is_active': True,
                'can_disable': True,
            },
            {
                'name': 'verification_approved',
                'description': 'KYC verification approved',
                'category': 'account',
                'title_template': 'Your account is verified!',
                'body_template': 'Congratulations $user_first_name! Your account has been verified. You now have access to all features.',
                'icon': 'check-circle',
                'color': '#4CAF50',
                'default_priority': 'high',
                'send_email': True,
                'send_sms': True,
                'send_push': True,
                'is_active': True,
                'can_disable': False,
            },
            {
                'name': 'verification_rejected',
                'description': 'KYC verification rejected',
                'category': 'account',
                'title_template': 'Verification unsuccessful',
                'body_template': '$user_first_name, your verification was not approved. Reason: $rejection_reason',
                'icon': 'alert-circle',
                'color': '#F44336',
                'default_priority': 'high',
                'send_email': True,
                'send_sms': True,
                'send_push': True,
                'is_active': True,
                'can_disable': False,
            },
            {
                'name': 'verification_flagged',
                'description': 'KYC verification flagged for review',
                'category': 'account',
                'title_template': 'Verification under review',
                'body_template': '$user_first_name, your verification is under additional review. We\'ll notify you once the process is complete.',
                'icon': 'alert-triangle',
                'color': '#FF9800',
                'default_priority': 'high',
                'send_email': True,
                'send_sms': True,
                'send_push': True,
                'is_active': True,
                'can_disable': False,
            },
            # New notification types
            {
                'name': 'profile_updated',
                'description': 'Profile information updated',
                'category': 'account',
                'title_template': 'Profile Updated',
                'body_template': '$user_first_name, your profile information has been updated successfully.',
                'icon': 'user',
                'color': '#2196F3',
                'default_priority': 'low',
                'send_email': True,
                'send_sms': False,
                'send_push': True,
                'is_active': True,
                'can_disable': True,
            },
            {
                'name': 'edit_code_requested',
                'description': 'Profile edit verification code',
                'category': 'security',
                'title_template': 'Profile Edit Authorization Code',
                'body_template': '$user_first_name, an administrator ($admin_name) has requested to edit your profile. Your verification code is: $verification_code',
                'icon': 'key',
                'color': '#9C27B0',
                'default_priority': 'high',
                'send_email': True,
                'send_sms': True,
                'send_push': True,
                'is_active': True,
                'can_disable': False,
            },
        ]

        # Create notification types
        created_count = 0
        updated_count = 0

        for nt_data in notification_types:
            nt, created = NotificationType.objects.update_or_create(
                name=nt_data['name'],
                defaults=nt_data
            )
            
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Successfully set up notification types: {created_count} created, {updated_count} updated'
        ))
