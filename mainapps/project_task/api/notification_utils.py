"""
Utility functions for sending task-related notifications in the project management system.
This centralizes all task notification creation to ensure consistency and proper preference checking.
"""

from django.contrib.auth import get_user_model
from django.utils import timezone
from mainapps.notification.models import Notification, NotificationType, NotificationPreference
from mainapps.notification.services import NotificationService
from mainapps.project_task.models import Task, TaskStatus, TaskPriority

User = get_user_model()

# Task URL paths (hardcoded for Next.js frontend compatibility)
TASK_DETAIL_URL = "/dashboard/tasks/{task_id}"
PROJECT_TASKS_URL = "/dashboard/projects/{project_id}/tasks"
MILESTONE_TASKS_URL = "/dashboard/projects/{project_id}/milestones/{milestone_id}/tasks"
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

def notify_task_created(task):
    """Send notification when a new task is created"""
    # Determine who should be notified
    recipients = set()
    
    # Notify the project manager if task is part of a project
    if task.project and task.project.manager:
        recipients.add(task.project.manager)
    
    # Notify assigned users
    for user in task.assigned_to.all():
        recipients.add(user)
    
    # Notify parent task assignees if this is a subtask
    if task.parent:
        for user in task.parent.assigned_to.all():
            recipients.add(user)
    
    # Don't notify the creator
    if task.created_by in recipients:
        recipients.remove(task.created_by)
    
    # Send notifications
    notification_type = 'task_created'
    
    # Determine priority based on task priority
    priority_map = {
        TaskPriority.LOW: 'normal',
        TaskPriority.MEDIUM: 'normal',
        TaskPriority.HIGH: 'high',
        TaskPriority.URGENT: 'high'
    }
    notification_priority = priority_map.get(task.priority, 'normal')
    
    # Determine icon based on task type
    icon_map = {
        'feature': 'plus-circle',
        'bug': 'alert-circle',
        'improvement': 'arrow-up-circle',
        'documentation': 'file-text',
        'research': 'search',
        'other': 'circle'
    }
    icon = icon_map.get(task.task_type, 'check-circle')
    
    # Determine color based on task priority
    color_map = {
        TaskPriority.LOW: '#2196F3',     # Blue
        TaskPriority.MEDIUM: '#4CAF50',  # Green
        TaskPriority.HIGH: '#FF9800',    # Orange
        TaskPriority.URGENT: '#F44336'   # Red
    }
    color = color_map.get(task.priority, '#2196F3')
    
    # Determine action URL
    if task.milestone:
        action_url = MILESTONE_TASKS_URL.format(
            project_id=task.project.id,
            milestone_id=task.milestone.id
        )
    elif task.project:
        action_url = PROJECT_TASKS_URL.format(project_id=task.project.id)
    else:
        action_url = TASK_DETAIL_URL.format(task_id=task.id)
    
    for recipient in recipients:
        if should_notify_user(recipient, notification_type, 'in_app'):
            NotificationService.create_notification(
                recipient=recipient,
                notification_type_name=notification_type,
                context_data={
                    'task_title': task.title,
                    'task_type': dict(task.TaskType.choices).get(task.task_type, task.task_type),
                    'project_title': task.project.title if task.project else None,
                    'milestone_title': task.milestone.title if task.milestone else None,
                    'created_by': task.created_by.get_full_name() or task.created_by.username if task.created_by else 'System',
                    'is_subtask': task.parent is not None,
                    'parent_task': task.parent.title if task.parent else None,
                },
                action_url=action_url,
                priority=notification_priority,
                icon=icon,
                color=color,
                send_email=should_notify_user(recipient, notification_type, 'email')
            )

def notify_task_assigned(task, user, assigned_by=None):
    """Send notification when a user is assigned to a task"""
    # Don't notify if the user assigned themselves
    if assigned_by and assigned_by == user:
        return
    
    notification_type = 'task_assigned'
    
    # Determine priority based on task priority
    priority_map = {
        TaskPriority.LOW: 'normal',
        TaskPriority.MEDIUM: 'normal',
        TaskPriority.HIGH: 'high',
        TaskPriority.URGENT: 'high'
    }
    notification_priority = priority_map.get(task.priority, 'normal')
    
    # Determine action URL
    if task.milestone:
        action_url = MILESTONE_TASKS_URL.format(
            project_id=task.project.id,
            milestone_id=task.milestone.id
        )
    elif task.project:
        action_url = PROJECT_TASKS_URL.format(project_id=task.project.id)
    else:
        action_url = TASK_DETAIL_URL.format(task_id=task.id)
    
    if should_notify_user(user, notification_type, 'in_app'):
        NotificationService.create_notification(
            recipient=user,
            notification_type_name=notification_type,
            context_data={
                'task_title': task.title,
                'task_priority': dict(task.TaskPriority.choices).get(task.priority, task.priority),
                'project_title': task.project.title if task.project else None,
                'milestone_title': task.milestone.title if task.milestone else None,
                'due_date': task.due_date.strftime('%Y-%m-%d %H:%M') if task.due_date else None,
                'assigned_by': assigned_by.get_full_name() or assigned_by.username if assigned_by else 'System',
            },
            action_url=action_url,
            priority=notification_priority,
            icon='user-plus',
            color='#2196F3',
            send_email=should_notify_user(user, notification_type, 'email')
        )

