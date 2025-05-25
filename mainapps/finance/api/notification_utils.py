from mainapps.notification.models import Notification, NotificationType
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Q
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from decimal import Decimal
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

def get_finance_notification_recipients(role_filter=None):
    """Get users who should receive finance notifications"""
    base_query = User.objects.filter(
        Q(profile__is_DB_executive=True) | 
        Q(profile__is_DB_admin=True) | 
        Q(groups__name__in=['Finance Managers', 'Accountants', 'Grant Managers', 'Donation Managers']) |
        Q(is_staff=True)
    ).distinct()
    
    if role_filter:
        if role_filter == 'finance_managers':
            return base_query.filter(groups__name='Finance Managers')
        elif role_filter == 'accountants':
            return base_query.filter(groups__name='Accountants')
        elif role_filter == 'grant_managers':
            return base_query.filter(groups__name='Grant Managers')
        elif role_filter == 'donation_managers':
            return base_query.filter(groups__name='Donation Managers')
    
    return base_query

def create_notification(notification_type_name, recipients, title, body, related_object=None, data=None, priority='normal'):
    """Create notifications for multiple recipients"""
    try:
        notification_type = NotificationType.objects.get(name=notification_type_name)
        
        if not isinstance(recipients, list):
            recipients = [recipients]
        
        notifications_created = []
        
        for user in recipients:
            # Check user preferences
            if hasattr(user, 'notification_preferences'):
                prefs = user.notification_preferences.filter(notification_type=notification_type).first()
                if prefs and not prefs.receive_in_app:
                    continue
            
            # Set content type and object id if related object provided
            content_type = None
            object_id = None
            if related_object:
                content_type = ContentType.objects.get_for_model(related_object)
                object_id = related_object.pk
            
            notification = Notification.objects.create(
                recipient=user,
                notification_type=notification_type,
                title=title,
                body=body,
                priority=priority,
                icon=notification_type.icon,
                color=notification_type.color,
                content_type=content_type,
                object_id=object_id,
                data=data or {}
            )
            notifications_created.append(notification)
            
            # Send email if enabled
            if notification_type.send_email and hasattr(user, 'notification_preferences'):
                prefs = user.notification_preferences.filter(notification_type=notification_type).first()
                if not prefs or prefs.receive_email:
                    send_notification_email(user, notification)
        
        return notifications_created
    
    except NotificationType.DoesNotExist:
        logger.error(f"Notification type '{notification_type_name}' does not exist")
        return []

# Donation Notifications
def send_donation_received_notification(donation):
    """Send notification when a donation is received"""
    recipients = get_finance_notification_recipients('donation_managers')
    
    campaign_info = f" for campaign '{donation.campaign.title}'" if donation.campaign else ""
    donor_info = f" from {donation.donor_name_display}" if not donation.is_anonymous else " from an anonymous donor"
    
    title = "New Donation Received"
    body = f"A donation of {donation.currency.code} {donation.amount:,.2f} has been received{campaign_info}{donor_info}"
    
    # Check if it's a large donation (over $1000 or equivalent)
    if donation.amount >= Decimal('1000.00'):
        create_notification(
            'large_donation_received',
            recipients,
            "Large Donation Alert!",
            f"A significant donation of {donation.currency.code} {donation.amount:,.2f} has been received{campaign_info}",
            related_object=donation,
            data={
                'donation_id': donation.id,
                'amount': str(donation.amount),
                'currency': donation.currency.code,
                'campaign_id': donation.campaign.id if donation.campaign else None,
                'donor_name': donation.donor_name_display,
                'payment_method': donation.payment_method
            },
            priority='high'
        )
    else:
        create_notification(
            'donation_received',
            recipients,
            title,
            body,
            related_object=donation,
            data={
                'donation_id': donation.id,
                'amount': str(donation.amount),
                'currency': donation.currency.code,
                'campaign_id': donation.campaign.id if donation.campaign else None,
                'donor_name': donation.donor_name_display,
                'payment_method': donation.payment_method
            }
        )

