"""
Utility functions for sending notifications in the project management system.
This centralizes all notification creation to ensure consistency and proper preference checking.
"""

from django.contrib.auth import get_user_model
from django.utils import timezone
from mainapps.notification.models import Notification, NotificationType, NotificationPreference
from mainapps.notification.services import NotificationService

User = get_user_model()

# Project URL paths (hardcoded for Next.js frontend compatibility)
PROJECT_DETAIL_URL = "/dashboard/projects/{project_id}"
PROJECT_MILESTONE_URL = "/dashboard/projects/{project_id}/milestones/{milestone_id}"
PROJECT_EXPENSE_URL = "/dashboard/projects/{project_id}"
PROJECT_UPDATE_URL = "/dashboard/projects/{project_id}"
SETTINGS_NOTIFICATIONS_URL = "/settings/notifications"

def should_notify_user(user, notification_type_name, channel='in_app'):
    """
    Check if a user should receive a notification based on their preferences.
    
    Args:
        user: The user to check
        notification_type_name: The name of the notification type
        channel: The notification channel ('in_app', 'email', 'push')
        
    Returns:
        Boolean indicating if the user should be notified
    """
    try:
        notification_type = NotificationType.objects.get(name=notification_type_name)
        
        # If notification type cannot be disabled, always send it
        if not notification_type.can_disable:
            return True
            
        # Check user preference
        try:
            preference = NotificationPreference.objects.get(
                user=user,
                notification_type=notification_type
            )
            
            # Check the appropriate channel preference
            if channel == 'in_app':
                return preference.receive_in_app
            elif channel == 'email':
                return preference.receive_email
            elif channel == 'push':
                return preference.receive_push
            else:
                return True
                
        except NotificationPreference.DoesNotExist:
            # If no preference exists, use the default from notification type
            if channel == 'in_app':
                return True  # In-app notifications are always on by default
            elif channel == 'email':
                return notification_type.send_email
            elif channel == 'push':
                return notification_type.send_push
            else:
                return True
                
    except NotificationType.DoesNotExist:
        # If notification type doesn't exist, don't send notification
        return False

def notify_project_created(project):
    """Send notification when a new project is created"""
    # Notify admins and executives
    admins_and_executives = User.objects.filter(
        profile__isnull=False,
        profile__is_active=True
    ).filter(
        profile__is_DB_admin=True
    ) | User.objects.filter(
        profile__isnull=False,
        profile__is_active=True,
        profile__is_DB_executive=True
    )
    
    for user in admins_and_executives:
        if should_notify_user(user, 'project_created', 'in_app'):
            NotificationService.create_notification(
                recipient=user,
                notification_type_name='project_created',
                context_data={
                    'project_title': project.title,
                    'project_type': project.get_project_type_display(),
                    'created_by': project.created_by.get_full_name() or project.created_by.username,
                },
                action_url=PROJECT_DETAIL_URL.format(project_id=project.id),
                priority='normal',
                icon='file-plus',
                color='#4CAF50',
                send_email=should_notify_user(user, 'project_created', 'email')
            )
    
    # Also notify the creator for confirmation
    if project.created_by and should_notify_user(project.created_by, 'project_created', 'in_app'):
        NotificationService.create_notification(
            recipient=project.created_by,
            notification_type_name='project_created',
            context_data={
                'project_title': project.title,
                'project_type': project.get_project_type_display(),
            },
            action_url=PROJECT_DETAIL_URL.format(project_id=project.id),
            priority='normal',
            icon='file-plus',
            color='#4CAF50',
            send_email=should_notify_user(project.created_by, 'project_created', 'email')
        )

