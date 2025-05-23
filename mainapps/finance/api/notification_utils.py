from mainapps.notification.models import Notification, NotificationType
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Q

User = get_user_model()

def get_finance_notification_recipients():
    """Get users who should receive finance notifications"""
    return User.objects.filter(
        Q(profile__is_DB_executive=True) | 
        Q(profile__is_DB_admin=True) | 
        Q(profile__is_donor=True)
    ).distinct()

def send_donation_received_notification(donation):
    """Send notification when a donation is received"""
    try:
        notification_type = NotificationType.objects.get(name='donation_received')
        recipients = get_finance_notification_recipients()
        
        for user in recipients:
            # Check user preferences
            if hasattr(user, 'notification_preferences'):
                prefs = user.notification_preferences.filter(notification_type=notification_type).first()
                if prefs and not prefs.in_app_enabled:
                    continue
            
            # Create in-app notification
            Notification.objects.create(
                user=user,
                notification_type=notification_type,
                title=f"New Donation Received",
                message=f"A donation of ${donation.amount} has been received" + 
                       (f" for {donation.campaign.title}" if donation.campaign else ""),
                data={
                    'donation_id': donation.id,
                    'amount': str(donation.amount),
                    'campaign_id': donation.campaign.id if donation.campaign else None,
                    'donor_name': donation.donor_name_display if not donation.is_anonymous else 'Anonymous'
                }
            )
            
            # Send email if enabled
            if hasattr(user, 'notification_preferences'):
                prefs = user.notification_preferences.filter(notification_type=notification_type).first()
                if prefs and prefs.email_enabled:
                    send_donation_email(user, donation)
    
    except NotificationType.DoesNotExist:
        pass

def send_campaign_milestone_notification(campaign, milestone_type):
    """Send notification when campaign reaches milestones"""
    try:
        notification_type = NotificationType.objects.get(name='campaign_milestone')
        recipients = get_finance_notification_recipients()
        
        milestone_messages = {
            '50_percent': f"Campaign '{campaign.title}' has reached 50% of its target!",
            '75_percent': f"Campaign '{campaign.title}' has reached 75% of its target!",
            'target_reached': f"Campaign '{campaign.title}' has reached its target amount!"
        }
        
        message = milestone_messages.get(milestone_type, f"Campaign '{campaign.title}' milestone reached")
        
        for user in recipients:
            # Check user preferences
            if hasattr(user, 'notification_preferences'):
                prefs = user.notification_preferences.filter(notification_type=notification_type).first()
                if prefs and not prefs.in_app_enabled:
                    continue
            
            Notification.objects.create(
                user=user,
                notification_type=notification_type,
                title="Campaign Milestone",
                message=message,
                data={
                    'campaign_id': campaign.id,
                    'milestone_type': milestone_type,
                    'progress_percentage': campaign.progress_percentage,
                    'target_amount': str(campaign.target_amount),
                    'current_amount': str(campaign.current_amount)
                }
            )
    
    except NotificationType.DoesNotExist:
        pass

def send_grant_status_notification(grant, old_status, new_status):
    """Send notification when grant status changes"""
    try:
        notification_type = NotificationType.objects.get(name='grant_status_change')
        recipients = get_finance_notification_recipients()
        
        for user in recipients:
            # Check user preferences
            if hasattr(user, 'notification_preferences'):
                prefs = user.notification_preferences.filter(notification_type=notification_type).first()
                if prefs and not prefs.in_app_enabled:
                    continue
            
            Notification.objects.create(
                user=user,
                notification_type=notification_type,
                title="Grant Status Update",
                message=f"Grant '{grant.title}' status changed from {old_status} to {new_status}",
                data={
                    'grant_id': grant.id,
                    'old_status': old_status,
                    'new_status': new_status,
                    'amount': str(grant.amount),
                    'grantor': grant.grantor
                }
            )
    
    except NotificationType.DoesNotExist:
        pass