def notify_task_unassigned(task, user, unassigned_by=None):
    """Send notification when a user is unassigned from a task"""
    # Don't notify if the user unassigned themselves
    if unassigned_by and unassigned_by == user:
        return
    
    notification_type = 'task_unassigned'
    
    # Determine action URL
    if task.milestone:
        action_url = MILESTONE_TASKS_URL.format(
            project_id=task.project.id,
            milestone_id=task.milestone.id
        )
    elif task.project:
        action_url = PROJECT_TASKS_URL.format(project_id=task.project.id)
    else:
        action_url = TASK_DETAIL_URL.format(task_id=task.id)
    
    if should_notify_user(user, notification_type, 'in_app'):
        NotificationService.create_notification(
            recipient=user,
            notification_type_name=notification_type,
            context_data={
                'task_title': task.title,
                'project_title': task.project.title if task.project else None,
                'milestone_title': task.milestone.title if task.milestone else None,
                'unassigned_by': unassigned_by.get_full_name() or unassigned_by.username if unassigned_by else 'System',
            },
            action_url=action_url,
            priority='normal',
            icon='user-minus',
            color='#FF9800',
            send_email=should_notify_user(user, notification_type, 'email')
        )

def notify_task_status_changed(task, old_status, new_status, changed_by=None):
    """Send notification when a task's status changes"""
    # Determine who should be notified
    recipients = set()
    
    # Notify assigned users
    for user in task.assigned_to.all():
        recipients.add(user)
    
    # Notify the creator
    if task.created_by:
        recipients.add(task.created_by)
    
    # Notify the project manager if task is part of a project
    if task.project and task.project.manager:
        recipients.add(task.project.manager)
    
    # Notify parent task assignees if this is a subtask
    if task.parent:
        for user in task.parent.assigned_to.all():
            recipients.add(user)
    
    # Don't notify the person who changed the status
    if changed_by in recipients:
        recipients.remove(changed_by)
    
    # Send notifications
    notification_type = 'task_status_changed'
    
    # Determine priority based on the transition
    priority = 'normal'
    if new_status == TaskStatus.COMPLETED:
        priority = 'normal'
    elif new_status == TaskStatus.BLOCKED:
        priority = 'high'
    
    # Determine icon based on new status
    icon_map = {
        TaskStatus.TODO: 'circle',
        TaskStatus.IN_PROGRESS: 'play-circle',
        TaskStatus.REVIEW: 'eye',
        TaskStatus.COMPLETED: 'check-circle',
        TaskStatus.BLOCKED: 'alert-triangle',
        TaskStatus.CANCELLED: 'x-circle'
    }
    icon = icon_map.get(new_status, 'circle')
    
    # Determine color based on new status
    color_map = {
        TaskStatus.TODO: '#2196F3',       # Blue
        TaskStatus.IN_PROGRESS: '#4CAF50', # Green
        TaskStatus.REVIEW: '#9C27B0',      # Purple
        TaskStatus.COMPLETED: '#4CAF50',   # Green
        TaskStatus.BLOCKED: '#F44336',     # Red
        TaskStatus.CANCELLED: '#9E9E9E'    # Grey
    }
    color = color_map.get(new_status, '#2196F3')
    
    # Determine action URL
    if task.milestone:
        action_url = MILESTONE_TASKS_URL.format(
            project_id=task.project.id,
            milestone_id=task.milestone.id
        )
    elif task.project:
        action_url = PROJECT_TASKS_URL.format(project_id=task.project.id)
    else:
        action_url = TASK_DETAIL_URL.format(task_id=task.id)
    
    for recipient in recipients:
        if should_notify_user(recipient, notification_type, 'in_app'):
            NotificationService.create_notification(
                recipient=recipient,
                notification_type_name=notification_type,
                context_data={
                    'task_title': task.title,
                    'old_status': dict(task.TaskStatus.choices).get(old_status, old_status),
                    'new_status': dict(task.TaskStatus.choices).get(new_status, new_status),
                    'project_title': task.project.title if task.project else None,
                    'milestone_title': task.milestone.title if task.milestone else None,
                    'changed_by': changed_by.get_full_name() or changed_by.username if changed_by else 'System',
                },
                action_url=action_url,
                priority=priority,
                icon=icon,
                color=color,
                send_email=should_notify_user(recipient, notification_type, 'email')
            )