def notify_project_status_changed(project, old_status, new_status, changed_by):
    """Send notification when a project's status changes"""
    # Determine who should be notified
    recipients = set()
    
    # Always notify the project manager
    if project.manager:
        recipients.add(project.manager)
    
    # Notify team members
    for team_member in project.team_members.all():
        recipients.add(team_member.user)
    
    # Notify officials
    for official in project.officials.all():
        recipients.add(official)
    
    # Notify admins and executives for important status changes
    important_transitions = [
        ('submitted', 'approved'),
        ('planning', 'active'),
        ('active', 'completed'),
        ('active', 'on_hold'),
        ('on_hold', 'active'),
        ('submitted', 'rejected'),
    ]
    
    if (old_status, new_status) in important_transitions:
        admins_and_executives = User.objects.filter(
            profile__isnull=False,
            profile__is_active=True
        ).filter(
            profile__is_DB_admin=True
        ) | User.objects.filter(
            profile__isnull=False,
            profile__is_active=True,
            profile__is_DB_executive=True
        )
        
        for user in admins_and_executives:
            recipients.add(user)
    
    # Send notifications
    notification_type = 'project_status_changed'
    
    # Determine priority based on the transition
    priority = 'normal'
    if new_status in ['completed', 'cancelled']:
        priority = 'high'
    elif new_status in ['on_hold', 'rejected']:
        priority = 'high'
    
    # Determine icon based on new status
    icon_map = {
        'planning': 'edit-3',
        'submitted': 'send',
        'approved': 'check-circle',
        'active': 'play-circle',
        'on_hold': 'pause-circle',
        'completed': 'check-square',
        'cancelled': 'x-circle',
        'rejected': 'x-circle'
    }
    icon = icon_map.get(new_status, 'activity')
    
    # Determine color based on new status
    color_map = {
        'planning': '#2196F3',  # Blue
        'submitted': '#FF9800',  # Orange
        'approved': '#4CAF50',  # Green
        'active': '#4CAF50',    # Green
        'on_hold': '#FFC107',   # Amber
        'completed': '#4CAF50', # Green
        'cancelled': '#F44336', # Red
        'rejected': '#F44336'   # Red
    }
    color = color_map.get(new_status, '#2196F3')
    
    for recipient in recipients:
        if should_notify_user(recipient, notification_type, 'in_app'):
            NotificationService.create_notification(
                recipient=recipient,
                notification_type_name=notification_type,
                context_data={
                    'project_title': project.title,
                    'old_status': dict(project.STATUS_CHOICES).get(old_status, old_status),
                    'new_status': dict(project.STATUS_CHOICES).get(new_status, new_status),
                    'changed_by': changed_by.get_full_name() or changed_by.username,
                },
                action_url=PROJECT_DETAIL_URL.format(project_id=project.id),
                priority=priority,
                icon=icon,
                color=color,
                send_email=should_notify_user(recipient, notification_type, 'email')
            )

def notify_team_member_added(team_member):
    """Send notification when a user is added to a project team"""
    project = team_member.project
    user = team_member.user
    
    # Notify the user who was added
    if should_notify_user(user, 'team_member_added', 'in_app'):
        NotificationService.create_notification(
            recipient=user,
            notification_type_name='team_member_added',
            context_data={
                'project_title': project.title,
                'role': dict(team_member.ROLE_CHOICES).get(team_member.role, team_member.role),
            },
            action_url=PROJECT_DETAIL_URL.format(project_id=project.id),
            priority='normal',
            icon='users',
            color='#2196F3',
            send_email=should_notify_user(user, 'team_member_added', 'email')
        )
    
    # Notify the project manager
    if project.manager and project.manager != user and should_notify_user(project.manager, 'team_member_added', 'in_app'):
        NotificationService.create_notification(
            recipient=project.manager,
            notification_type_name='team_member_added',
            context_data={
                'project_title': project.title,
                'user_name': user.get_full_name() or user.username,
                'role': dict(team_member.ROLE_CHOICES).get(team_member.role, team_member.role),
            },
            action_url=PROJECT_DETAIL_URL.format(project_id=project.id),
            priority='normal',
            icon='user-plus',
            color='#2196F3',
            send_email=should_notify_user(project.manager, 'team_member_added', 'email')
        )

def notify_team_member_removed(project, user, role):
    """Send notification when a user is removed from a project team"""
    # Notify the user who was removed
    if should_notify_user(user, 'team_member_removed', 'in_app'):
        NotificationService.create_notification(
            recipient=user,
            notification_type_name='team_member_removed',
            context_data={
                'project_title': project.title,
                'role': role,
            },
            action_url=PROJECT_DETAIL_URL.format(project_id=project.id),
            priority='normal',
            icon='user-minus',
            color='#FF9800',
            send_email=should_notify_user(user, 'team_member_removed', 'email')
        )
    
    # Notify the project manager
    if project.manager and project.manager != user and should_notify_user(project.manager, 'team_member_removed', 'in_app'):
        NotificationService.create_notification(
            recipient=project.manager,
            notification_type_name='team_member_removed',
            context_data={
                'project_title': project.title,
                'user_name': user.get_full_name() or user.username,
                'role': role,
            },
            action_url=PROJECT_DETAIL_URL.format(project_id=project.id),
            priority='normal',
            icon='user-minus',
            color='#FF9800',
            send_email=should_notify_user(project.manager, 'team_member_removed', 'email')
        )