def send_recurring_donation_notification(recurring_donation, event_type):
    """Send notification for recurring donation events"""
    recipients = get_finance_notification_recipients('donation_managers')
    
    if event_type == 'created':
        title = "New Recurring Donation"
        body = f"A recurring donation of {recurring_donation.currency.code} {recurring_donation.amount:,.2f} {recurring_donation.frequency} has been set up"
        notification_type = 'recurring_donation_created'
    elif event_type == 'cancelled':
        title = "Recurring Donation Cancelled"
        body = f"A recurring donation of {recurring_donation.currency.code} {recurring_donation.amount:,.2f} {recurring_donation.frequency} has been cancelled"
        notification_type = 'recurring_donation_cancelled'
    elif event_type == 'payment_failed':
        title = "Recurring Payment Failed"
        body = f"A recurring payment of {recurring_donation.currency.code} {recurring_donation.amount:,.2f} has failed. Please check payment method."
        notification_type = 'recurring_payment_failed'
        # Also notify the donor
        if recurring_donation.donor:
            recipients.append(recurring_donation.donor)
    else:
        return
    
    create_notification(
        notification_type,
        recipients,
        title,
        body,
        related_object=recurring_donation,
        data={
            'recurring_donation_id': recurring_donation.id,
            'amount': str(recurring_donation.amount),
            'currency': recurring_donation.currency.code,
            'frequency': recurring_donation.frequency,
            'status': recurring_donation.status,
            'donor_name': recurring_donation.donor.get_full_name() if recurring_donation.donor else 'Unknown'
        }
    )

def send_in_kind_donation_notification(in_kind_donation):
    """Send notification for in-kind donations"""
    recipients = get_finance_notification_recipients('donation_managers')
    
    title = "In-Kind Donation Received"
    body = f"An in-kind donation has been received: {in_kind_donation.item_description} (valued at {in_kind_donation.valuation_currency.code} {in_kind_donation.estimated_value:,.2f})"
    
    create_notification(
        'in_kind_donation_received',
        recipients,
        title,
        body,
        related_object=in_kind_donation,
        data={
            'donation_id': in_kind_donation.id,
            'item_description': in_kind_donation.item_description,
            'estimated_value': str(in_kind_donation.estimated_value),
            'currency': in_kind_donation.valuation_currency.code,
            'donor_name': in_kind_donation.donor_name_display,
            'category': in_kind_donation.category or 'Uncategorized'
        }
    )

# Campaign Notifications
def send_campaign_milestone_notification(campaign, milestone_percentage):
    """Send notification when campaign reaches milestones"""
    recipients = get_finance_notification_recipients('donation_managers')
    
    if milestone_percentage >= 100:
        title = "Campaign Target Achieved!"
        body = f"Congratulations! Campaign '{campaign.title}' has reached its target of {campaign.target_currency.code} {campaign.target_amount:,.2f}!"
        notification_type = 'campaign_target_reached'
        priority = 'high'
    else:
        title = "Campaign Milestone Reached!"
        body = f"Campaign '{campaign.title}' has reached {milestone_percentage}% of its target!"
        notification_type = 'campaign_milestone'
        priority = 'normal'
    
    create_notification(
        notification_type,
        recipients,
        title,
        body,
        related_object=campaign,
        data={
            'campaign_id': campaign.id,
            'milestone_percentage': milestone_percentage,
            'target_amount': str(campaign.target_amount),
            'current_amount': str(campaign.current_amount_in_target_currency),
            'currency': campaign.target_currency.code
        },
        priority=priority
    )

