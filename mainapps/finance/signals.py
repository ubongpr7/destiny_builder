from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from .models import (
  Donation, RecurringDonation, InKindDonation, DonationCampaign,
  Grant, GrantReport, Budget, OrganizationalExpense, 
  BankAccount, AccountTransaction
)
from .api.notification_utils import (
  send_donation_received_notification,
  send_recurring_donation_notification,
  send_in_kind_donation_notification,
  send_campaign_milestone_notification,
  send_grant_status_notification,
  send_grant_report_due_notification,
  send_budget_notification,
  send_expense_notification,
  send_account_notification,
  send_transaction_notification
)

# Donation Signals
@receiver(post_save, sender=Donation)
def donation_created_handler(sender, instance, created, **kwargs):
  """Handle donation creation and status changes"""
  if created and instance.status == 'completed':
      send_donation_received_notification(instance)
      
      # Check campaign milestones
      if instance.campaign:
          campaign = instance.campaign
          progress = campaign.progress_percentage
          
          # Send milestone notifications at 25%, 50%, 75%, and 100%
          milestones = [25, 50, 75, 100]
          for milestone in milestones:
              if progress >= milestone:
                  # Check if we haven't already sent this milestone notification
                  # You might want to track this in the database
                  send_campaign_milestone_notification(campaign, milestone)
  
  elif not created and instance.status == 'completed':
      # Status changed to completed
      send_donation_received_notification(instance)

@receiver(post_save, sender=RecurringDonation)
def recurring_donation_handler(sender, instance, created, **kwargs):
  """Handle recurring donation events"""
  if created:
      send_recurring_donation_notification(instance, 'created')

@receiver(pre_save, sender=RecurringDonation)
def recurring_donation_status_change_handler(sender, instance, **kwargs):
  """Handle recurring donation status changes"""
  if instance.pk:
      try:
          old_instance = RecurringDonation.objects.get(pk=instance.pk)
          if old_instance.status != instance.status:
              if instance.status == 'cancelled':
                  send_recurring_donation_notification(instance, 'cancelled')
              elif instance.status == 'failed':
                  send_recurring_donation_notification(instance, 'payment_failed')
      except RecurringDonation.DoesNotExist:
          pass

@receiver(post_save, sender=InKindDonation)
def in_kind_donation_handler(sender, instance, created, **kwargs):
  """Handle in-kind donation creation"""
  if created and instance.status == 'received':
      send_in_kind_donation_notification(instance)

# Grant Signals
@receiver(pre_save, sender=Grant)
def grant_status_change_handler(sender, instance, **kwargs):
  """Handle grant status changes"""
  if instance.pk:
      try:
          old_instance = Grant.objects.get(pk=instance.pk)
          if old_instance.status != instance.status:
              send_grant_status_notification(instance, old_instance.status, instance.status)
      except Grant.DoesNotExist:
          pass

@receiver(post_save, sender=GrantReport)
def grant_report_due_handler(sender, instance, created, **kwargs):
  """Handle grant report due notifications"""
  if created and instance.due_date:
      # Send notification if due date is within 7 days
      days_until_due = (instance.due_date - timezone.now().date()).days
      if days_until_due <= 7:
          send_grant_report_due_notification(instance)

# Budget Signals
@receiver(pre_save, sender=Budget)
def budget_status_change_handler(sender, instance, **kwargs):
  """Handle budget status changes"""
  if instance.pk:
      try:
          old_instance = Budget.objects.get(pk=instance.pk)
          if old_instance.status != instance.status and instance.status == 'approved':
              send_budget_notification(instance, 'approved')
      except Budget.DoesNotExist:
          pass

@receiver(post_save, sender=Budget)
def budget_utilization_handler(sender, instance, **kwargs):
  """Handle budget utilization alerts"""
  if not kwargs.get('created', False):  # Only for updates
      spent_percentage = instance.spent_percentage
      
      if spent_percentage >= 100:
          send_budget_notification(instance, 'exceeded')
      elif spent_percentage >= 90:
          send_budget_notification(instance, 'alert_90')
      elif spent_percentage >= 80:
          send_budget_notification(instance, 'alert_80')

# Expense Signals
@receiver(post_save, sender=OrganizationalExpense)
def expense_handler(sender, instance, created, **kwargs):
  """Handle expense creation and status changes"""
  if created and instance.status == 'pending':
      send_expense_notification(instance, 'submitted')

@receiver(pre_save, sender=OrganizationalExpense)
def expense_status_change_handler(sender, instance, **kwargs):
  """Handle expense status changes"""
  if instance.pk:
      try:
          old_instance = OrganizationalExpense.objects.get(pk=instance.pk)
          if old_instance.status != instance.status:
              if instance.status == 'approved':
                  send_expense_notification(instance, 'approved', instance.approved_by)
              elif instance.status == 'rejected':
                  send_expense_notification(instance, 'rejected', instance.approved_by)
      except OrganizationalExpense.DoesNotExist:
          pass

# Account Signals
@receiver(post_save, sender=BankAccount)
def bank_account_created_handler(sender, instance, created, **kwargs):
  """Handle bank account creation"""
  if created:
      send_account_notification(instance, 'created')

@receiver(post_save, sender=AccountTransaction)
def transaction_handler(sender, instance, created, **kwargs):
  """Handle transaction events"""
  if created:
      # Check for large transactions (over $10,000 or equivalent)
      if instance.amount >= 10000:
          send_transaction_notification(instance, 'large_transaction')
      
      # Check account balance after transaction
      if instance.status == 'completed':
          balance = instance.account.current_balance
          # Send low balance alert if balance is below $1,000
          if balance < 1000:
              send_account_notification(instance.account, 'low_balance', threshold=1000)

@receiver(pre_save, sender=AccountTransaction)
def transaction_status_change_handler(sender, instance, **kwargs):
  """Handle transaction status changes"""
  if instance.pk:
      try:
          old_instance = AccountTransaction.objects.get(pk=instance.pk)
          if old_instance.status != instance.status and instance.status == 'failed':
              send_transaction_notification(instance, 'failed')
      except AccountTransaction.DoesNotExist:
          pass

@receiver(post_save, sender=AccountTransaction)
def account_transaction_created_notification(sender, instance, created, **kwargs):
    """Send notification to bank account signatories and superusers when transaction is created"""
    if created:
        send_transaction_notification(instance, 'created')