def notify_milestone_created(milestone):
    """Send notification when a new milestone is created"""
    project = milestone.project
    
    # Notify the project manager
    if project.manager and should_notify_user(project.manager, 'milestone_created', 'in_app'):
        NotificationService.create_notification(
            recipient=project.manager,
            notification_type_name='milestone_created',
            context_data={
                'project_title': project.title,
                'milestone_title': milestone.title,
                'due_date': milestone.due_date.strftime('%Y-%m-%d'),
                'created_by': milestone.created_by.get_full_name() or milestone.created_by.username if milestone.created_by else 'System',
            },
            action_url=PROJECT_MILESTONE_URL.format(project_id=project.id, milestone_id=milestone.id),
            priority='normal',
            icon='flag',
            color='#2196F3',
            send_email=should_notify_user(project.manager, 'milestone_created', 'email')
        )
    
    # Notify assigned users
    for user in milestone.assigned_to.all():
        if should_notify_user(user, 'milestone_assigned', 'in_app'):
            NotificationService.create_notification(
                recipient=user,
                notification_type_name='milestone_assigned',
                context_data={
                    'project_title': project.title,
                    'milestone_title': milestone.title,
                    'due_date': milestone.due_date.strftime('%Y-%m-%d'),
                },
                action_url=PROJECT_MILESTONE_URL.format(project_id=project.id, milestone_id=milestone.id),
                priority='normal',
                icon='flag',
                color='#2196F3',
                send_email=should_notify_user(user, 'milestone_assigned', 'email')
            )

def notify_milestone_assigned(milestone, user):
    """Send notification when a user is assigned to a milestone"""
    project = milestone.project
    
    # Notify the assigned user
    if should_notify_user(user, 'milestone_assigned', 'in_app'):
        NotificationService.create_notification(
            recipient=user,
            notification_type_name='milestone_assigned',
            context_data={
                'project_title': project.title,
                'milestone_title': milestone.title,
                'due_date': milestone.due_date.strftime('%Y-%m-%d'),
            },
            action_url=PROJECT_MILESTONE_URL.format(project_id=project.id, milestone_id=milestone.id),
            priority='normal',
            icon='flag',
            color='#2196F3',
            send_email=should_notify_user(user, 'milestone_assigned', 'email')
        )

def notify_milestone_unassigned(milestone, user):
    """Send notification when a user is unassigned from a milestone"""
    project = milestone.project
    
    # Notify the unassigned user
    if should_notify_user(user, 'milestone_unassigned', 'in_app'):
        NotificationService.create_notification(
            recipient=user,
            notification_type_name='milestone_unassigned',
            context_data={
                'project_title': project.title,
                'milestone_title': milestone.title,
            },
            action_url=PROJECT_DETAIL_URL.format(project_id=project.id),
            priority='normal',
            icon='flag',
            color='#FF9800',
            send_email=should_notify_user(user, 'milestone_unassigned', 'email')
        )

def notify_milestone_status_changed(milestone, old_status, new_status, changed_by):
    """Send notification when a milestone's status changes"""
    project = milestone.project
    
    # Determine who should be notified
    recipients = set()
    
    # Always notify the project manager
    if project.manager:
        recipients.add(project.manager)
    
    # Notify assigned users
    for user in milestone.assigned_to.all():
        recipients.add(user)
    
    # Send notifications
    notification_type = 'milestone_status_changed'
    
    # Determine priority based on the transition
    priority = 'normal'
    if new_status == 'completed':
        priority = 'normal'
    elif new_status == 'delayed':
        priority = 'high'
    
    # Determine icon based on new status
    icon_map = {
        'pending': 'clock',
        'in_progress': 'play-circle',
        'completed': 'check-square',
        'delayed': 'alert-triangle',
        'cancelled': 'x-circle'
    }
    icon = icon_map.get(new_status, 'flag')
    
    # Determine color based on new status
    color_map = {
        'pending': '#2196F3',    # Blue
        'in_progress': '#4CAF50', # Green
        'completed': '#4CAF50',   # Green
        'delayed': '#FF9800',     # Orange
        'cancelled': '#F44336'    # Red
    }
    color = color_map.get(new_status, '#2196F3')
    
    for recipient in recipients:
        if should_notify_user(recipient, notification_type, 'in_app'):
            NotificationService.create_notification(
                recipient=recipient,
                notification_type_name=notification_type,
                context_data={
                    'project_title': project.title,
                    'milestone_title': milestone.title,
                    'old_status': dict(milestone.STATUS_CHOICES).get(old_status, old_status),
                    'new_status': dict(milestone.STATUS_CHOICES).get(new_status, new_status),
                    'changed_by': changed_by.get_full_name() or changed_by.username,
                },
                action_url=PROJECT_MILESTONE_URL.format(project_id=project.id, milestone_id=milestone.id),
                priority=priority,
                icon=icon,
                color=color,
                send_email=should_notify_user(recipient, notification_type, 'email')
            )

