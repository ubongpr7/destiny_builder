from django.core.management.base import BaseCommand
from ...models import NotificationType, NotificationCategory, NotificationPriority

class Command(BaseCommand):
    help = 'Set up notification types for the project management system'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Creating project management notification types...'))
        
        # Define notification types for project management
        notification_types = [
            # Project notifications
            {
                'name': 'project_created',
                'description': 'A new project has been created',
                'category': NotificationCategory.PROJECT,
                'title_template': 'New Project Created',
                'body_template': 'A new project "${project_title}" has been created by ${created_by}.',
                'icon': 'file-plus',
                'color': 'green',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
                'send_push': True,
                'can_disable': True
            },
            {
                'name': 'project_status_changed',
                'description': 'A project\'s status has been updated',
                'category': NotificationCategory.PROJECT,
                'title_template': 'Project Status Changed',
                'body_template': 'The project "${project_title}" status has been changed from ${old_status} to ${new_status}.',
                'icon': 'refresh-cw',
                'color': 'blue',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
                'send_push': True,
                'can_disable': True
            },
            {
                'name': 'project_approved',
                'description': 'A submitted project has been approved',
                'category': NotificationCategory.PROJECT,
                'title_template': 'Project Approved',
                'body_template': 'Your project "${project_title}" has been approved and is now active.',
                'icon': 'check-circle',
                'color': 'green',
                'default_priority': NotificationPriority.HIGH,
                'send_email': True,
                'send_push': True,
                'can_disable': False
            },
            {
                'name': 'project_rejected',
                'description': 'A submitted project has been rejected',
                'category': NotificationCategory.PROJECT,
                'title_template': 'Project Rejected',
                'body_template': 'Your project "${project_title}" has been rejected. Reason: ${rejection_reason}',
                'icon': 'x-circle',
                'color': 'red',
                'default_priority': NotificationPriority.HIGH,
                'send_email': True,
                'send_push': True,
                'can_disable': False
            },
            {
                'name': 'project_completed',
                'description': 'A project has been marked as completed',
                'category': NotificationCategory.PROJECT,
                'title_template': 'Project Completed',
                'body_template': 'The project "${project_title}" has been marked as completed.',
                'icon': 'check-square',
                'color': 'green',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
                'send_push': True,
                'can_disable': True
            },
            {
                'name': 'project_on_hold',
                'description': 'A project has been put on hold',
                'category': NotificationCategory.PROJECT,
                'title_template': 'Project On Hold',
                'body_template': 'The project "${project_title}" has been put on hold. Reason: ${hold_reason}',
                'icon': 'pause-circle',
                'color': 'orange',
                'default_priority': NotificationPriority.HIGH,
                'send_email': True,
                'send_push': True,
                'can_disable': False
            },
            {
                'name': 'project_reactivated',
                'description': 'A project has been reactivated from on-hold status',
                'category': NotificationCategory.PROJECT,
                'title_template': 'Project Reactivated',
                'body_template': 'The project "${project_title}" has been reactivated and is now active again.',
                'icon': 'play-circle',
                'color': 'green',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
                'send_push': True,
                'can_disable': True
            },
            {
                'name': 'project_approaching_end',
                'description': 'A project\'s end date is approaching',
                'category': NotificationCategory.PROJECT,
                'title_template': 'Project End Date Approaching',
                'body_template': 'The project "${project_title}" is scheduled to end in ${days_remaining} days.',
                'icon': 'clock',
                'color': 'orange',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
                'send_push': True,
                'can_disable': True
            },
            {
                'name': 'project_overdue',
                'description': 'A project has passed its target end date',
                'category': NotificationCategory.PROJECT,
                'title_template': 'Project Overdue',
                'body_template': 'The project "${project_title}" is overdue by ${days_overdue} days.',
                'icon': 'alert-circle',
                'color': 'red',
                'default_priority': NotificationPriority.HIGH,
                'send_email': True,
                'send_push': True,
                'can_disable': False
            },
            {
                'name': 'project_overbudget',
                'description': 'A project has exceeded its budget',
                'category': NotificationCategory.PROJECT,
                'title_template': 'Project Over Budget',
                'body_template': 'The project "${project_title}" has exceeded its budget of ${budget} by ${amount_over}.',
                'icon': 'alert-triangle',
                'color': 'red',
                'default_priority': NotificationPriority.HIGH,
                'send_email': True,
                'send_push': True,
                'can_disable': False
            },
            {
                'name': 'project_budget_updated',
                'description': 'A project\'s budget has been updated',
                'category': NotificationCategory.PROJECT,
                'title_template': 'Project Budget Updated',
                'body_template': 'The budget for project "${project_title}" has been updated from ${old_budget} to ${new_budget}.',
                'icon': 'dollar-sign',
                'color': 'blue',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
                'send_push': False,
                'can_disable': True
            },
            {
                'name': 'project_dates_updated',
                'description': 'A project\'s dates have been updated',
                'category': NotificationCategory.PROJECT,
                'title_template': 'Project Dates Updated',
                'body_template': 'The dates for project "${project_title}" have been updated. New end date: ${new_end_date}.',
                'icon': 'calendar',
                'color': 'blue',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
                'send_push': False,
                'can_disable': True
            },
            
            # Team notifications
            {
                'name': 'team_member_added',
                'description': 'You have been added to a project team',
                'category': NotificationCategory.TEAM,
                'title_template': 'Added to Project Team',
                'body_template': 'You have been added to the project "${project_title}" as a ${role}.',
                'icon': 'user-plus',
                'color': 'blue',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
                'send_push': True,
                'can_disable': False
            },
            {
                'name': 'team_member_removed',
                'description': 'You have been removed from a project team',
                'category': NotificationCategory.TEAM,
                'title_template': 'Removed from Project Team',
                'body_template': 'You have been removed from the project "${project_title}" team.',
                'icon': 'user-minus',
                'color': 'orange',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
                'send_push': True,
                'can_disable': False
            },
            {
                'name': 'team_member_role_changed',
                'description': 'Your role in a project team has been changed',
                'category': NotificationCategory.TEAM,
                'title_template': 'Team Role Changed',
                'body_template': 'Your role in the project "${project_title}" has been changed from ${old_role} to ${new_role}.',
                'icon': 'users',
                'color': 'blue',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
                'send_push': False,
                'can_disable': True
            },
            {
                'name': 'official_added',
                'description': 'You have been added as an official to a project',
                'category': NotificationCategory.TEAM,
                'title_template': 'Added as Project Official',
                'body_template': 'You have been added as an official to the project "${project_title}".',
                'icon': 'user-plus',
                'color': 'blue',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
                'send_push': True,
                'can_disable': False
            },
            {
                'name': 'official_removed',
                'description': 'You have been removed as an official from a project',
                'category': NotificationCategory.TEAM,
                'title_template': 'Removed as Project Official',
                'body_template': 'You have been removed as an official from the project "${project_title}".',
                'icon': 'user-minus',
                'color': 'orange',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
                'send_push': True,
                'can_disable': False
            },
            {
                'name': 'project_manager_changed',
                'description': 'A project\'s manager has been changed',
                'category': NotificationCategory.TEAM,
                'title_template': 'Project Manager Changed',
                'body_template': 'The manager for project "${project_title}" has been changed from ${old_manager} to ${new_manager}.',
                'icon': 'user',
                'color': 'blue',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
                'send_push': True,
                'can_disable': True
            },
            
            # Milestone notifications
            {
                'name': 'milestone_created',
                'description': 'A new milestone has been created',
                'category': NotificationCategory.MILESTONE,
                'title_template': 'New Milestone Created',
                'body_template': 'A new milestone "${milestone_title}" has been created for project "${project_title}".',
                'icon': 'flag',
                'color': 'blue',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
                'send_push': False,
                'can_disable': True
            },
            {
                'name': 'milestone_assigned',
                'description': 'You have been assigned to a milestone',
                'category': NotificationCategory.MILESTONE,
                'title_template': 'Assigned to Milestone',
                'body_template': 'You have been assigned to the milestone "${milestone_title}" in project "${project_title}".',
                'icon': 'flag',
                'color': 'blue',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
                'send_push': True,
                'can_disable': False
            },
            {
                'name': 'milestone_unassigned',
                'description': 'You have been unassigned from a milestone',
                'category': NotificationCategory.MILESTONE,
                'title_template': 'Unassigned from Milestone',
                'body_template': 'You have been unassigned from the milestone "${milestone_title}" in project "${project_title}".',
                'icon': 'flag',
                'color': 'orange',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
                'send_push': False,
                'can_disable': True
            },
            {
                'name': 'milestone_status_changed',
                'description': 'A milestone\'s status has been updated',
                'category': NotificationCategory.MILESTONE,
                'title_template': 'Milestone Status Changed',
                'body_template': 'The status of milestone "${milestone_title}" in project "${project_title}" has been changed from ${old_status} to ${new_status}.',
                'icon': 'refresh-cw',
                'color': 'blue',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
                'send_push': False,
                'can_disable': True
            },
            {
                'name': 'milestone_completed',
                'description': 'A milestone has been completed',
                'category': NotificationCategory.MILESTONE,
                'title_template': 'Milestone Completed',
                'body_template': 'The milestone "${milestone_title}" in project "${project_title}" has been marked as completed.',
                'icon': 'check-square',
                'color': 'green',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
                'send_push': True,
                'can_disable': True
            },
            {
                'name': 'milestone_approaching',
                'description': 'A milestone\'s due date is approaching',
                'category': NotificationCategory.MILESTONE,
                'title_template': 'Milestone Due Soon',
                'body_template': 'The milestone "${milestone_title}" in project "${project_title}" is due in ${days_remaining} days.',
                'icon': 'clock',
                'color': 'orange',
                'default_priority': NotificationPriority.HIGH,
                'send_email': True,
                'send_push': True,
                'can_disable': True
            },
            {
                'name': 'milestone_overdue',
                'description': 'A milestone is past its due date',
                'category': NotificationCategory.MILESTONE,
                'title_template': 'Milestone Overdue',
                'body_template': 'The milestone "${milestone_title}" in project "${project_title}" is overdue by ${days_overdue} days.',
                'icon': 'alert-circle',
                'color': 'red',
                'default_priority': NotificationPriority.HIGH,
                'send_email': True,
                'send_push': True,
                'can_disable': False
            },
            {
                'name': 'milestone_dependency_added',
                'description': 'A dependency has been added to a milestone',
                'category': NotificationCategory.MILESTONE,
                'title_template': 'Milestone Dependency Added',
                'body_template': 'The milestone "${milestone_title}" now depends on "${dependency_title}" in project "${project_title}".',
                'icon': 'link',
                'color': 'blue',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
                'send_push': False,
                'can_disable': True
            },
            {
                'name': 'milestone_priority_changed',
                'description': 'A milestone\'s priority has been changed',
                'category': NotificationCategory.MILESTONE,
                'title_template': 'Milestone Priority Changed',
                'body_template': 'The priority of milestone "${milestone_title}" in project "${project_title}" has been changed from ${old_priority} to ${new_priority}.',
                'icon': 'arrow-up',
                'color': 'purple',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
                'send_push': False,
                'can_disable': True
            },
            
            # Expense notifications
            {
                'name': 'expense_created',
                'description': 'A new expense has been created',
                'category': NotificationCategory.EXPENSE,
                'title_template': 'New Expense Created',
                'body_template': 'A new expense "${expense_title}" for ${amount} has been created for project "${project_title}".',
                'icon': 'credit-card',
                'color': 'blue',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
                'send_push': False,
                'can_disable': True
            },
            {
                'name': 'expense_approved',
                'description': 'An expense has been approved',
                'category': NotificationCategory.EXPENSE,
                'title_template': 'Expense Approved',
                'body_template': 'Your expense "${expense_title}" for ${amount} has been approved.',
                'icon': 'check-circle',
                'color': 'green',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
                'send_push': True,
                'can_disable': False
            },
            {
                'name': 'expense_rejected',
                'description': 'An expense has been rejected',
                'category': NotificationCategory.EXPENSE,
                'title_template': 'Expense Rejected',
                'body_template': 'Your expense "${expense_title}" for ${amount} has been rejected. Reason: ${rejection_reason}',
                'icon': 'x-circle',
                'color': 'red',
                'default_priority': NotificationPriority.HIGH,
                'send_email': True,
                'send_push': True,
                'can_disable': False
            },
            {
                'name': 'expense_reimbursed',
                'description': 'An expense has been reimbursed',
                'category': NotificationCategory.EXPENSE,
                'title_template': 'Expense Reimbursed',
                'body_template': 'Your expense "${expense_title}" for ${amount} has been reimbursed.',
                'icon': 'dollar-sign',
                'color': 'green',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
                'send_push': True,
                'can_disable': False
            },
            {
                'name': 'large_expense_created',
                'description': 'A large expense has been created',
                'category': NotificationCategory.EXPENSE,
                'title_template': 'Large Expense Created',
                'body_template': 'A large expense "${expense_title}" for ${amount} has been created for project "${project_title}".',
                'icon': 'alert-circle',
                'color': 'orange',
                'default_priority': NotificationPriority.HIGH,
                'send_email': True,
                'send_push': True,
                'can_disable': False
            },
            
            # Update notifications
            {
                'name': 'update_created',
                'description': 'A new project update has been created',
                'category': NotificationCategory.UPDATE,
                'title_template': 'New Project Update',
                'body_template': 'A new update has been posted for project "${project_title}" by ${submitted_by}.',
                'icon': 'file-text',
                'color': 'blue',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
                'send_push': False,
                'can_disable': True
            },
            {
                'name': 'update_with_challenges',
                'description': 'A project update mentions significant challenges',
                'category': NotificationCategory.UPDATE,
                'title_template': 'Project Challenges Reported',
                'body_template': 'Challenges have been reported in the latest update for project "${project_title}".',
                'icon': 'alert-triangle',
                'color': 'orange',
                'default_priority': NotificationPriority.HIGH,
                'send_email': True,
                'send_push': True,
                'can_disable': False
            },
            {
                'name': 'update_with_high_spend',
                'description': 'A project update reports high daily expenditure',
                'category': NotificationCategory.UPDATE,
                'title_template': 'High Daily Expenditure',
                'body_template': 'High daily expenditure of ${amount} reported in the latest update for project "${project_title}".',
                'icon': 'dollar-sign',
                'color': 'orange',
                'default_priority': NotificationPriority.HIGH,
                'send_email': True,
                'send_push': True,
                'can_disable': False
            },
            
            # Media notifications
            {
                'name': 'media_uploaded',
                'description': 'New media has been uploaded',
                'category': NotificationCategory.MEDIA,
                'title_template': 'New Media Uploaded',
                'body_template': 'New ${media_type} has been uploaded to project "${project_title}".',
                'icon': 'image',
                'color': 'blue',
                'default_priority': NotificationPriority.LOW,
                'send_email': False,
                'send_push': False,
                'can_disable': True
            },
            {
                'name': 'deliverable_media_added',
                'description': 'Media representing a deliverable has been uploaded',
                'category': NotificationCategory.MEDIA,
                'title_template': 'Deliverable Added',
                'body_template': 'A deliverable for milestone "${milestone_title}" has been uploaded to project "${project_title}".',
                'icon': 'package',
                'color': 'green',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
                'send_push': False,
                'can_disable': True
            },
            
            # Comment notifications
            {
                'name': 'comment_added',
                'description': 'A new comment has been added',
                'category': NotificationCategory.COMMENT,
                'title_template': 'New Comment',
                'body_template': '${commenter} commented on project "${project_title}": "${comment_preview}"',
                'icon': 'message-square',
                'color': 'blue',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
                'send_push': False,
                'can_disable': True
            },
            {
                'name': 'comment_reply',
                'description': 'Someone replied to your comment',
                'category': NotificationCategory.COMMENT,
                'title_template': 'Reply to Your Comment',
                'body_template': '${commenter} replied to your comment on project "${project_title}": "${comment_preview}"',
                'icon': 'message-circle',
                'color': 'blue',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
                'send_push': True,
                'can_disable': True
            },
            
            # System notifications
            {
                'name': 'weekly_project_summary',
                'description': 'Weekly summary of project activities',
                'category': NotificationCategory.SYSTEM,
                'title_template': 'Weekly Project Summary',
                'body_template': 'Your weekly summary for project "${project_title}" is now available.',
                'icon': 'bar-chart-2',
                'color': 'purple',
                'default_priority': NotificationPriority.NORMAL,
                'send_email': True,
                'send_push': False,
                'can_disable': True
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
        
        self.stdout.write(self.style.SUCCESS(f'Successfully created {created_count} and updated {updated_count} notification types'))
