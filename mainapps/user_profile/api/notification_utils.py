from django.conf import settings
from notifications.services import NotificationService

def send_kyc_approved_notification(profile, request=None):
    """Send notification when KYC is approved"""
    try:
        user = profile.user
        if not user:
            return False
            
        # Create context data for the notification
        context_data = {
            'app_name': settings.SITE_NAME,
            'user_first_name': user.first_name or user.username or 'there',
            'dashboard_url': f"{settings.SITE_URL}/dashboard"
        }
        
        # Send the notification
        NotificationService.create_notification(
            recipient=user,
            notification_type_name='verification_approved',
            context_data=context_data,
            action_url='/dashboard',
            priority='high',
            icon='check-circle',
            color='#4CAF50',  # Green color
            send_email=True,
            send_sms=True if hasattr(profile, 'phone_number') and profile.phone_number else False
        )
        
        return True
    except Exception as e:
        print(f"Error sending KYC approved notification: {e}")
        return False


def send_kyc_rejected_notification(profile, reason=None):
    """Send notification when KYC is rejected"""
    try:
        user = profile.user
        if not user:
            return False
            
        # Create context data for the notification
        context_data = {
            'app_name': settings.SITE_NAME,
            'user_first_name': user.first_name or user.username or 'there',
            'rejection_reason': reason or 'Please check your details and try again.',
            'profile_url': f"{settings.SITE_URL}/profile/update"
        }
        
        # Send the notification
        NotificationService.create_notification(
            recipient=user,
            notification_type_name='verification_rejected',
            context_data=context_data,
            action_url='/profile/update',
            priority='high',
            icon='alert-circle',
            color='#F44336',  # Red color
            send_email=True,
            send_sms=True if hasattr(profile, 'phone_number') and profile.phone_number else False
        )
        
        return True
    except Exception as e:
        print(f"Error sending KYC rejected notification: {e}")
        return False


def send_kyc_flagged_notification(profile, reason=None):
    """Send notification when KYC is flagged"""
    try:
        user = profile.user
        if not user:
            return False
            
        # Create context data for the notification
        context_data = {
            'app_name': settings.SITE_NAME,
            'user_first_name': user.first_name or user.username or 'there',
            'flag_reason': reason or 'Your verification requires additional review.',
            'profile_url': f"{settings.SITE_URL}/profile/update"
        }
        
        # Send the notification
        NotificationService.create_notification(
            recipient=user,
            notification_type_name='verification_flagged',
            context_data=context_data,
            action_url='/profile/update',
            priority='high',
            icon='alert-triangle',
            color='#FF9800',  # Orange color
            send_email=True,
            send_sms=True if hasattr(profile, 'phone_number') and profile.phone_number else False
        )
        
        return True
    except Exception as e:
        print(f"Error sending KYC flagged notification: {e}")
        return False


def send_kyc_reminder_notification(profile):
    """Send notification to remind user to complete KYC"""
    try:
        user = profile.user
        if not user:
            return False
            
        # Create context data for the notification
        context_data = {
            'app_name': settings.SITE_NAME,
            'user_first_name': user.first_name or user.username or 'there',
            'profile_url': f"{settings.SITE_URL}/profile/update"
        }
        
        # Send the notification
        NotificationService.create_notification(
            recipient=user,
            notification_type_name='profile_incomplete',
            context_data=context_data,
            action_url='/profile/update',
            priority='normal',
            icon='user-check',
            color='#FFC107',  # Yellow/amber color
            send_email=True
        )
        
        return True
    except Exception as e:
        print(f"Error sending KYC reminder notification: {e}")
        return False


def send_profile_updated_notification(profile):
    """Send notification when profile is updated"""
    try:
        user = profile.user
        if not user:
            return False
            
        # Create context data for the notification
        context_data = {
            'app_name': settings.SITE_NAME,
            'user_first_name': user.first_name or user.username or 'there',
            'profile_url': f"{settings.SITE_URL}/profile"
        }
        
        # Send the notification
        NotificationService.create_notification(
            recipient=user,
            notification_type_name='profile_updated',
            context_data=context_data,
            action_url='/profile',
            priority='low',
            icon='user',
            color='#2196F3',  # Blue color
            send_email=True
        )
        
        return True
    except Exception as e:
        print(f"Error sending profile updated notification: {e}")
        return False


def send_edit_code_notification(user, code, admin_user, admin_profile=None):
    """Send notification when edit code is requested"""
    try:
        if not user:
            return False
            
        # Create context data for the notification
        admin_name = f"{admin_user.first_name} {admin_user.last_name}".strip() or admin_user.username
        
        context_data = {
            'app_name': settings.SITE_NAME,
            'user_first_name': user.first_name or user.username or 'there',
            'verification_code': code,
            'admin_name': admin_name,
            'admin_email': admin_user.email
        }
        
        # Send the notification
        NotificationService.create_notification(
            recipient=user,
            notification_type_name='edit_code_requested',
            context_data=context_data,
            action_url=None,  # No action needed
            priority='high',
            icon='key',
            color='#9C27B0',  # Purple color
            send_email=True,
            send_sms=True  # Important security notification
        )
        
        return True
    except Exception as e:
        print(f"Error sending edit code notification: {e}")
        return False