def notify_milestone_completed(milestone, completed_by):
    """Send notification when a milestone is completed"""
    project = milestone.project
    
    # Determine who should be notified
    recipients = set()
    
    # Always notify the project manager
    if project.manager:
        recipients.add(project.manager)
    
    # Notify team members
    for team_member in project.team_members.all():
        recipients.add(team_member.user)
    
    # Send notifications
    notification_type = 'milestone_completed'
    
    for recipient in recipients:
        if should_notify_user(recipient, notification_type, 'in_app'):
            NotificationService.create_notification(
                recipient=recipient,
                notification_type_name=notification_type,
                context_data={
                    'project_title': project.title,
                    'milestone_title': milestone.title,
                    'completed_by': completed_by.get_full_name() or completed_by.username,
                    'completion_date': milestone.completion_date.strftime('%Y-%m-%d') if milestone.completion_date else timezone.now().date().strftime('%Y-%m-%d'),
                },
                action_url=PROJECT_MILESTONE_URL.format(project_id=project.id, milestone_id=milestone.id),
                priority='normal',
                icon='check-square',
                color='#4CAF50',
                send_email=should_notify_user(recipient, notification_type, 'email')
            )

def notify_milestone_approaching(milestone, days_remaining):
    """Send notification when a milestone due date is approaching"""
    project = milestone.project
    
    # Determine who should be notified
    recipients = set()
    
    # Always notify the project manager
    if project.manager:
        recipients.add(project.manager)
    
    # Notify assigned users
    for user in milestone.assigned_to.all():
        recipients.add(user)
    
    # Send notifications
    notification_type = 'milestone_approaching'
    
    # Determine priority based on days remaining
    priority = 'normal'
    if days_remaining <= 1:
        priority = 'high'
    elif days_remaining <= 3:
        priority = 'normal'
    
    for recipient in recipients:
        if should_notify_user(recipient, notification_type, 'in_app'):
            NotificationService.create_notification(
                recipient=recipient,
                notification_type_name=notification_type,
                context_data={
                    'project_title': project.title,
                    'milestone_title': milestone.title,
                    'due_date': milestone.due_date.strftime('%Y-%m-%d'),
                    'days_remaining': days_remaining,
                },
                action_url=PROJECT_MILESTONE_URL.format(project_id=project.id, milestone_id=milestone.id),
                priority=priority,
                icon='clock',
                color='#FF9800',
                send_email=should_notify_user(recipient, notification_type, 'email')
            )

def notify_milestone_overdue(milestone):
    """Send notification when a milestone is overdue"""
    project = milestone.project
    
    # Determine who should be notified
    recipients = set()
    
    # Always notify the project manager
    if project.manager:
        recipients.add(project.manager)
    
    # Notify assigned users
    for user in milestone.assigned_to.all():
        recipients.add(user)
    
    # Send notifications
    notification_type = 'milestone_overdue'
    
    for recipient in recipients:
        if should_notify_user(recipient, notification_type, 'in_app'):
            NotificationService.create_notification(
                recipient=recipient,
                notification_type_name=notification_type,
                context_data={
                    'project_title': project.title,
                    'milestone_title': milestone.title,
                    'due_date': milestone.due_date.strftime('%Y-%m-%d'),
                    'days_overdue': (timezone.now().date() - milestone.due_date).days,
                },
                action_url=PROJECT_MILESTONE_URL.format(project_id=project.id, milestone_id=milestone.id),
                priority='high',
                icon='alert-circle',
                color='#F44336',
                send_email=should_notify_user(recipient, notification_type, 'email')
            )