def notify_task_completed(task, completed_by=None):
    """Send notification when a task is completed"""
    # Determine who should be notified
    recipients = set()
    
    # Notify the creator
    if task.created_by and task.created_by != completed_by:
        recipients.add(task.created_by)
    
    # Notify the project manager if task is part of a project
    if task.project and task.project.manager and task.project.manager != completed_by:
        recipients.add(task.project.manager)
    
    # Notify parent task assignees if this is a subtask
    if task.parent:
        for user in task.parent.assigned_to.all():
            if user != completed_by:
                recipients.add(user)
    
    # Notify task dependents (tasks that depend on this one)
    for dependent_task in task.dependents.all():
        for user in dependent_task.assigned_to.all():
            if user != completed_by:
                recipients.add(user)
    
    # Send notifications
    notification_type = 'task_completed'
    
    # Determine action URL
    if task.milestone:
        action_url = MILESTONE_TASKS_URL.format(
            project_id=task.project.id,
            milestone_id=task.milestone.id
        )
    elif task.project:
        action_url = PROJECT_TASKS_URL.format(project_id=task.project.id)
    else:
        action_url = TASK_DETAIL_URL.format(task_id=task.id)
    
    for recipient in recipients:
        if should_notify_user(recipient, notification_type, 'in_app'):
            NotificationService.create_notification(
                recipient=recipient,
                notification_type_name=notification_type,
                context_data={
                    'task_title': task.title,
                    'project_title': task.project.title if task.project else None,
                    'milestone_title': task.milestone.title if task.milestone else None,
                    'completed_by': completed_by.get_full_name() or completed_by.username if completed_by else 'System',
                    'completion_date': task.completion_date.strftime('%Y-%m-%d %H:%M') if task.completion_date else timezone.now().strftime('%Y-%m-%d %H:%M'),
                    'is_subtask': task.parent is not None,
                    'parent_task': task.parent.title if task.parent else None,
                },
                action_url=action_url,
                priority='normal',
                icon='check-circle',
                color='#4CAF50',
                send_email=should_notify_user(recipient, notification_type, 'email')
            )

def notify_task_approaching_due(task, days_remaining):
    """Send notification when a task's due date is approaching"""
    # Determine who should be notified
    recipients = set()
    
    # Notify assigned users
    for user in task.assigned_to.all():
        recipients.add(user)
    
    # Send notifications
    notification_type = 'task_approaching_due'
    
    # Determine priority based on days remaining
    priority = 'normal'
    if days_remaining <= 1:
        priority = 'high'
    elif days_remaining <= 3:
        priority = 'normal'
    
    # Determine action URL
    if task.milestone:
        action_url = MILESTONE_TASKS_URL.format(
            project_id=task.project.id,
            milestone_id=task.milestone.id
        )
    elif task.project:
        action_url = PROJECT_TASKS_URL.format(project_id=task.project.id)
    else:
        action_url = TASK_DETAIL_URL.format(task_id=task.id)
    
    for recipient in recipients:
        if should_notify_user(recipient, notification_type, 'in_app'):
            NotificationService.create_notification(
                recipient=recipient,
                notification_type_name=notification_type,
                context_data={
                    'task_title': task.title,
                    'project_title': task.project.title if task.project else None,
                    'milestone_title': task.milestone.title if task.milestone else None,
                    'due_date': task.due_date.strftime('%Y-%m-%d %H:%M') if task.due_date else None,
                    'days_remaining': days_remaining,
                },
                action_url=action_url,
                priority=priority,
                icon='clock',
                color='#FF9800',
                send_email=should_notify_user(recipient, notification_type, 'email')
            )