def send_budget_alert_notification(budget, alert_type):
    """Send notification for budget alerts"""
    try:
        notification_type = NotificationType.objects.get(name='budget_alert')
        recipients = get_finance_notification_recipients()
        
        alert_messages = {
            'approved': f"Budget '{budget.title}' has been approved",
            '80_percent': f"Budget '{budget.title}' is 80% spent",
            '90_percent': f"Budget '{budget.title}' is 90% spent - approaching limit!",
            'overspent': f"Budget '{budget.title}' has exceeded its allocated amount!"
        }
        
        message = alert_messages.get(alert_type, f"Budget '{budget.title}' alert")
        
        for user in recipients:
            # Check user preferences
            if hasattr(user, 'notification_preferences'):
                prefs = user.notification_preferences.filter(notification_type=notification_type).first()
                if prefs and not prefs.in_app_enabled:
                    continue
            
            Notification.objects.create(
                user=user,
                notification_type=notification_type,
                title="Budget Alert",
                message=message,
                data={
                    'budget_id': budget.id,
                    'alert_type': alert_type,
                    'spent_percentage': budget.spent_percentage,
                    'total_amount': str(budget.total_amount),
                    'spent_amount': str(budget.spent_amount)
                }
            )
    
    except NotificationType.DoesNotExist:
        pass

def send_expense_approval_notification(expense, approved_by):
    """Send notification when expense is approved/rejected"""
    try:
        notification_type = NotificationType.objects.get(name='expense_approval')
        
        # Notify the person who submitted the expense
        if hasattr(expense.submitted_by, 'notification_preferences'):
            prefs = expense.submitted_by.notification_preferences.filter(notification_type=notification_type).first()
            if not prefs or prefs.in_app_enabled:
                Notification.objects.create(
                    user=expense.submitted_by,
                    notification_type=notification_type,
                    title=f"Expense {expense.status.title()}",
                    message=f"Your expense '{expense.title}' has been {expense.status} by {approved_by.get_full_name()}",
                    data={
                        'expense_id': expense.id,
                        'status': expense.status,
                        'amount': str(expense.amount),
                        'approved_by': approved_by.get_full_name()
                    }
                )
    
    except NotificationType.DoesNotExist:
        pass

def send_recurring_donation_notification(recurring_donation, notification_type_name):
    """Send notification for recurring donation events"""
    try:
        notification_type = NotificationType.objects.get(name=notification_type_name)
        recipients = get_finance_notification_recipients()
        
        messages = {
            'recurring_donation_created': f"New recurring donation set up: ${recurring_donation.amount} {recurring_donation.frequency}",
            'recurring_donation_cancelled': f"Recurring donation cancelled: ${recurring_donation.amount} {recurring_donation.frequency}"
        }
        
        message = messages.get(notification_type_name, "Recurring donation update")
        
        for user in recipients:
            # Check user preferences
            if hasattr(user, 'notification_preferences'):
                prefs = user.notification_preferences.filter(notification_type=notification_type).first()
                if prefs and not prefs.in_app_enabled:
                    continue
            
            Notification.objects.create(
                user=user,
                notification_type=notification_type,
                title="Recurring Donation Update",
                message=message,
                data={
                    'recurring_donation_id': recurring_donation.id,
                    'amount': str(recurring_donation.amount),
                    'frequency': recurring_donation.frequency,
                    'status': recurring_donation.status
                }
            )
    
    except NotificationType.DoesNotExist:
        pass

def send_donation_email(user, donation):
    """Send email notification for donation"""
    subject = f"New Donation Received - ${donation.amount}"
    
    context = {
        'user': user,
        'donation': donation,
        'site_name': getattr(settings, 'SITE_NAME', 'Organization Platform')
    }
    
    html_message = render_to_string('notifications/email/donation_received.html', context)
    plain_message = render_to_string('notifications/email/donation_received.txt', context)
    
    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=True
    )