def notify_expense_created(expense):
    """Send notification when a new expense is created"""
    project = expense.project
    
    # Notify admins and executives
    admins_and_executives = User.objects.filter(
        profile__isnull=False,
        profile__is_active=True
    ).filter(
        profile__is_DB_admin=True
    ) | User.objects.filter(
        profile__isnull=False,
        profile__is_active=True,
        profile__is_DB_executive=True
    )
    
    for user in admins_and_executives:
        if should_notify_user(user, 'expense_created', 'in_app'):
            NotificationService.create_notification(
                recipient=user,
                notification_type_name='expense_created',
                context_data={
                    'project_title': project.title,
                    'expense_title': expense.title,
                    'amount': str(expense.amount),
                    'created_by': expense.incurred_by.get_full_name() or expense.incurred_by.username,
                },
                action_url=PROJECT_EXPENSE_URL.format(project_id=project.id),
                priority='normal',
                icon='credit-card',
                color='#2196F3',
                send_email=should_notify_user(user, 'expense_created', 'email')
            )
    
    # Notify the project manager
    if project.manager and project.manager != expense.incurred_by and should_notify_user(project.manager, 'expense_created', 'in_app'):
        NotificationService.create_notification(
            recipient=project.manager,
            notification_type_name='expense_created',
            context_data={
                'project_title': project.title,
                'expense_title': expense.title,
                'amount': str(expense.amount),
                'created_by': expense.incurred_by.get_full_name() or expense.incurred_by.username,
            },
            action_url=PROJECT_EXPENSE_URL.format(project_id=project.id),
            priority='normal',
            icon='credit-card',
            color='#2196F3',
            send_email=should_notify_user(project.manager, 'expense_created', 'email')
        )
    
    # Notify team members
    for team_member in project.team_members.all():
        if team_member.user != expense.incurred_by and team_member.user != project.manager and should_notify_user(team_member.user, 'expense_created', 'in_app'):
            NotificationService.create_notification(
                recipient=team_member.user,
                notification_type_name='expense_created',
                context_data={
                    'project_title': project.title,
                    'expense_title': expense.title,
                    'amount': str(expense.amount),
                    'created_by': expense.incurred_by.get_full_name() or expense.incurred_by.username,
                },
                action_url=PROJECT_EXPENSE_URL.format(project_id=project.id),
                priority='normal',
                icon='credit-card',
                color='#2196F3',
                send_email=should_notify_user(team_member.user, 'expense_created', 'email')
            )

def notify_expense_status_changed(expense, old_status, new_status, changed_by):
    """Send notification when an expense's status changes"""
    project = expense.project
    
    # Determine who should be notified
    recipients = set()
    
    # Always notify the person who incurred the expense
    recipients.add(expense.incurred_by)
    
    # Notify the project manager
    if project.manager:
        recipients.add(project.manager)
    
    # For approved or rejected expenses, notify admins and executives
    if new_status in ['approved', 'rejected', 'reimbursed']:
        admins_and_executives = User.objects.filter(
            profile__isnull=False,
            profile__is_active=True
        ).filter(
            profile__is_DB_admin=True
        ) | User.objects.filter(
            profile__isnull=False,
            profile__is_active=True,
            profile__is_DB_executive=True
        )
        
        for user in admins_and_executives:
            recipients.add(user)
    
    # Send notifications
    notification_type = 'expense_status_changed'
    
    # Determine priority based on the transition
    priority = 'normal'
    if new_status == 'rejected':
        priority = 'high'
    elif new_status == 'approved':
        priority = 'normal'
    elif new_status == 'reimbursed':
        priority = 'normal'
    
    # Determine icon based on new status
    icon_map = {
        'pending': 'clock',
        'approved': 'check-circle',
        'rejected': 'x-circle',
        'reimbursed': 'dollar-sign'
    }
    icon = icon_map.get(new_status, 'credit-card')
    
    # Determine color based on new status
    color_map = {
        'pending': '#2196F3',    # Blue
        'approved': '#4CAF50',   # Green
        'rejected': '#F44336',   # Red
        'reimbursed': '#4CAF50'  # Green
    }
    color = color_map.get(new_status, '#2196F3')
    
    for recipient in recipients:
        if should_notify_user(recipient, notification_type, 'in_app'):
            NotificationService.create_notification(
                recipient=recipient,
                notification_type_name=notification_type,
                context_data={
                    'project_title': project.title,
                    'expense_title': expense.title,
                    'amount': str(expense.amount),
                    'old_status': dict(expense.STATUS_CHOICES).get(old_status, old_status),
                    'new_status': dict(expense.STATUS_CHOICES).get(new_status, new_status),
                    'changed_by': changed_by.get_full_name() or changed_by.username,
                },
                action_url=PROJECT_EXPENSE_URL.format(project_id=project.id),
                priority=priority,
                icon=icon,
                color=color,
                send_email=should_notify_user(recipient, notification_type, 'email')
            )

def notify_update_created(update):
    """Send notification when a new project update is created"""
    project = update.project
    
    # Determine who should be notified
    recipients = set()
    
    # Notify the project manager
    if project.manager and project.manager != update.submitted_by:
        recipients.add(project.manager)
    
    # Notify team members
    for team_member in project.team_members.all():
        if team_member.user != update.submitted_by:
            recipients.add(team_member.user)
    
    # Notify officials
    for official in project.officials.all():
        if official != update.submitted_by:
            recipients.add(official)
    
    # Send notifications
    notification_type = 'update_created'
    
    for recipient in recipients:
        if should_notify_user(recipient, notification_type, 'in_app'):
            NotificationService.create_notification(
                recipient=recipient,
                notification_type_name=notification_type,
                context_data={
                    'project_title': project.title,
                    'update_date': update.date.strftime('%Y-%m-%d'),
                    'submitted_by': update.submitted_by.get_full_name() or update.submitted_by.username,
                },
                action_url=PROJECT_UPDATE_URL.format(project_id=project.id),
                priority='normal',
                icon='file-text',
                color='#2196F3',
                send_email=should_notify_user(recipient, notification_type, 'email')
            )