def notify_task_overdue(task):
    """Send notification when a task is overdue"""
    # Determine who should be notified
    recipients = set()
    
    # Notify assigned users
    for user in task.assigned_to.all():
        recipients.add(user)
    
    # Notify the project manager if task is part of a project
    if task.project and task.project.manager:
        recipients.add(task.project.manager)
    
    # Send notifications
    notification_type = 'task_overdue'
    
    # Determine action URL
    if task.milestone:
        action_url = MILESTONE_TASKS_URL.format(
            project_id=task.project.id,
            milestone_id=task.milestone.id
        )
    elif task.project:
        action_url = PROJECT_TASKS_URL.format(project_id=task.project.id)
    else:
        action_url = TASK_DETAIL_URL.format(task_id=task.id)
    
    for recipient in recipients:
        if should_notify_user(recipient, notification_type, 'in_app'):
            NotificationService.create_notification(
                recipient=recipient,
                notification_type_name=notification_type,
                context_data={
                    'task_title': task.title,
                    'project_title': task.project.title if task.project else None,
                    'milestone_title': task.milestone.title if task.milestone else None,
                    'due_date': task.due_date.strftime('%Y-%m-%d %H:%M') if task.due_date else None,
                    'days_overdue': (timezone.now().date() - task.due_date.date()).days if task.due_date else 0,
                },
                action_url=action_url,
                priority='high',
                icon='alert-circle',
                color='#F44336',
                send_email=should_notify_user(recipient, notification_type, 'email')
            )

def notify_task_comment_added(comment):
    """Send notification when a comment is added to a task"""
    task = comment.task
    
    # Determine who should be notified
    recipients = set()
    
    # Notify assigned users
    for user in task.assigned_to.all():
        recipients.add(user)
    
    # Notify the creator
    if task.created_by:
        recipients.add(task.created_by)
    
    # Don't notify the commenter
    if comment.user in recipients:
        recipients.remove(comment.user)
    
    # Send notifications
    notification_type = 'task_comment_added'
    
    # Determine action URL
    action_url = TASK_DETAIL_URL.format(task_id=task.id)
    
    for recipient in recipients:
        if should_notify_user(recipient, notification_type, 'in_app'):
            NotificationService.create_notification(
                recipient=recipient,
                notification_type_name=notification_type,
                context_data={
                    'task_title': task.title,
                    'project_title': task.project.title if task.project else None,
                    'milestone_title': task.milestone.title if task.milestone else None,
                    'comment_by': comment.user.get_full_name() or comment.user.username,
                    'comment_preview': comment.content[:100] + ('...' if len(comment.content) > 100 else ''),
                },
                action_url=action_url,
                priority='normal',
                icon='message-square',
                color='#2196F3',
                send_email=should_notify_user(recipient, notification_type, 'email')
            )

def notify_task_attachment_added(attachment):
    """Send notification when an attachment is added to a task"""
    task = attachment.task
    
    # Determine who should be notified
    recipients = set()
    
    # Notify assigned users
    for user in task.assigned_to.all():
        recipients.add(user)
    
    # Notify the creator
    if task.created_by:
        recipients.add(task.created_by)
    
    # Don't notify the uploader
    if attachment.uploaded_by in recipients:
        recipients.remove(attachment.uploaded_by)
    
    # Send notifications
    notification_type = 'task_attachment_added'
    
    # Determine action URL
    action_url = TASK_DETAIL_URL.format(task_id=task.id)
    
    for recipient in recipients:
        if should_notify_user(recipient, notification_type, 'in_app'):
            NotificationService.create_notification(
                recipient=recipient,
                notification_type_name=notification_type,
                context_data={
                    'task_title': task.title,
                    'project_title': task.project.title if task.project else None,
                    'milestone_title': task.milestone.title if task.milestone else None,
                    'attachment_name': attachment.filename,
                    'uploaded_by': attachment.uploaded_by.get_full_name() or attachment.uploaded_by.username,
                },
                action_url=action_url,
                priority='normal',
                icon='paperclip',
                color='#2196F3',
                send_email=should_notify_user(recipient, notification_type, 'email')
            )

def notify_task_time_logged(time_log):
    """Send notification when time is logged on a task"""
    task = time_log.task
    
    # Determine who should be notified
    recipients = set()
    
    # Notify the project manager if task is part of a project
    if task.project and task.project.manager and task.project.manager != time_log.user:
        recipients.add(task.project.manager)
    
    # Notify the task creator
    if task.created_by and task.created_by != time_log.user:
        recipients.add(task.created_by)
    
    # Send notifications
    notification_type = 'task_time_logged'
    
    # Determine action URL
    action_url = TASK_DETAIL_URL.format(task_id=task.id)
    
    for recipient in recipients:
        if should_notify_user(recipient, notification_type, 'in_app'):
            NotificationService.create_notification(
                recipient=recipient,
                notification_type_name=notification_type,
                context_data={
                    'task_title': task.title,
                    'project_title': task.project.title if task.project else None,
                    'milestone_title': task.milestone.title if task.milestone else None,
                    'minutes': time_log.minutes,
                    'hours_minutes': f"{time_log.minutes // 60}h {time_log.minutes % 60}m",
                    'logged_by': time_log.user.get_full_name() or time_log.user.username,
                    'description': time_log.description,
                },
                action_url=action_url,
                priority='normal',
                icon='clock',
                color='#2196F3',
                send_email=should_notify_user(recipient, notification_type, 'email')
            )