def send_campaign_ending_notification(campaign, days_remaining):
    """Send notification when campaign is ending soon"""
    recipients = get_finance_notification_recipients('donation_managers')
    
    title = "Campaign Ending Soon"
    body = f"Campaign '{campaign.title}' will end in {days_remaining} days"
    
    create_notification(
        'campaign_ending_soon',
        recipients,
        title,
        body,
        related_object=campaign,
        data={
            'campaign_id': campaign.id,
            'days_remaining': days_remaining,
            'target_amount': str(campaign.target_amount),
            'current_amount': str(campaign.current_amount_in_target_currency),
            'currency': campaign.target_currency.code
        }
    )

# Grant Notifications
def send_grant_status_notification(grant, old_status, new_status):
    """Send notification when grant status changes"""
    recipients = get_finance_notification_recipients('grant_managers')
    
    if new_status == 'approved':
        title = "Grant Approved!"
        body = f"Great news! Grant '{grant.title}' for {grant.currency.code} {grant.amount:,.2f} has been approved by {grant.grantor}"
        notification_type = 'grant_approved'
        priority = 'high'
    else:
        title = "Grant Status Update"
        body = f"Grant '{grant.title}' status changed from {old_status} to {new_status}"
        notification_type = 'grant_status_change'
        priority = 'normal'
    
    # Also notify the grant manager if assigned
    if grant.managed_by:
        recipients = list(recipients) + [grant.managed_by]
    
    create_notification(
        notification_type,
        recipients,
        title,
        body,
        related_object=grant,
        data={
            'grant_id': grant.id,
            'old_status': old_status,
            'new_status': new_status,
            'amount': str(grant.amount),
            'currency': grant.currency.code,
            'grantor': grant.grantor
        },
        priority=priority
    )

def send_grant_report_due_notification(grant_report):
    """Send notification when grant report is due"""
    recipients = []
    
    # Notify grant managers
    recipients.extend(get_finance_notification_recipients('grant_managers'))
    
    # Notify the specific grant manager if assigned
    if grant_report.grant.managed_by:
        recipients.append(grant_report.grant.managed_by)
    
    title = "Grant Report Due"
    body = f"Grant report for '{grant_report.grant.title}' is due on {grant_report.due_date}"
    
    create_notification(
        'grant_report_due',
        recipients,
        title,
        body,
        related_object=grant_report,
        data={
            'grant_report_id': grant_report.id,
            'grant_id': grant_report.grant.id,
            'grant_title': grant_report.grant.title,
            'due_date': grant_report.due_date.isoformat(),
            'report_type': grant_report.report_type
        },
        priority='high'
    )

def send_grant_disbursement_notification(grant, amount):
    """Send notification when grant disbursement is received"""
    recipients = get_finance_notification_recipients('grant_managers')
    
    if grant.managed_by:
        recipients = list(recipients) + [grant.managed_by]
    
    title = "Grant Disbursement Received"
    body = f"Grant disbursement of {grant.currency.code} {amount:,.2f} received for '{grant.title}'"
    
    create_notification(
        'grant_disbursement_received',
        recipients,
        title,
        body,
        related_object=grant,
        data={
            'grant_id': grant.id,
            'disbursement_amount': str(amount),
            'currency': grant.currency.code,
            'total_amount': str(grant.amount),
            'amount_received': str(grant.amount_received)
        }
    )