def notify_project_approaching_end(project, days_remaining):
    """Send notification when a project's end date is approaching"""
    # Determine who should be notified
    recipients = set()
    
    # Notify the project manager
    if project.manager:
        recipients.add(project.manager)
    
    # Notify team members
    for team_member in project.team_members.all():
        recipients.add(team_member.user)
    
    # Notify officials
    for official in project.officials.all():
        recipients.add(official)
    
    # Send notifications
    notification_type = 'project_approaching_end'
    
    # Determine priority based on days remaining
    priority = 'normal'
    if days_remaining <= 3:
        priority = 'high'
    elif days_remaining <= 7:
        priority = 'normal'
    
    for recipient in recipients:
        if should_notify_user(recipient, notification_type, 'in_app'):
            NotificationService.create_notification(
                recipient=recipient,
                notification_type_name=notification_type,
                context_data={
                    'project_title': project.title,
                    'end_date': project.target_end_date.strftime('%Y-%m-%d'),
                    'days_remaining': days_remaining,
                },
                action_url=PROJECT_DETAIL_URL.format(project_id=project.id),
                priority=priority,
                icon='clock',
                color='#FF9800',
                send_email=should_notify_user(recipient, notification_type, 'email')
            )

def notify_project_overbudget(project, current_spent, budget):
    """Send notification when a project exceeds its budget"""
    # Notify admins and executives
    admins_and_executives = User.objects.filter(
        profile__isnull=False,
        profile__is_active=True
    ).filter(
        profile__is_DB_admin=True
    ) | User.objects.filter(
        profile__isnull=False,
        profile__is_active=True,
        profile__is_DB_executive=True
    )
    
    for user in admins_and_executives:
        if should_notify_user(user, 'project_overbudget', 'in_app'):
            NotificationService.create_notification(
                recipient=user,
                notification_type_name='project_overbudget',
                context_data={
                    'project_title': project.title,
                    'budget': str(budget),
                    'current_spent': str(current_spent),
                    'overage': str(current_spent - budget),
                },
                action_url=PROJECT_DETAIL_URL.format(project_id=project.id),
                priority='high',
                icon='alert-triangle',
                color='#F44336',
                send_email=should_notify_user(user, 'project_overbudget', 'email')
            )
    
    # Notify the project manager
    if project.manager and should_notify_user(project.manager, 'project_overbudget', 'in_app'):
        NotificationService.create_notification(
            recipient=project.manager,
            notification_type_name='project_overbudget',
            context_data={
                'project_title': project.title,
                'budget': str(budget),
                'current_spent': str(current_spent),
                'overage': str(current_spent - budget),
            },
            action_url=PROJECT_DETAIL_URL.format(project_id=project.id),
            priority='high',
            icon='alert-triangle',
            color='#F44336',
            send_email=should_notify_user(project.manager, 'project_overbudget', 'email')
        )

def notify_project_budget_updated(project, old_budget, new_budget, updated_by):
    """Send notification when a project's budget is updated"""
    # Determine who should be notified
    recipients = set()
    
    # Notify the project manager
    if project.manager:
        recipients.add(project.manager)
    
    # Notify admins and executives
    admins_and_executives = User.objects.filter(
        profile__isnull=False,
        profile__is_active=True
    ).filter(
        profile__is_DB_admin=True
    ) | User.objects.filter(
        profile__isnull=False,
        profile__is_active=True,
        profile__is_DB_executive=True
    )
    
    for user in admins_and_executives:
        recipients.add(user)
    
    # Send notifications
    notification_type = 'project_budget_updated'
    
    for recipient in recipients:
        if should_notify_user(recipient, notification_type, 'in_app'):
            NotificationService.create_notification(
                recipient=recipient,
                notification_type_name=notification_type,
                context_data={
                    'project_title': project.title,
                    'old_budget': str(old_budget),
                    'new_budget': str(new_budget),
                    'updated_by': updated_by.get_full_name() or updated_by.username,
                },
                action_url=PROJECT_DETAIL_URL.format(project_id=project.id),
                priority='normal',
                icon='dollar-sign',
                color='#2196F3',
                send_email=should_notify_user(recipient, notification_type, 'email')
            )

