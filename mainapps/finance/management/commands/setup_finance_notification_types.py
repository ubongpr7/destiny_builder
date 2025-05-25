from django.core.management.base import BaseCommand
from mainapps.notification.models import NotificationType, NotificationCategory

class Command(BaseCommand):
    help = 'Set up notification types for the enhanced finance app'

    def handle(self, *args, **options):
        notification_types = [
            # Donation Notifications
            {
                'name': 'donation_received',
                'description': 'Notification when a donation is received',
                'category': NotificationCategory.PAYMENT,
                'title_template': 'New Donation Received',
                'body_template': 'A donation of {currency} {amount} has been received{campaign_info}{donor_info}',
                'icon': 'heart',
                'color': 'success',
                'send_email': True,
                'send_push': True
            },
            {
                'name': 'large_donation_received',
                'description': 'Notification for large donations (over threshold)',
                'category': NotificationCategory.PAYMENT,
                'title_template': 'Large Donation Alert!',
                'body_template': 'A significant donation of {currency} {amount} has been received{campaign_info}',
                'icon': 'star',
                'color': 'warning',
                'send_email': True,
                'send_push': True,
                'default_priority': 'high'
            },
            {
                'name': 'recurring_donation_created',
                'description': 'Notification when recurring donation is set up',
                'category': NotificationCategory.PAYMENT,
                'title_template': 'New Recurring Donation',
                'body_template': 'A recurring donation of {currency} {amount} {frequency} has been set up',
                'icon': 'refresh',
                'color': 'info',
                'send_email': True
            },
            {
                'name': 'recurring_donation_cancelled',
                'description': 'Notification when recurring donation is cancelled',
                'category': NotificationCategory.PAYMENT,
                'title_template': 'Recurring Donation Cancelled',
                'body_template': 'A recurring donation of {currency} {amount} {frequency} has been cancelled',
                'icon': 'x-circle',
                'color': 'danger',
                'send_email': True
            },
            {
                'name': 'recurring_payment_failed',
                'description': 'Notification when recurring payment fails',
                'category': NotificationCategory.PAYMENT,
                'title_template': 'Recurring Payment Failed',
                'body_template': 'A recurring payment of {currency} {amount} has failed. Please check payment method.',
                'icon': 'alert-triangle',
                'color': 'danger',
                'send_email': True,
                'default_priority': 'high'
            },
            {
                'name': 'in_kind_donation_received',
                'description': 'Notification when in-kind donation is received',
                'category': NotificationCategory.OTHER,
                'title_template': 'In-Kind Donation Received',
                'body_template': 'An in-kind donation has been received: {item_description} (valued at {currency} {value})',
                'icon': 'gift',
                'color': 'success',
                'send_email': True
            },
            
            # Campaign Notifications
            {
                'name': 'campaign_milestone',
                'description': 'Notification when campaign reaches milestones',
                'category': NotificationCategory.PROJECT,
                'title_template': 'Campaign Milestone Reached!',
                'body_template': 'Campaign "{campaign_title}" has reached {milestone}% of its target!',
                'icon': 'target',
                'color': 'success',
                'send_email': True,
                'send_push': True
            },
            {
                'name': 'campaign_target_reached',
                'description': 'Notification when campaign reaches its target',
                'category': NotificationCategory.PROJECT,
                'title_template': 'Campaign Target Achieved!',
                'body_template': 'Congratulations! Campaign "{campaign_title}" has reached its target of {currency} {target_amount}!',
                'icon': 'trophy',
                'color': 'success',
                'send_email': True,
                'send_push': True,
                'default_priority': 'high'
            },
            {
                'name': 'campaign_ending_soon',
                'description': 'Notification when campaign is ending soon',
                'category': NotificationCategory.PROJECT,
                'title_template': 'Campaign Ending Soon',
                'body_template': 'Campaign "{campaign_title}" will end in {days_remaining} days',
                'icon': 'clock',
                'color': 'warning',
                'send_email': True
            },
            
            # Grant Notifications
            {
                'name': 'grant_status_change',
                'description': 'Notification when grant status changes',
                'category': NotificationCategory.PROJECT,
                'title_template': 'Grant Status Update',
                'body_template': 'Grant "{grant_title}" status changed from {old_status} to {new_status}',
                'icon': 'file-text',
                'color': 'info',
                'send_email': True
            },
            {
                'name': 'grant_approved',
                'description': 'Notification when grant is approved',
                'category': NotificationCategory.PROJECT,
                'title_template': 'Grant Approved!',
                'body_template': 'Great news! Grant "{grant_title}" for {currency} {amount} has been approved by {grantor}',
                'icon': 'check-circle',
                'color': 'success',
                'send_email': True,
                'send_push': True,
                'default_priority': 'high'
            },
            {
                'name': 'grant_report_due',
                'description': 'Notification when grant report is due',
                'category': NotificationCategory.DOCUMENT,
                'title_template': 'Grant Report Due',
                'body_template': 'Grant report for "{grant_title}" is due on {due_date}',
                'icon': 'calendar',
                'color': 'warning',
                'send_email': True,
                'default_priority': 'high'
            },
            {
                'name': 'grant_disbursement_received',
                'description': 'Notification when grant disbursement is received',
                'category': NotificationCategory.PAYMENT,
                'title_template': 'Grant Disbursement Received',
                'body_template': 'Grant disbursement of {currency} {amount} received for "{grant_title}"',
                'icon': 'dollar-sign',
                'color': 'success',
                'send_email': True
            },
            
            # Budget Notifications
            {
                'name': 'budget_approved',
                'description': 'Notification when budget is approved',
                'category': NotificationCategory.PROJECT,
                'title_template': 'Budget Approved',
                'body_template': 'Budget "{budget_title}" for {currency} {amount} has been approved',
                'icon': 'check',
                'color': 'success',
                'send_email': True
            },
            {
                'name': 'budget_alert_80',
                'description': 'Notification when budget reaches 80% utilization',
                'category': NotificationCategory.PROJECT,
                'title_template': 'Budget Alert - 80% Used',
                'body_template': 'Budget "{budget_title}" is 80% utilized. {currency} {remaining} remaining.',
                'icon': 'alert-triangle',
                'color': 'warning',
                'send_email': True
            },
            {
                'name': 'budget_alert_90',
                'description': 'Notification when budget reaches 90% utilization',
                'category': NotificationCategory.PROJECT,
                'title_template': 'Budget Alert - 90% Used',
                'body_template': 'Budget "{budget_title}" is 90% utilized. Only {currency} {remaining} remaining!',
                'icon': 'alert-triangle',
                'color': 'danger',
                'send_email': True,
                'default_priority': 'high'
            },
            {
                'name': 'budget_exceeded',
                'description': 'Notification when budget is exceeded',
                'category': NotificationCategory.PROJECT,
                'title_template': 'Budget Exceeded!',
                'body_template': 'Budget "{budget_title}" has been exceeded by {currency} {overspent_amount}',
                'icon': 'x-circle',
                'color': 'danger',
                'send_email': True,
                'send_push': True,
                'default_priority': 'urgent'
            },
            
            # Expense Notifications
            {
                'name': 'expense_submitted',
                'description': 'Notification when expense is submitted for approval',
                'category': NotificationCategory.EXPENSE,
                'title_template': 'New Expense Submitted',
                'body_template': 'Expense "{expense_title}" for {currency} {amount} submitted by {submitted_by}',
                'icon': 'file-plus',
                'color': 'info',
                'send_email': True
            },
            {
                'name': 'expense_approved',
                'description': 'Notification when expense is approved',
                'category': NotificationCategory.EXPENSE,
                'title_template': 'Expense Approved',
                'body_template': 'Your expense "{expense_title}" for {currency} {amount} has been approved',
                'icon': 'check-circle',
                'color': 'success',
                'send_email': True
            },
            {
                'name': 'expense_rejected',
                'description': 'Notification when expense is rejected',
                'category': NotificationCategory.EXPENSE,
                'title_template': 'Expense Rejected',
                'body_template': 'Your expense "{expense_title}" for {currency} {amount} has been rejected',
                'icon': 'x-circle',
                'color': 'danger',
                'send_email': True
            },
            {
                'name': 'large_expense_alert',
                'description': 'Notification for large expenses requiring special attention',
                'category': NotificationCategory.EXPENSE,
                'title_template': 'Large Expense Alert',
                'body_template': 'Large expense of {currency} {amount} submitted for "{expense_title}"',
                'icon': 'alert-circle',
                'color': 'warning',
                'send_email': True,
                'default_priority': 'high'
            },
            
            # Account & Transaction Notifications
            {
                'name': 'account_low_balance',
                'description': 'Notification when account balance is low',
                'category': NotificationCategory.PAYMENT,
                'title_template': 'Low Account Balance',
                'body_template': 'Account "{account_name}" has a low balance: {currency} {balance}',
                'icon': 'alert-triangle',
                'color': 'warning',
                'send_email': True,
                'default_priority': 'high'
            },
            {
                'name': 'large_transaction',
                'description': 'Notification for large transactions',
                'category': NotificationCategory.PAYMENT,
                'title_template': 'Large Transaction Alert',
                'body_template': 'Large {transaction_type} of {currency} {amount} in account "{account_name}"',
                'icon': 'dollar-sign',
                'color': 'info',
                'send_email': True
            },
            {
                'name': 'transaction_failed',
                'description': 'Notification when transaction fails',
                'category': NotificationCategory.PAYMENT,
                'title_template': 'Transaction Failed',
                'body_template': 'Transaction of {currency} {amount} failed in account "{account_name}"',
                'icon': 'x-circle',
                'color': 'danger',
                'send_email': True,
                'default_priority': 'high'
            },
            {
                'name': 'reconciliation_required',
                'description': 'Notification when account reconciliation is required',
                'category': NotificationCategory.SYSTEM,
                'title_template': 'Account Reconciliation Required',
                'body_template': 'Account "{account_name}" has {count} unreconciled transactions',
                'icon': 'list',
                'color': 'warning',
                'send_email': True
            },
            
            # Exchange Rate Notifications
            {
                'name': 'exchange_rate_alert',
                'description': 'Notification for significant exchange rate changes',
                'category': NotificationCategory.SYSTEM,
                'title_template': 'Exchange Rate Alert',
                'body_template': 'Significant change in {from_currency}/{to_currency} exchange rate: {old_rate} → {new_rate}',
                'icon': 'trending-up',
                'color': 'info',
                'send_email': True
            },
            
            # Financial Institution Notifications
            {
                'name': 'bank_account_created',
                'description': 'Notification when new bank account is added',
                'category': NotificationCategory.SYSTEM,
                'title_template': 'New Bank Account Added',
                'body_template': 'New {account_type} account "{account_name}" has been added',
                'icon': 'plus-circle',
                'color': 'success',
                'send_email': True
            },
        ]

        created_count = 0
        updated_count = 0

        for nt_data in notification_types:
            notification_type, created = NotificationType.objects.get_or_create(
                name=nt_data['name'],
                defaults={
                    'description': nt_data['description'],
                    'category': nt_data['category'],
                    'title_template': nt_data['title_template'],
                    'body_template': nt_data['body_template'],
                    'icon': nt_data.get('icon', 'bell'),
                    'color': nt_data.get('color', 'primary'),
                    'default_priority': nt_data.get('default_priority', 'normal'),
                    'send_email': nt_data.get('send_email', False),
                    'send_sms': nt_data.get('send_sms', False),
                    'send_push': nt_data.get('send_push', False),
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Created notification type: {notification_type.name}')
                )
            else:
                # Update existing notification type
                for field, value in nt_data.items():
                    if field != 'name' and hasattr(notification_type, field):
                        setattr(notification_type, field, value)
                notification_type.save()
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'↻ Updated notification type: {notification_type.name}')
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n🎉 Finance notification types setup completed!\n'
                f'Created: {created_count} | Updated: {updated_count}'
            )
        )