# Budget Notifications
def send_budget_notification(budget, notification_type, **kwargs):
    """Send budget-related notifications"""
    recipients = get_finance_notification_recipients('finance_managers')
    
    # Add budget creator and responsible persons
    if budget.created_by:
        recipients = list(recipients) + [budget.created_by]
    
    # Add responsible persons from budget items
    for item in budget.items.filter(responsible_person__isnull=False):
        recipients.append(item.responsible_person)
    
    # Remove duplicates
    recipients = list(set(recipients))
    
    if notification_type == 'approved':
        title = "Budget Approved"
        body = f"Budget '{budget.title}' for {budget.currency.code} {budget.total_amount:,.2f} has been approved"
        nt_name = 'budget_approved'
        priority = 'normal'
    elif notification_type == 'alert_80':
        title = "Budget Alert - 80% Used"
        body = f"Budget '{budget.title}' is 80% utilized. {budget.currency.code} {budget.remaining_amount:,.2f} remaining."
        nt_name = 'budget_alert_80'
        priority = 'normal'
    elif notification_type == 'alert_90':
        title = "Budget Alert - 90% Used"
        body = f"Budget '{budget.title}' is 90% utilized. Only {budget.currency.code} {budget.remaining_amount:,.2f} remaining!"
        nt_name = 'budget_alert_90'
        priority = 'high'
    elif notification_type == 'exceeded':
        overspent = budget.spent_amount - budget.total_amount
        title = "Budget Exceeded!"
        body = f"Budget '{budget.title}' has been exceeded by {budget.currency.code} {overspent:,.2f}"
        nt_name = 'budget_exceeded'
        priority = 'urgent'
    else:
        return
    
    create_notification(
        nt_name,
        recipients,
        title,
        body,
        related_object=budget,
        data={
            'budget_id': budget.id,
            'budget_title': budget.title,
            'total_amount': str(budget.total_amount),
            'spent_amount': str(budget.spent_amount),
            'remaining_amount': str(budget.remaining_amount),
            'spent_percentage': float(budget.spent_percentage),
            'currency': budget.currency.code
        },
        priority=priority
    )

# Expense Notifications
def send_expense_notification(expense, notification_type, approved_by=None):
    """Send expense-related notifications"""
    if notification_type == 'submitted':
        recipients = get_finance_notification_recipients('finance_managers')
        title = "New Expense Submitted"
        body = f"Expense '{expense.title}' for {expense.currency.code} {expense.amount:,.2f} submitted by {expense.submitted_by.get_full_name()}"
        nt_name = 'expense_submitted'
        priority = 'normal'
        
        # Check if it's a large expense
        if expense.amount >= Decimal('5000.00'):  # Configurable threshold
            create_notification(
                'large_expense_alert',
                recipients,
                "Large Expense Alert",
                f"Large expense of {expense.currency.code} {expense.amount:,.2f} submitted for '{expense.title}'",
                related_object=expense,
                data={
                    'expense_id': expense.id,
                    'amount': str(expense.amount),
                    'currency': expense.currency.code,
                    'submitted_by': expense.submitted_by.get_full_name()
                },
                priority='high'
            )
    
    elif notification_type == 'approved':
        recipients = [expense.submitted_by]
        title = "Expense Approved"
        body = f"Your expense '{expense.title}' for {expense.currency.code} {expense.amount:,.2f} has been approved"
        nt_name = 'expense_approved'
        priority = 'normal'
    
    elif notification_type == 'rejected':
        recipients = [expense.submitted_by]
        title = "Expense Rejected"
        body = f"Your expense '{expense.title}' for {expense.currency.code} {expense.amount:,.2f} has been rejected"
        nt_name = 'expense_rejected'
        priority = 'normal'
    
    else:
        return
    
    create_notification(
        nt_name,
        recipients,
        title,
        body,
        related_object=expense,
        data={
            'expense_id': expense.id,
            'expense_title': expense.title,
            'amount': str(expense.amount),
            'currency': expense.currency.code,
            'status': expense.status,
            'submitted_by': expense.submitted_by.get_full_name(),
            'approved_by': approved_by.get_full_name() if approved_by else None
        },
        priority=priority
    )