def notify_project_dates_updated(project, field_changed, old_date, new_date, updated_by):
    """Send notification when a project's dates are updated"""
    # Determine who should be notified
    recipients = set()
    
    # Notify the project manager
    if project.manager:
        recipients.add(project.manager)
    
    # Notify team members
    for team_member in project.team_members.all():
        recipients.add(team_member.user)
    
    # Notify officials
    for official in project.officials.all():
        recipients.add(official)
    
    # Send notifications
    notification_type = 'project_dates_updated'
    
    for recipient in recipients:
        if should_notify_user(recipient, notification_type, 'in_app'):
            NotificationService.create_notification(
                recipient=recipient,
                notification_type_name=notification_type,
                context_data={
                    'project_title': project.title,
                    'field_changed': field_changed,
                    'old_date': old_date.strftime('%Y-%m-%d') if old_date else 'Not set',
                    'new_date': new_date.strftime('%Y-%m-%d') if new_date else 'Not set',
                    'updated_by': updated_by.get_full_name() or updated_by.username,
                },
                action_url=PROJECT_DETAIL_URL.format(project_id=project.id),
                priority='normal',
                icon='calendar',
                color='#2196F3',
                send_email=should_notify_user(recipient, notification_type, 'email')
            )

def notify_official_added(project, user, added_by):
    """Send notification when an official is added to a project"""
    # Notify the official who was added
    if should_notify_user(user, 'official_added', 'in_app'):
        NotificationService.create_notification(
            recipient=user,
            notification_type_name='official_added',
            context_data={
                'project_title': project.title,
                'added_by': added_by.get_full_name() or added_by.username,
            },
            action_url=PROJECT_DETAIL_URL.format(project_id=project.id),
            priority='normal',
            icon='user-plus',
            color='#2196F3',
            send_email=should_notify_user(user, 'official_added', 'email')
        )
    
    # Notify the project manager
    if project.manager and project.manager != added_by and project.manager != user and should_notify_user(project.manager, 'official_added', 'in_app'):
        NotificationService.create_notification(
            recipient=project.manager,
            notification_type_name='official_added',
            context_data={
                'project_title': project.title,
                'official_name': user.get_full_name() or user.username,
                'added_by': added_by.get_full_name() or added_by.username,
            },
            action_url=PROJECT_DETAIL_URL.format(project_id=project.id),
            priority='normal',
            icon='user-plus',
            color='#2196F3',
            send_email=should_notify_user(project.manager, 'official_added', 'email')
        )

def notify_official_removed(project, user, removed_by):
    """Send notification when an official is removed from a project"""
    # Notify the official who was removed
    if should_notify_user(user, 'official_removed', 'in_app'):
        NotificationService.create_notification(
            recipient=user,
            notification_type_name='official_removed',
            context_data={
                'project_title': project.title,
                'removed_by': removed_by.get_full_name() or removed_by.username,
            },
            action_url=PROJECT_DETAIL_URL.format(project_id=project.id),
            priority='normal',
            icon='user-minus',
            color='#FF9800',
            send_email=should_notify_user(user, 'official_removed', 'email')
        )
    
    # Notify the project manager
    if project.manager and project.manager != removed_by and project.manager != user and should_notify_user(project.manager, 'official_removed', 'in_app'):
        NotificationService.create_notification(
            recipient=project.manager,
            notification_type_name='official_removed',
            context_data={
                'project_title': project.title,
                'official_name': user.get_full_name() or user.username,
                'removed_by': removed_by.get_full_name() or removed_by.username,
            },
            action_url=PROJECT_DETAIL_URL.format(project_id=project.id),
            priority='normal',
            icon='user-minus',
            color='#FF9800',
            send_email=should_notify_user(project.manager, 'official_removed', 'email')
        )