def notify_task_dependency_completed(dependency, dependent_task):
    """Send notification when a task dependency is completed"""
    # Notify users assigned to the dependent task
    for user in dependent_task.assigned_to.all():
        notification_type = 'task_dependency_completed'
        
        # Determine action URL
        action_url = TASK_DETAIL_URL.format(task_id=dependent_task.id)
        
        if should_notify_user(user, notification_type, 'in_app'):
            NotificationService.create_notification(
                recipient=user,
                notification_type_name=notification_type,
                context_data={
                    'task_title': dependent_task.title,
                    'dependency_title': dependency.title,
                    'project_title': dependent_task.project.title if dependent_task.project else None,
                    'milestone_title': dependent_task.milestone.title if dependent_task.milestone else None,
                },
                action_url=action_url,
                priority='normal',
                icon='unlock',
                color='#4CAF50',
                send_email=should_notify_user(user, notification_type, 'email')
            )

def notify_task_priority_changed(task, old_priority, new_priority, changed_by=None):
    """Send notification when a task's priority changes"""
    # Determine who should be notified
    recipients = set()
    
    # Notify assigned users
    for user in task.assigned_to.all():
        recipients.add(user)
    
    # Don't notify the person who changed the priority
    if changed_by in recipients:
        recipients.remove(changed_by)
    
    # Send notifications
    notification_type = 'task_priority_changed'
    
    # Determine priority based on new task priority
    priority_map = {
        TaskPriority.LOW: 'normal',
        TaskPriority.MEDIUM: 'normal',
        TaskPriority.HIGH: 'high',
        TaskPriority.URGENT: 'high'
    }
    notification_priority = priority_map.get(new_priority, 'normal')
    
    # Determine color based on new priority
    color_map = {
        TaskPriority.LOW: '#2196F3',     # Blue
        TaskPriority.MEDIUM: '#4CAF50',  # Green
        TaskPriority.HIGH: '#FF9800',    # Orange
        TaskPriority.URGENT: '#F44336'   # Red
    }
    color = color_map.get(new_priority, '#2196F3')
    
    # Determine action URL
    if task.milestone:
        action_url = MILESTONE_TASKS_URL.format(
            project_id=task.project.id,
            milestone_id=task.milestone.id
        )
    elif task.project:
        action_url = PROJECT_TASKS_URL.format(project_id=task.project.id)
    else:
        action_url = TASK_DETAIL_URL.format(task_id=task.id)
    
    for recipient in recipients:
        if should_notify_user(recipient, notification_type, 'in_app'):
            NotificationService.create_notification(
                recipient=recipient,
                notification_type_name=notification_type,
                context_data={
                    'task_title': task.title,
                    'old_priority': dict(task.TaskPriority.choices).get(old_priority, old_priority),
                    'new_priority': dict(task.TaskPriority.choices).get(new_priority, new_priority),
                    'project_title': task.project.title if task.project else None,
                    'milestone_title': task.milestone.title if task.milestone else None,
                    'changed_by': changed_by.get_full_name() or changed_by.username if changed_by else 'System',
                },
                action_url=action_url,
                priority=notification_priority,
                icon='flag',
                color=color,
                send_email=should_notify_user(recipient, notification_type, 'email')
            )

def notify_subtask_created(subtask):
    """Send notification when a subtask is created"""
    parent_task = subtask.parent
    
    # Notify users assigned to the parent task
    for user in parent_task.assigned_to.all():
        # Don't notify the creator of the subtask
        if subtask.created_by and user == subtask.created_by:
            continue
            
        notification_type = 'subtask_created'
        
        # Determine action URL
        action_url = TASK_DETAIL_URL.format(task_id=parent_task.id)
        
        if should_notify_user(user, notification_type, 'in_app'):
            NotificationService.create_notification(
                recipient=user,
                notification_type_name=notification_type,
                context_data={
                    'parent_task_title': parent_task.title,
                    'subtask_title': subtask.title,
                    'project_title': parent_task.project.title if parent_task.project else None,
                    'milestone_title': parent_task.milestone.title if parent_task.milestone else None,
                    'created_by': subtask.created_by.get_full_name() or subtask.created_by.username if subtask.created_by else 'System',
                },
                action_url=action_url,
                priority='normal',
                icon='git-branch',
                color='#2196F3',
                send_email=should_notify_user(user, notification_type, 'email')
            )