# Account & Transaction Notifications
def send_account_notification(account, notification_type, **kwargs):
    """Send account-related notifications"""
    recipients = get_finance_notification_recipients('accountants')
    
    # Add account signatories
    recipients = list(recipients) + [account.primary_signatory]
    recipients.extend(account.secondary_signatories.all())
    
    # Remove duplicates
    recipients = list(set(recipients))
    
    if notification_type == 'low_balance':
        threshold = kwargs.get('threshold', 1000)
        title = "Low Account Balance"
        body = f"Account '{account.name}' has a low balance: {account.currency.code} {account.current_balance:,.2f}"
        nt_name = 'account_low_balance'
        priority = 'high'
    
    elif notification_type == 'created':
        title = "New Bank Account Added"
        body = f"New {account.get_account_type_display()} account '{account.name}' has been added"
        nt_name = 'bank_account_created'
        priority = 'normal'
    
    else:
        return
    
    create_notification(
        nt_name,
        recipients,
        title,
        body,
        related_object=account,
        data={
            'account_id': account.id,
            'account_name': account.name,
            'account_type': account.account_type,
            'balance': str(account.current_balance),
            'currency': account.currency.code
        },
        priority=priority
    )

def send_transaction_notification(transaction, notification_type):
    """Send transaction-related notifications"""
    recipients = get_finance_notification_recipients('accountants')
    
    # Add account signatories
    recipients = list(recipients) + [transaction.account.primary_signatory]
    recipients.extend(transaction.account.secondary_signatories.all())
    
    # Remove duplicates
    recipients = list(set(recipients))
    
    if notification_type == 'large_transaction':
        title = "Large Transaction Alert"
        body = f"Large {transaction.get_transaction_type_display().lower()} of {transaction.account.currency.code} {transaction.amount:,.2f} in account '{transaction.account.name}'"
        nt_name = 'large_transaction'
        priority = 'normal'
    
    elif notification_type == 'failed':
        title = "Transaction Failed"
        body = f"Transaction of {transaction.account.currency.code} {transaction.amount:,.2f} failed in account '{transaction.account.name}'"
        nt_name = 'transaction_failed'
        priority = 'high'
    
    else:
        return
    
    create_notification(
        nt_name,
        recipients,
        title,
        body,
        related_object=transaction,
        data={
            'transaction_id': transaction.id,
            'account_id': transaction.account.id,
            'account_name': transaction.account.name,
            'amount': str(transaction.amount),
            'currency': transaction.account.currency.code,
            'transaction_type': transaction.transaction_type,
            'status': transaction.status
        },
        priority=priority
    )

def send_reconciliation_notification(account, unreconciled_count):
    """Send notification when account reconciliation is required"""
    recipients = get_finance_notification_recipients('accountants')
    
    title = "Account Reconciliation Required"
    body = f"Account '{account.name}' has {unreconciled_count} unreconciled transactions"
    
    create_notification(
        'reconciliation_required',
        recipients,
        title,
        body,
        related_object=account,
        data={
            'account_id': account.id,
            'account_name': account.name,
            'unreconciled_count': unreconciled_count,
            'currency': account.currency.code
        }
    )

def send_notification_email(user, notification):
    """Send email notification to user"""
    try:
        subject = f"[{getattr(settings, 'SITE_NAME', 'NGO Platform')}] {notification.title}"
        
        context = {
            'user': user,
            'notification': notification,
            'site_name': getattr(settings, 'SITE_NAME', 'NGO Platform'),
            'site_url': getattr(settings, 'SITE_URL', 'http://localhost:8000')
        }
        
        # Try to render custom template for notification type
        template_name = f'notifications/email/{notification.notification_type.name}.html'
        try:
            html_message = render_to_string(template_name, context)
        except:
            # Fall back to generic template
            html_message = render_to_string('notifications/email/generic.html', context)
        
        # Plain text version
        plain_message = f"""
        {notification.title}
        
        {notification.body}
        
        ---
        {getattr(settings, 'SITE_NAME', 'NGO Platform')}
        """
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=True
        )
        
        # Mark email as sent
        notification.is_email_sent = True
        notification.save(update_fields=['is_email_sent'])
        
    except Exception as e:
        logger.error(f"Failed to send email notification to {user.email}: {str(e)}")