def notify_media_uploaded(media_obj, media_type, related_obj_type, related_obj):
    """Send notification when media is uploaded to a project or milestone"""
    # Determine project based on related object type
    project = None
    action_url = None
    
    if related_obj_type == 'project':
        project = related_obj
        action_url = PROJECT_DETAIL_URL.format(project_id=project.id)
    elif related_obj_type == 'milestone':
        project = related_obj.project
        action_url = PROJECT_MILESTONE_URL.format(project_id=project.id, milestone_id=related_obj.id)
    elif related_obj_type == 'update':
        project = related_obj.project
        action_url = PROJECT_UPDATE_URL.format(project_id=project.id)
    else:
        return  # Unsupported related object type
    
    # Determine who should be notified
    recipients = set()
    
    # Notify the project manager
    if project.manager and project.manager != media_obj.uploaded_by:
        recipients.add(project.manager)
    
    # For milestone media, notify assigned users
    if related_obj_type == 'milestone':
        for user in related_obj.assigned_to.all():
            if user != media_obj.uploaded_by:
                recipients.add(user)
    
    # Send notifications
    notification_type = 'media_uploaded'
    
    # Determine icon based on media type
    icon_map = {
        'image': 'image',
        'video': 'video',
        'document': 'file-text',
        'audio': 'music',
        'blueprint': 'layers',
        'contract': 'file-text',
        'diagram': 'bar-chart-2',
        'report': 'clipboard'
    }
    icon = icon_map.get(media_obj.media_type, 'file')
    
    for recipient in recipients:
        if should_notify_user(recipient, notification_type, 'in_app'):
            NotificationService.create_notification(
                recipient=recipient,
                notification_type_name=notification_type,
                context_data={
                    'project_title': project.title,
                    'media_type': dict(media_obj.MEDIA_TYPE_CHOICES).get(media_obj.media_type, media_obj.media_type),
                    'media_title': media_obj.title or 'Untitled',
                    'related_to': f"{related_obj_type.capitalize()}: {related_obj.title}",
                    'uploaded_by': media_obj.uploaded_by.get_full_name() or media_obj.uploaded_by.username,
                },
                action_url=action_url,
                priority='normal',
                icon=icon,
                color='#2196F3',
                send_email=should_notify_user(recipient, notification_type, 'email')
            )

def notify_comment_added(comment):
    """Send notification when a comment is added to a project or update"""
    project = comment.project
    update = comment.update
    
    # Determine who should be notified
    recipients = set()
    
    # Notify the project manager
    if project.manager and project.manager != comment.user:
        recipients.add(project.manager)
    
    # If it's a reply, notify the parent comment author
    if comment.parent and comment.parent.user != comment.user:
        recipients.add(comment.parent.user)
    
    # If it's on an update, notify the update submitter
    if update and update.submitted_by != comment.user:
        recipients.add(update.submitted_by)
    
    # Send notifications
    notification_type = 'comment_added'
    
    action_url = PROJECT_DETAIL_URL.format(project_id=project.id)
    if update:
        action_url = PROJECT_UPDATE_URL.format(project_id=project.id)
    
    for recipient in recipients:
        if should_notify_user(recipient, notification_type, 'in_app'):
            NotificationService.create_notification(
                recipient=recipient,
                notification_type_name=notification_type,
                context_data={
                    'project_title': project.title,
                    'comment_by': comment.user.get_full_name() or comment.user.username,
                    'comment_on': 'update' if update else 'project',
                    'is_reply': comment.parent is not None,
                },
                action_url=action_url,
                priority='normal',
                icon='message-square',
                color='#2196F3',
                send_email=should_notify_user(recipient, notification_type, 'email')
            )

def notify_team_member_role_changed(team_member, old_role, new_role, changed_by):
    """Send notification when a team member's role is changed"""
    project = team_member.project
    user = team_member.user
    
    # Notify the user whose role was changed
    if should_notify_user(user, 'team_member_role_changed', 'in_app'):
        NotificationService.create_notification(
            recipient=user,
            notification_type_name='team_member_role_changed',
            context_data={
                'project_title': project.title,
                'old_role': dict(team_member.ROLE_CHOICES).get(old_role, old_role),
                'new_role': dict(team_member.ROLE_CHOICES).get(new_role, new_role),
                'changed_by': changed_by.get_full_name() or changed_by.username,
            },
            action_url=PROJECT_DETAIL_URL.format(project_id=project.id),
            priority='normal',
            icon='users',
            color='#2196F3',
            send_email=should_notify_user(user, 'team_member_role_changed', 'email')
        )
    
    # Notify the project manager
    if project.manager and project.manager != user and project.manager != changed_by and should_notify_user(project.manager, 'team_member_role_changed', 'in_app'):
        NotificationService.create_notification(
            recipient=project.manager,
            notification_type_name='team_member_role_changed',
            context_data={
                'project_title': project.title,
                'user_name': user.get_full_name() or user.username,
                'old_role': dict(team_member.ROLE_CHOICES).get(old_role, old_role),
                'new_role': dict(team_member.ROLE_CHOICES).get(new_role, new_role),
                'changed_by': changed_by.get_full_name() or changed_by.username,
            },
            action_url=PROJECT_DETAIL_URL.format(project_id=project.id),
            priority='normal',
            icon='users',
            color='#2196F3',
            send_email=should_notify_user(project.manager, 'team_member_role_changed', 'email')
        )
