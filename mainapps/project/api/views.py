from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Avg, Count, Q, F
from django.utils import timezone
from datetime import timedelta
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.decorators import api_view, permission_classes, action
from django.db.models.functions import TruncDate
from rest_framework.viewsets import ReadOnlyModelViewSet
from mainapps.user_profile.api.views import BaseReferenceViewSet
from .notification_utils import (
    notify_project_created, notify_project_status_changed, notify_team_member_added,
    notify_team_member_removed, notify_milestone_created, notify_milestone_assigned,
    notify_milestone_unassigned, notify_milestone_status_changed, notify_milestone_completed,
    notify_expense_created, notify_expense_status_changed, notify_update_created,
    notify_project_budget_updated, notify_project_dates_updated, notify_official_added,
    notify_official_removed, notify_media_uploaded, notify_team_member_role_changed,
    notify_project_approaching_end, notify_project_overbudget, notify_milestone_approaching,
    notify_milestone_overdue, notify_comment_added
)
from ..models import Project, ProjectCategory, DailyProjectUpdate, ProjectUpdateMedia
from .serializers import *
from django.db.models import F, Sum, Count, Avg, Case, When, DecimalField, Value, Q
from decimal import Decimal
from django.http import HttpResponse, FileResponse
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from django.conf import settings


User = get_user_model()

class BaseUserViewSet(ReadOnlyModelViewSet):
    """
    Base Read-only ViewSet for users with dynamic profile filters
    """
    serializer_class = None  # Must be set in child class
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['username', 'email', 'first_name', 'last_name']
    search_fields = ['username', 'email', 'first_name', 'last_name']

    profile_filters = {}

    def get_queryset(self):
        queryset = User.objects.all()

        if self.profile_filters:
            queryset = queryset.filter(profile__isnull=False, profile__kyc_status='approved', **self.profile_filters)
        else:
            queryset = queryset.filter(profile__isnull=False, profile__kyc_status='approved')

        username = self.request.query_params.get('username')
        if username:
            queryset = queryset.filter(username__icontains=username)
        
        email = self.request.query_params.get('email')
        if email:
            queryset = queryset.filter(email__icontains=email)

        return queryset

class CEOUserViewSet(BaseUserViewSet):
    serializer_class = ProjectUserSerializer
    profile_filters = {'profile__is_ceo': True}

    
class TeambleUserViewSet(BaseUserViewSet):
    serializer_class = ProjectUserSerializer
    profile_filters = {'profile__is_ceo': False,'profile__is_DB_admin': False,'profile__is_DB_executive': False,}

    

class AllUserViewSet(BaseUserViewSet):
    serializer_class = ProjectUserSerializer
    # profile_filters = {'is_ceo': True}

    
class ProjectCategoryViewSet(BaseReferenceViewSet):
    """
    ViewSet for ProjectCategory model
    """
    queryset = ProjectCategory.objects.all()
    serializer_class = ProjectCategorySerializer
    search_fields = ['name']


class ProjectViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Project model with additional actions
    """
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['project_type', 'status', 'category']
    search_fields = ['title', 'description', 'location']
    ordering_fields = ['created_at', 'start_date', 'target_end_date', 'budget', 'status']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return ProjectListSerializer
        return ProjectSerializer
    
    def get_queryset(self):
        """
        Customize queryset based on query parameters and annotate with calculated fields
        """
        # Annotate queryset with calculated fields
        queryset = Project.objects.annotate(
            calculated_funds_spent=Sum(
                Case(
                    When(expenses__status='reimbursed', then='expenses__amount'),
                    default=Value(Decimal('0.00')),
                    output_field=DecimalField()
                )
            ),
            calculated_funds_allocated=Case(
                When(full_budget_disbursed=True, then=F('budget')),
                default=Sum(
                    Case(
                        When(expenses__status='reimbursed', then='expenses__amount'),
                        default=Value(Decimal('0.00')),
                        output_field=DecimalField()
                    )
                ),
                output_field=DecimalField()
            )
        )
        
        # Filter by manager
        manager_id = self.request.query_params.get('manager_id')
        if manager_id:
            queryset = queryset.filter(manager_id=manager_id)
        
        # Filter by official
        official_id = self.request.query_params.get('official_id')
        if official_id:
            queryset = queryset.filter(officials__id=official_id)
        
        # Filter by date range
        start_after = self.request.query_params.get('start_after')
        start_before = self.request.query_params.get('start_before')
        end_after = self.request.query_params.get('end_after')
        end_before = self.request.query_params.get('end_before')
        
        if start_after:
            queryset = queryset.filter(start_date__gte=start_after)
        if start_before:
            queryset = queryset.filter(start_date__lte=start_before)
        if end_after:
            queryset = queryset.filter(target_end_date__gte=end_after)
        if end_before:
            queryset = queryset.filter(target_end_date__lte=end_before)
        
        # Filter by budget range
        min_budget = self.request.query_params.get('min_budget')
        max_budget = self.request.query_params.get('max_budget')
        
        if min_budget:
            queryset = queryset.filter(budget__gte=min_budget)
        if max_budget:
            queryset = queryset.filter(budget__lte=max_budget)
        
        # Filter overbudget projects - now using calculated_funds_spent
        overbudget = self.request.query_params.get('overbudget')
        if overbudget and overbudget.lower() == 'true':
            queryset = queryset.filter(calculated_funds_spent__gt=F('budget'))
        
        # Filter delayed projects
        delayed = self.request.query_params.get('delayed')
        if delayed and delayed.lower() == 'true':
            today = timezone.now().date()
            queryset = queryset.filter(
                target_end_date__lt=today,
                status__in=['planning', 'active', 'on_hold']
            )
        
        return queryset
    
    def perform_create(self, serializer):
        """Set current user as creator if not specified"""
        serializer.save()
        instance = serializer.instance
        instance.created_by = self.request.user
        instance.save()
        
        # Send notification for project creation
        notify_project_created(instance)
        
        # Check for approaching end date
        today = timezone.now().date()
        if instance.target_end_date:
            days_remaining = (instance.target_end_date - today).days
            if 0 < days_remaining <= 7:
                notify_project_approaching_end(instance, days_remaining)
    
    @action(detail=False, methods=['get'])
    def assigned(self, request):
        """Get projects assigned to the current user (as official)"""
        projects = self.get_queryset().filter(officials=request.user)
        serializer = self.get_serializer(projects, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def created(self, request):
        """Get projects created by the current user"""
        projects = self.get_queryset().filter(created_by=request.user)
        serializer = self.get_serializer(projects, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def managed(self, request):
        """Get projects managed by the current user"""
        projects = self.get_queryset().filter(manager=request.user)
        serializer = self.get_serializer(projects, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        """Update project status"""
        project = self.get_object()
        serializer = ProjectStatusUpdateSerializer(data=request.data)
        
        if serializer.is_valid():
            old_status = project.status
            new_status = serializer.validated_data['status']
            notes = serializer.validated_data.get('notes', '')
            
            # If completing a project, set actual end date
            if new_status == 'completed' and project.status != 'completed':
                project.actual_end_date = timezone.now().date()
            
            # Update project
            project.status = new_status
            if notes:
                project.notes = (project.notes or '') + f"\n\nStatus changed to {new_status} on {timezone.now().date()}: {notes}"
            
            project.save()
            
            # Send notification for status change
            notify_project_status_changed(project, old_status, new_status, request.user)
            
            return Response(ProjectSerializer(project).data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['patch'])
    def update_budget(self, request, pk=None):
        """Update project budget information"""
        project = self.get_object()
        serializer = ProjectBudgetUpdateSerializer(data=request.data)
        
        if serializer.is_valid():
            data = serializer.validated_data
            notes = data.get('notes', '')
            old_budget = project.budget
            
            # Update budget field if provided
            if 'budget' in data:
                project.budget = data['budget']
            
            # Update full_budget_disbursed flag if provided
            if 'full_budget_disbursed' in data:
                project.full_budget_disbursed = data['full_budget_disbursed']
            
            # Add note about budget update
            if notes:
                project.notes = (project.notes or '') + f"\n\nBudget updated on {timezone.now().date()}: {notes}"
            
            project.save()
            
            # Send notification for budget update
            if 'budget' in data and old_budget != project.budget:
                notify_project_budget_updated(project, old_budget, project.budget, request.user)
            
            # Check if project is over budget
            funds_spent = project.funds_spent
            if funds_spent > project.budget:
                notify_project_overbudget(project, funds_spent, project.budget)
            
            return Response(ProjectSerializer(project).data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['patch'])
    def update_dates(self, request, pk=None):
        """Update project dates"""
        project = self.get_object()
        serializer = ProjectDateUpdateSerializer(data=request.data)
        
        if serializer.is_valid():
            data = serializer.validated_data
            notes = data.get('notes', '')
            
            # Track date changes for notifications
            date_changes = []
            
            # Update start_date if provided
            if 'start_date' in data:
                old_date = project.start_date
                project.start_date = data['start_date']
                if old_date != project.start_date:
                    date_changes.append(('start_date', old_date, project.start_date))
            
            # Update target_end_date if provided
            if 'target_end_date' in data:
                old_date = project.target_end_date
                project.target_end_date = data['target_end_date']
                if old_date != project.target_end_date:
                    date_changes.append(('target_end_date', old_date, project.target_end_date))
            
            # Update actual_end_date if provided
            if 'actual_end_date' in data:
                old_date = project.actual_end_date
                project.actual_end_date = data['actual_end_date']
                if old_date != project.actual_end_date:
                    date_changes.append(('actual_end_date', old_date, project.actual_end_date))
            
            # Add note about date update
            if notes:
                project.notes = (project.notes or '') + f"\n\nDates updated on {timezone.now().date()}: {notes}"
            
            project.save()
            
            # Send notifications for date changes
            for field, old_date, new_date in date_changes:
                notify_project_dates_updated(project, field, old_date, new_date, request.user)
            
            # Check for approaching end date
            today = timezone.now().date()
            if project.target_end_date:
                days_remaining = (project.target_end_date - today).days
                if 0 < days_remaining <= 7:
                    notify_project_approaching_end(project, days_remaining)
            
            return Response(ProjectSerializer(project).data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def add_official(self, request, pk=None):
        """Add an official to the project"""
        project = self.get_object()
        serializer = ProjectOfficialSerializer(data=request.data)
        
        if serializer.is_valid():
            user_id = serializer.validated_data['user_id']
            
            # Check if user exists
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            try:
                user = User.objects.get(pk=user_id)
                project.officials.add(user)
                
                # Send notification for official added
                notify_official_added(project, user, request.user)
                
                return Response({'status': 'official added'})
            except User.DoesNotExist:
                return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def remove_official(self, request, pk=None):
        """Remove an official from the project"""
        project = self.get_object()
        serializer = ProjectOfficialSerializer(data=request.data)
        
        if serializer.is_valid():
            user_id = serializer.validated_data['user_id']
            
            # Check if user exists
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            try:
                user = User.objects.get(pk=user_id)
                project.officials.remove(user)
                
                # Send notification for official removed
                notify_official_removed(project, user, request.user)
                
                return Response({'status': 'official removed'})
            except User.DoesNotExist:
                return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False)
    def statistics(self, request):
        """Get project statistics"""
        base_queryset = self.get_queryset()
        
        # Get full status counts (including all statuses)
        status_counts = dict(
            base_queryset.values('status')
            .annotate(count=Count('id'))
            .values_list('status', 'count')
        )
        
        # Create filtered queryset excluding submitted/cancelled projects
        filtered_queryset = base_queryset.exclude(
            status__in=['submitted', 'cancelled','rejected']
        )
        
        # Financial calculations using filtered queryset
        budget_stats = filtered_queryset.aggregate(
            total_budget=Sum('budget'),
            total_allocated=Sum('calculated_funds_allocated'),
            total_spent=Sum('calculated_funds_spent'),
            avg_budget=Avg('budget')
        )
        
        # Timeline statistics using filtered queryset
        today = timezone.now().date()
        active_projects = filtered_queryset.filter(status='active').count()
        delayed_projects = filtered_queryset.filter(
            target_end_date__lt=today,
            status__in=['planning', 'active', 'on_hold']
        ).count()
        completed_on_time = filtered_queryset.filter(
            status='completed',
            actual_end_date__lte=F('target_end_date')
        ).count()
        completed_late = filtered_queryset.filter(
            status='completed',
            actual_end_date__gt=F('target_end_date')
        ).count()
        
        # Type and category counts using filtered queryset
        type_counts = dict(
            filtered_queryset.values('project_type')
            .annotate(count=Count('id'))
            .values_list('project_type', 'count')
        )
        
        category_counts = dict(
            filtered_queryset.values('category__name')
            .annotate(count=Count('id'))
            .values_list('category__name', 'count')
        )
        
        return Response({
            'status_counts': status_counts,
            'type_counts': type_counts,
            'budget_stats': budget_stats,
            'timeline_stats': {
                'active_projects': active_projects,
                'delayed_projects': delayed_projects,
                'completed_on_time': completed_on_time,
                'completed_late': completed_late,
            },
            'category_counts': category_counts
        })


class ProjectTeamMemberViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing project team members
    """
    serializer_class = ProjectTeamMemberSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'role']
    ordering_fields = ['join_date', 'role', 'created_at']
    
    def get_queryset(self):
        """
        This view returns team members based on query parameters
        """
        queryset = ProjectTeamMember.objects.all()
        
        # Filter by project if project_id is provided
        project_id = self.request.query_params.get('project_id')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
            
        # Filter by user if user_id is provided
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
            
        # Filter by role if role is provided
        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)
            
        return queryset
    
    def get_serializer_class(self):
        """
        Use different serializers for different actions
        """
        if self.action in ['create', 'update', 'partial_update']:
            return ProjectTeamMemberCreateSerializer
        return ProjectTeamMemberSerializer
    
    def perform_create(self, serializer):
        """
        Set created_by to current user when creating a team member
        """
        team_member = serializer.save()
        
        # Send notification for team member added
        notify_team_member_added(team_member)
    
    def perform_destroy(self, instance):
        """
        Send notification before deleting team member
        """
        project = instance.project
        user = instance.user
        role = dict(instance.ROLE_CHOICES).get(instance.role, instance.role)
        
        # Delete the instance
        instance.delete()
        
        # Send notification for team member removed
        notify_team_member_removed(project, user, role)
    
    @action(detail=False, methods=['get'])
    def by_project(self, request):
        """
        Get all team members for a specific project
        """
        project_id = request.query_params.get('project_id')
        if not project_id:
            return Response(
                {"detail": "project_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        project = get_object_or_404(Project, id=project_id)
        team_members = ProjectTeamMember.objects.filter(project=project)
        serializer = self.get_serializer(team_members, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_user(self, request):
        """
        Get all project roles for a specific user
        """
        user_id = request.query_params.get('user_id')
        if not user_id:
            # Default to current user if no user_id provided
            user = request.user
        else:
            user = get_object_or_404(User, id=user_id)
            
        team_roles = ProjectTeamMember.objects.filter(user=user)
        serializer = self.get_serializer(team_roles, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_role(self, request):
        """
        Get all team members with a specific role
        """
        role = request.query_params.get('role')
        if not role:
            return Response(
                {"detail": "role is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        team_members = ProjectTeamMember.objects.filter(role=role)
        serializer = self.get_serializer(team_members, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def active_members(self, request):
        """
        Get all active team members (no end_date or end_date in future)
        """
        from django.utils import timezone
        today = timezone.now().date()
        
        team_members = ProjectTeamMember.objects.filter(
            Q(end_date__isnull=True) | Q(end_date__gt=today)
        )
        
        # Filter by project if provided
        project_id = request.query_params.get('project_id')
        if project_id:
            team_members = team_members.filter(project_id=project_id)
            
        serializer = self.get_serializer(team_members, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def extend_membership(self, request, pk=None):
        """
        Extend the end_date of a team member
        """
        team_member = self.get_object()
        new_end_date = request.data.get('end_date')
        
        if not new_end_date:
            return Response(
                {"detail": "end_date is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        team_member.end_date = new_end_date
        team_member.save()
        
        serializer = self.get_serializer(team_member)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def change_role(self, request, pk=None):
        """
        Change the role of a team member
        """
        team_member = self.get_object()
        new_role = request.data.get('role')
        
        if not new_role:
            return Response(
                {"detail": "role is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Validate that the role is one of the allowed choices
        valid_roles = [choice[0] for choice in ProjectTeamMember.ROLE_CHOICES]
        if new_role not in valid_roles:
            return Response(
                {"detail": f"Invalid role. Must be one of: {', '.join(valid_roles)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        old_role = team_member.role
        team_member.role = new_role
        team_member.save()
        
        # Send notification for role change
        notify_team_member_role_changed(team_member, old_role, new_role, request.user)
        
        serializer = self.get_serializer(team_member)
        return Response(serializer.data)

class ProjectMilestoneViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing project milestones
    """
    serializer_class = ProjectMilestoneSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description', 'status', 'priority']
    ordering_fields = ['due_date', 'priority', 'status', 'created_at', 'completion_percentage']
    
    def get_queryset(self):
        """
        This view returns milestones based on query parameters
        """
        queryset = ProjectMilestone.objects.all()
        
        # Filter by project if project_id is provided
        project_id = self.request.query_params.get('project_id')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
            
        # Filter by status if status is provided
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)
            
        # Filter by priority if priority is provided
        priority = self.request.query_params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)
            
        # Filter by assigned user if user_id is provided
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(assigned_to__id=user_id)
            
        # Filter by due date range
        due_date_start = self.request.query_params.get('due_date_start')
        due_date_end = self.request.query_params.get('due_date_end')
        
        if due_date_start:
            queryset = queryset.filter(due_date__gte=due_date_start)
        
        if due_date_end:
            queryset = queryset.filter(due_date__lte=due_date_end)
            
        # Filter overdue milestones
        is_overdue = self.request.query_params.get('is_overdue')
        if is_overdue and is_overdue.lower() == 'true':
            today = timezone.now().date()
            queryset = queryset.filter(
                Q(due_date__lt=today) & 
                ~Q(status='completed')
            )
            
        return queryset
    
    def get_serializer_class(self):
        """
        Use different serializers for different actions
        """
        if self.action in ['create', 'update', 'partial_update']:
            return ProjectMilestoneCreateUpdateSerializer
        return ProjectMilestoneSerializer
    
    def perform_create(self, serializer):
        """
        Set created_by to current user when creating a milestone
        """
        milestone = serializer.save(created_by=self.request.user)
        
        # Send notification for milestone created
        notify_milestone_created(milestone)
        
        # Send notifications for assigned users
        for user in milestone.assigned_to.all():
            notify_milestone_assigned(milestone, user)
        
        # Check for approaching due date
        today = timezone.now().date()
        days_remaining = (milestone.due_date - today).days
        if 0 < days_remaining <= 7:
            notify_milestone_approaching(milestone, days_remaining)
        elif days_remaining < 0:
            notify_milestone_overdue(milestone)
    
    def perform_update(self, serializer):
        """
        Handle notifications when updating a milestone
        """
        milestone = self.get_object()
        old_assigned_users = set(milestone.assigned_to.all())
        
        # Save the updated milestone
        updated_milestone = serializer.save()
        
        # Check for changes in assigned users
        new_assigned_users = set(updated_milestone.assigned_to.all())
        
        # Users who were added
        for user in new_assigned_users - old_assigned_users:
            notify_milestone_assigned(updated_milestone, user)
        
        # Users who were removed
        for user in old_assigned_users - new_assigned_users:
            notify_milestone_unassigned(updated_milestone, user)
        
        # Check for approaching due date
        today = timezone.now().date()
        days_remaining = (updated_milestone.due_date - today).days
        if 0 < days_remaining <= 7:
            notify_milestone_approaching(updated_milestone, days_remaining)
        elif days_remaining < 0 and updated_milestone.status != 'completed':
            notify_milestone_overdue(updated_milestone)
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """
        Mark a milestone as completed
        """
        milestone = self.get_object()
        completion_date = request.data.get('completion_date')
        
        if completion_date:
            try:
                from datetime import datetime
                completion_date = datetime.strptime(completion_date, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {"detail": "Invalid date format. Use YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            completion_date = timezone.now().date()
            
        milestone.complete_milestone(completion_date)
        tasks = milestone.tasks.filter(parent__isnull=True)
        for task in tasks:
            task.update_status('completed')
        
        # Send notification for milestone completed
        notify_milestone_completed(milestone, request.user)

        serializer = self.get_serializer(milestone)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """
        Update the status of a milestone
        """
        milestone = self.get_object()
        new_status = request.data.get('status')
        
        if not new_status:
            return Response(
                {"detail": "Status is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Validate that the status is one of the allowed choices
        valid_statuses = [choice[0] for choice in ProjectMilestone.STATUS_CHOICES]
        if new_status not in valid_statuses:
            return Response(
                {"detail": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        old_status = milestone.status
            
        # If marking as completed, set completion date and percentage
        if new_status == 'completed' and milestone.status != 'completed':
            milestone.completion_date = timezone.now().date()
            milestone.completion_percentage = 100
            tasks = milestone.tasks.filter(parent__isnull=True)
            for task in tasks:
                task.update_status('completed')
            
            # Will send completed notification
            notify_milestone_completed(milestone, request.user)
        
        milestone.status = new_status
        milestone.save()
        
        # Send notification for status change (if not completed, as we already sent that)
        if new_status != 'completed' or old_status == 'completed':
            notify_milestone_status_changed(milestone, old_status, new_status, request.user)
        
        serializer = self.get_serializer(milestone)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def update_percentage(self, request, pk=None):
        """
        Update the completion percentage of a milestone
        """
        milestone = self.get_object()
        try:
            percentage = int(request.data.get('completion_percentage', 0))
        except ValueError:
            return Response(
                {"detail": "Completion percentage must be an integer"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if percentage < 0 or percentage > 100:
            return Response(
                {"detail": "Completion percentage must be between 0 and 100"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        old_status = milestone.status
            
        # If setting to 100%, also mark as completed
        if percentage == 100 and milestone.status != 'completed':
            milestone.status = 'completed'
            milestone.completion_date = timezone.now().date()
            
            # Will send completed notification
            notify_milestone_completed(milestone, request.user)
            
        milestone.completion_percentage = percentage
        milestone.save()
        
        # Send notification for status change if it changed and not to completed
        if old_status != milestone.status and milestone.status != 'completed':
            notify_milestone_status_changed(milestone, old_status, milestone.status, request.user)
        
        serializer = self.get_serializer(milestone)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def assign_users(self, request, pk=None):
        """
        Assign users to a milestone
        """
        milestone = self.get_object()
        user_ids = request.data.get('user_ids', [])
        
        if not isinstance(user_ids, list):
            return Response(
                {"detail": "user_ids must be a list of integers"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get current assigned users
        old_assigned_users = set(milestone.assigned_to.all())
            
        # Get valid users
        users = User.objects.filter(id__in=user_ids)
        
        # Set the assigned users
        milestone.assigned_to.set(users)
        
        # Get new assigned users
        new_assigned_users = set(users)
        
        # Send notifications for newly assigned users
        for user in new_assigned_users - old_assigned_users:
            notify_milestone_assigned(milestone, user)
        
        # Send notifications for unassigned users
        for user in old_assigned_users - new_assigned_users:
            notify_milestone_unassigned(milestone, user)
        
        serializer = self.get_serializer(milestone)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_project(self, request):
        """
        Get all milestones for a specific project
        """
        project_id = request.query_params.get('project_id')
        if not project_id:
            return Response(
                {"detail": "project_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        project = get_object_or_404(Project, id=project_id)
        milestones = ProjectMilestone.objects.filter(project=project)
        serializer = self.get_serializer(milestones, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_user(self, request):
        """
        Get all milestones assigned to a specific user
        """
        user_id = request.query_params.get('user_id')
        if not user_id:
            # Default to current user if no user_id provided
            user = request.user
        else:
            user = get_object_or_404(User, id=user_id)
            
        milestones = ProjectMilestone.objects.filter(assigned_to=user)
        serializer = self.get_serializer(milestones, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """
        Get upcoming milestones (due in the next 30 days)
        """
        today = timezone.now().date()
        thirty_days_later = today + timezone.timedelta(days=30)
        
        milestones = ProjectMilestone.objects.filter(
            due_date__gte=today,
            due_date__lte=thirty_days_later,
            status__in=['pending', 'in_progress']
        )
        
        # Filter by project if provided
        project_id = request.query_params.get('project_id')
        if project_id:
            milestones = milestones.filter(project_id=project_id)
            
        # Filter by user if provided
        user_id = request.query_params.get('user_id')
        if user_id:
            milestones = milestones.filter(assigned_to__id=user_id)
            
        serializer = self.get_serializer(milestones, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """
        Get overdue milestones
        """
        today = timezone.now().date()
        
        milestones = ProjectMilestone.objects.filter(
            due_date__lt=today,
            status__in=['pending', 'in_progress', 'delayed']
        )
        
        # Filter by project if provided
        project_id = request.query_params.get('project_id')
        if project_id:
            milestones = milestones.filter(project_id=project_id)
            
        # Filter by user if provided
        user_id = request.query_params.get('user_id')
        if user_id:
            milestones = milestones.filter(assigned_to__id=user_id)
            
        serializer = self.get_serializer(milestones, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get milestone statistics
        """
        # Filter by project if provided
        project_id = request.query_params.get('project_id')
        queryset = ProjectMilestone.objects.all()
        
        if project_id:
            queryset = queryset.filter(project_id=project_id)
            
        # Count milestones by status
        status_counts = queryset.values('status').annotate(count=Count('id'))
        
        # Count milestones by priority
        priority_counts = queryset.values('priority').annotate(count=Count('id'))
        
        # Calculate average completion percentage
        avg_completion = queryset.aggregate(avg_completion=Avg('completion_percentage'))
        
        # Count overdue milestones
        today = timezone.now().date()
        overdue_count = queryset.filter(
            due_date__lt=today,
            status__in=['pending', 'in_progress', 'delayed']
        ).count()
        
        # Count upcoming milestones (next 30 days)
        thirty_days_later = today + timezone.timedelta(days=30)
        upcoming_count = queryset.filter(
            due_date__gte=today,
            due_date__lte=thirty_days_later,
            status__in=['pending', 'in_progress']
        ).count()
        
        # Count milestones by assignee
        assignee_counts = queryset.values(
            'assigned_to__id', 
            'assigned_to__username',
            'assigned_to__first_name',
            'assigned_to__last_name'
        ).annotate(count=Count('id'))
        
        return Response({
            'total_milestones': queryset.count(),
            'status_counts': status_counts,
            'priority_counts': priority_counts,
            'avg_completion': avg_completion,
            'overdue_count': overdue_count,
            'upcoming_count': upcoming_count,
            'assignee_counts': assignee_counts
        })

    @action(detail=False, methods=['get'], url_path='user-milestones')
    def user_milestones(self, request):
        """
        Get all milestones for projects that the user is related to
        """
        user = request.user
        
        # Get all projects where the user has any relationship
        user_projects = Project.objects.filter(
            Q(manager=user) |  # User is manager
            Q(officials=user) |  # User is an official
            Q(created_by=user) |  # User created the project
            Q(team_members__user=user)  # User is a team member
        ).distinct()
        
        # Get all milestones for these projects
        milestones = ProjectMilestone.objects.filter(
            project__in=user_projects
        ).select_related(
            'project', 'created_by'
        ).prefetch_related(
            'assigned_to', 'dependencies'
        )
        
        # Apply additional filters if provided
        status = request.query_params.get('status')
        if status:
            milestones = milestones.filter(status=status)
            
        priority = request.query_params.get('priority')
        if priority:
            milestones = milestones.filter(priority=priority)
            
        overdue = request.query_params.get('overdue')
        if overdue and overdue.lower() == 'true':
            milestones = milestones.filter(due_date__lt=timezone.now().date(), status__in=['not_started', 'in_progress', 'delayed'])
            
        # Order by due date by default
        milestones = milestones.order_by('due_date')
        
        serializer = ProjectMilestoneSerializer(milestones, many=True, context={'request': request})
        return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_project_team_members(request):
    """
    Get all users who are team members of a specific project
    """
    project_id = request.query_params.get('project_id')
    if not project_id:
        return Response(
            {"detail": "project_id is required"},
            status=status.HTTP_400_BAD_REQUEST
        )
        
    project = get_object_or_404(Project, id=project_id)
    
    # Get all team members for the project
    team_members = ProjectTeamMember.objects.filter(project=project)
    
    # Extract the users from the team members
    users = [team_member.user for team_member in team_members]
    
    
    serializer = ProjectUserSerializer(users, many=True)
    return Response(serializer.data)


class ProjectExpenseViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing project expenses
    """
    serializer_class = ProjectExpenseSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description', 'category', 'status']
    ordering_fields = ['date_incurred', 'amount', 'status', 'created_at']
    
    def get_queryset(self):
        """
        This view returns expenses based on query parameters
        """
        queryset = ProjectExpense.objects.all()
        
        # Filter by project if project_id is provided
        project_id = self.request.query_params.get('project_id')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
            
        # Filter by update if update_id is provided
        update_id = self.request.query_params.get('update_id')
        if update_id:
            queryset = queryset.filter(update_id=update_id)
            
        # Filter by status if status is provided
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)
            
        # Filter by category if category is provided
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
            
        # Filter by incurred_by if user_id is provided
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(incurred_by_id=user_id)
            
        # Filter by approved_by if approved_by_id is provided
        approved_by_id = self.request.query_params.get('approved_by_id')
        if approved_by_id:
            queryset = queryset.filter(approved_by_id=approved_by_id)
            
        # Filter by date range
        date_start = self.request.query_params.get('date_start')
        date_end = self.request.query_params.get('date_end')
        
        if date_start:
            queryset = queryset.filter(date_incurred__gte=date_start)
        
        if date_end:
            queryset = queryset.filter(date_incurred__lte=date_end)
            
        # Filter by amount range
        amount_min = self.request.query_params.get('amount_min')
        amount_max = self.request.query_params.get('amount_max')
        
        if amount_min:
            queryset = queryset.filter(amount__gte=amount_min)
        
        if amount_max:
            queryset = queryset.filter(amount__lte=amount_max)
            
        return queryset
    
    def get_serializer_class(self):
        """
        Use different serializers for different actions
        """
        if self.action in ['create', 'update', 'partial_update']:
            return ProjectExpenseCreateUpdateSerializer
        elif self.action == 'approve' or self.action == 'reject':
            return ExpenseApprovalSerializer
        elif self.action == 'reimburse':
            return ExpenseReimbursementSerializer
        return ProjectExpenseSerializer
    
    def perform_create(self, serializer):
        """
        Set incurred_by to current user if not provided
        """
        if 'incurred_by' not in serializer.validated_data:
            expense = serializer.save(incurred_by=self.request.user, created_by=self.request.user)
        else:
            expense = serializer.save()
        
        # Send notification for expense created
        notify_expense_created(expense)
        
        # Check if project is over budget
        project = expense.project
        funds_spent = project.funds_spent
        if funds_spent > project.budget:
            notify_project_overbudget(project, funds_spent, project.budget)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """
        Approve an expense
        """
        expense = self.get_object()
        
        # Check if expense is already approved or reimbursed
        if expense.status in ['approved', 'reimbursed']:
            return Response(
                {"detail": f"Expense is already {expense.status}."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Check if expense is rejected
        if expense.status == 'rejected':
            return Response(
                {"detail": "Cannot approve a rejected expense."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        old_status = expense.status
        
        # Update expense
        expense.status = 'approved'
        expense.approved_by = request.user
        expense.approval_date = timezone.now().date()
        
        # Add notes if provided
        if 'notes' in serializer.validated_data and serializer.validated_data['notes']:
            if expense.notes:
                expense.notes += f"\n\nApproval notes: {serializer.validated_data['notes']}"
            else:
                expense.notes = f"Approval notes: {serializer.validated_data['notes']}"
                
        expense.save()
        
        # Send notification for expense status change
        notify_expense_status_changed(expense, old_status, 'approved', request.user)
        
        # Return updated expense
        response_serializer = ProjectExpenseSerializer(expense, context={'request': request})
        return Response(response_serializer.data)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """
        Reject an expense
        """
        expense = self.get_object()
        
        # Check if expense is already approved or reimbursed
        if expense.status in ['approved', 'reimbursed']:
            return Response(
                {"detail": f"Expense is already {expense.status}."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Check if expense is already rejected
        if expense.status == 'rejected':
            return Response(
                {"detail": "Expense is already rejected."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        old_status = expense.status
        
        # Update expense
        expense.status = 'rejected'
        expense.approved_by = request.user
        expense.approval_date = timezone.now().date()
        
        # Add notes if provided
        if 'notes' in serializer.validated_data and serializer.validated_data['notes']:
            if expense.notes:
                expense.notes += f"\n\nRejection notes: {serializer.validated_data['notes']}"
            else:
                expense.notes = f"Rejection notes: {serializer.validated_data['notes']}"
                
        expense.save()
        
        # Send notification for expense status change
        notify_expense_status_changed(expense, old_status, 'rejected', request.user)
        
        # Return updated expense
        response_serializer = ProjectExpenseSerializer(expense, context={'request': request})
        return Response(response_serializer.data)
    
    @action(detail=True, methods=['post'])
    def reimburse(self, request, pk=None):
        """
        Mark an expense as reimbursed
        """
        expense = self.get_object()
        
        # Check if expense is approved
        if expense.status != 'approved':
            return Response(
                {"detail": "Only approved expenses can be marked as reimbursed."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        old_status = expense.status
        
        # Update expense
        expense.status = 'reimbursed'
        
        # Add notes if provided
        if 'notes' in serializer.validated_data and serializer.validated_data['notes']:
            if expense.notes:
                expense.notes += f"\n\nReimbursement notes: {serializer.validated_data['notes']}"
            else:
                expense.notes = f"Reimbursement notes: {serializer.validated_data['notes']}"
                
        expense.save()
        
        # Send notification for expense status change
        notify_expense_status_changed(expense, old_status, 'reimbursed', request.user)
        
        # Return updated expense
        response_serializer = ProjectExpenseSerializer(expense, context={'request': request})
        return Response(response_serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_project(self, request, project_id=None):
        """
        Get all expenses for a specific project
        """
        if not project_id:
            project_id = request.query_params.get('project_id')
            if not project_id:
                return Response(
                    {"detail": "project_id is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
        project = get_object_or_404(Project, id=project_id)
        expenses = ProjectExpense.objects.filter(project=project)
        
        # Apply additional filters
        status_filter = request.query_params.get('status')
        if status_filter:
            expenses = expenses.filter(status=status_filter)
            
        serializer = self.get_serializer(expenses, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_user(self, request):
        """
        Get all expenses incurred by a specific user
        """
        user_id = request.query_params.get('user_id')
        if not user_id:
            # Default to current user if no user_id provided
            user = request.user
        else:
            user = get_object_or_404(User, id=user_id)
            
        expenses = ProjectExpense.objects.filter(incurred_by=user)
        
        # Apply additional filters
        status_filter = request.query_params.get('status')
        if status_filter:
            expenses = expenses.filter(status=status_filter)
            
        serializer = self.get_serializer(expenses, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def pending_approval(self, request):
        """
        Get all expenses pending approval
        """
        expenses = ProjectExpense.objects.filter(status='pending')
        
        # Filter by project if provided
        project_id = request.query_params.get('project_id')
        if project_id:
            expenses = expenses.filter(project_id=project_id)
            
        serializer = self.get_serializer(expenses, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get expense statistics
        """
        # Filter by project if provided
        project_id = request.query_params.get('project_id')
        queryset = ProjectExpense.objects.all()
        
        if project_id:
            queryset = queryset.filter(project_id=project_id)
            
        # Count expenses by status
        status_counts = queryset.values('status').annotate(count=Count('id'), total=Sum('amount'))
        
        # Count expenses by category
        category_counts = queryset.values('category').annotate(count=Count('id'), total=Sum('amount'))
        
        # Calculate total expenses
        total_expenses = queryset.aggregate(
            total=Sum('amount', filter=~Q(status='rejected')),  # Exclude rejected from total
            pending=Sum('amount', filter=Q(status='pending')),
            approved=Sum('amount', filter=Q(status__in=['approved', 'reimbursed'])),
            rejected=Sum('amount', filter=Q(status='rejected')),
            reimbursed=Sum('amount', filter=Q(status='reimbursed'))
        )
        
        # Expenses by month
        from django.db.models.functions import TruncMonth
        expenses_by_month = queryset.annotate(
            month=TruncMonth('date_incurred')
        ).values('month').annotate(
            count=Count('id'),
            total=Sum('amount')
        ).order_by('month')
        
        # Expenses by user
        expenses_by_user = queryset.values(
            'incurred_by__id',
            'incurred_by__username',
            'incurred_by__first_name',
            'incurred_by__last_name'
        ).annotate(
            count=Count('id'),
            total=Sum('amount')
        )
           
        return Response({
            'total_expenses': total_expenses,
            'status_counts': status_counts,
            'category_counts': category_counts,
            'expenses_by_month': expenses_by_month,
            'expenses_by_user': expenses_by_user
        })

class DailyProjectUpdateViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing daily project updates
    """
    serializer_class = DailyProjectUpdateSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['summary', 'challenges', 'achievements', 'next_steps']
    ordering_fields = ['date', 'funds_spent_today', 'created_at']
    
    def get_queryset(self):
        """
        This view returns updates based on query parameters
        """
        queryset = DailyProjectUpdate.objects.all()
        
        # Filter by project if project_id is provided
        project_id = self.request.query_params.get('project_id')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
            
        # Filter by submitted_by if user_id is provided
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(submitted_by_id=user_id)
            
        # Filter by date range
        date_start = self.request.query_params.get('date_start')
        date_end = self.request.query_params.get('date_end')
        
        if date_start:
            queryset = queryset.filter(date__gte=date_start)
        
        if date_end:
            queryset = queryset.filter(date__lte=date_end)
            
        # Filter by funds spent range
        funds_min = self.request.query_params.get('funds_min')
        funds_max = self.request.query_params.get('funds_max')
        
        if funds_min:
            queryset = queryset.filter(funds_spent_today__gte=funds_min)
        
        if funds_max:
            queryset = queryset.filter(funds_spent_today__lte=funds_max)
            
        # Filter by has_media
        has_media = self.request.query_params.get('has_media')
        if has_media and has_media.lower() == 'true':
            queryset = queryset.filter(media_files__isnull=False).distinct()
            
        return queryset
    
    def get_serializer_class(self):
        """
        Use different serializers for different actions
        """
        if self.action in ['create', 'update', 'partial_update']:
            return DailyProjectUpdateCreateUpdateSerializer
        return DailyProjectUpdateSerializer
    
    def perform_create(self, serializer):
        """
        Set submitted_by to current user if not provided
        """
        if 'submitted_by' not in serializer.validated_data:
            update = serializer.save(submitted_by=self.request.user)
        else:
            update = serializer.save()
        
        # Send notification for update created
        notify_update_created(update)
        
        # Check if project is over budget due to funds spent today
        project = update.project
        funds_spent = project.funds_spent
        if funds_spent > project.budget:
            notify_project_overbudget(project, funds_spent, project.budget)
    
    @action(detail=False, methods=['get'])
    def by_project(self, request, project_id=None):
        """
        Get all updates for a specific project
        """
        # If project_id is not provided in the URL, check query params
        if project_id is None:
            project_id = request.query_params.get('project_id')
            
        if not project_id:
            return Response(
                {"detail": "project_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        project = get_object_or_404(Project, id=project_id)
        updates = DailyProjectUpdate.objects.filter(project=project)
        
        # Apply additional filters
        date_start = request.query_params.get('date_start')
        date_end = request.query_params.get('date_end')
        
        if date_start:
            updates = updates.filter(date__gte=date_start)
        
        if date_end:
            updates = updates.filter(date__lte=date_end)
        
        serializer = self.get_serializer(updates, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_user(self, request):
        """
        Get all updates submitted by a specific user
        """
        user_id = request.query_params.get('user_id')
        if not user_id:
            # Default to current user if no user_id provided
            user = request.user
        else:
            user = get_object_or_404(User, id=user_id)
            
        updates = DailyProjectUpdate.objects.filter(submitted_by=user)
        
        # Apply additional filters
        project_id = request.query_params.get('project_id')
        if project_id:
            updates = updates.filter(project_id=project_id)
            
        serializer = self.get_serializer(updates, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """
        Get recent updates (last 7 days)
        """
        today = timezone.now().date()
        seven_days_ago = today - timezone.timedelta(days=7)
        
        updates = DailyProjectUpdate.objects.filter(date__gte=seven_days_ago)
        
        # Filter by project if provided
        project_id = request.query_params.get('project_id')
        if project_id:
            updates = updates.filter(project_id=project_id)
            
        serializer = self.get_serializer(updates, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def today(self, request):
        """
        Get today's updates
        """
        today = timezone.now().date()
        
        updates = DailyProjectUpdate.objects.filter(date=today)
        
        # Filter by project if provided
        project_id = request.query_params.get('project_id')
        if project_id:
            updates = updates.filter(project_id=project_id)
            
        serializer = self.get_serializer(updates, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get update statistics including current week's updates
        """
        from django.utils import timezone
        from datetime import timedelta

        project_id = request.query_params.get('project_id')
        queryset = DailyProjectUpdate.objects.all()
        
        if project_id:
            queryset = queryset.filter(project_id=project_id)
            
        # Calculate current week range (Monday to Sunday)
        today = timezone.now().date()
        start_of_week = today - timedelta(days=today.weekday())  # Monday
        end_of_week = start_of_week + timedelta(days=6)         # Sunday

        # Get updates count for current week
        updates_this_week = queryset.filter(
            created_at__date__range=[start_of_week, end_of_week]
        ).count()

        # Existing statistics calculations
        total_updates = queryset.count()
        
        updates_by_project = list(
            queryset.values('project__title').annotate(count=Count('id'))
        )

        total_funds_spent = queryset.aggregate(total=Sum('funds_spent_today'))
        total_funds_value = float(total_funds_spent['total']) if total_funds_spent['total'] else 0.0

        updates_by_user = list(
            queryset.values(
                'submitted_by__username',
                'submitted_by__first_name',
                'submitted_by__last_name'
            ).annotate(count=Count('id'))
        )

        updates_by_date = list(
            queryset.annotate(date_only=TruncDate('date'))
            .values('date_only')
            .annotate(count=Count('id'))
            .order_by('date_only')
        )

        return Response({
            'total_updates': total_updates,
            'updates_this_week': updates_this_week,
            'updates_by_project': updates_by_project,
            'total_funds_spent': total_funds_value,
            'updates_by_user': updates_by_user,
            'updates_by_date': updates_by_date,
        })

class ProjectUpdateMediaViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing project update media files
    """
    serializer_class = ProjectUpdateMediaSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['caption', 'media_type']
    ordering_fields = ['uploaded_at']
    
    def get_queryset(self):
        """
        This view returns media files based on query parameters
        """
        queryset = ProjectUpdateMedia.objects.all()
        
        # Filter by update if update_id is provided
        update_id = self.request.query_params.get('update_id')
        if update_id:
            queryset = queryset.filter(update_id=update_id)
            
        # Filter by project if project_id is provided
        project_id = self.request.query_params.get('project_id')
        if project_id:
            queryset = queryset.filter(update__project_id=project_id)
            
        # Filter by media_type if provided
        media_type = self.request.query_params.get('media_type')
        if media_type:
            queryset = queryset.filter(media_type=media_type)
            
        return queryset
    
    def get_serializer_class(self):
        """
        Use different serializers for different actions
        """
        if self.action in ['create', 'update', 'partial_update']:
            return ProjectUpdateMediaCreateSerializer
        return ProjectUpdateMediaSerializer
    
    def perform_create(self, serializer):
        """
        Set uploaded_by to current user when creating media
        """
        media = serializer.save(uploaded_by=self.request.user)
        
        # Send notification for media uploaded
        notify_media_uploaded(media, media.media_type, 'update', media.update)
    
    @action(detail=False, methods=['get'])
    def by_update(self, request, update_id=None):
        """
        Get all media files for a specific update
        """
        # If update_id is not provided in the URL, check query params
        if update_id is None:
            update_id = request.query_params.get('update_id')
            
        if not update_id:
            return Response(
                {"detail": "update_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        update = get_object_or_404(DailyProjectUpdate, id=update_id)
        media_files = ProjectUpdateMedia.objects.filter(update=update)
        
        # Apply additional filters
        media_type = request.query_params.get('media_type')
        if media_type:
            media_files = media_files.filter(media_type=media_type)
            
        serializer = self.get_serializer(media_files, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_project(self, request):
        """
        Get all media files for a specific project
        """
        project_id = request.query_params.get('project_id')
        if not project_id:
            return Response(
                {"detail": "project_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        project = get_object_or_404(Project, id=project_id)
        media_files = ProjectUpdateMedia.objects.filter(update__project=project)
        
        # Apply additional filters
        media_type = request.query_params.get('media_type')
        if media_type:
            media_files = media_files.filter(media_type=media_type)
            
        serializer = self.get_serializer(media_files, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def images(self, request):
        """
        Get all image media files
        """
        media_files = ProjectUpdateMedia.objects.filter(media_type='image')
        
        # Filter by project if provided
        project_id = request.query_params.get('project_id')
        if project_id:
            media_files = media_files.filter(update__project_id=project_id)
            
        # Filter by update if provided
        update_id = request.query_params.get('update_id')
        if update_id:
            media_files = media_files.filter(update_id=update_id)
            
        serializer = self.get_serializer(media_files, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def videos(self, request):
        """
        Get all video media files
        """
        media_files = ProjectUpdateMedia.objects.filter(media_type='video')
        
        # Filter by project if provided
        project_id = request.query_params.get('project_id')
        if project_id:
            media_files = media_files.filter(update__project_id=project_id)
            
        # Filter by update if provided
        update_id = request.query_params.get('update_id')
        if update_id:
            media_files = media_files.filter(update_id=update_id)
            
        serializer = self.get_serializer(media_files, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def documents(self, request):
        """
        Get all document media files
        """
        media_files = ProjectUpdateMedia.objects.filter(media_type='document')
        
        # Filter by project if provided
        project_id = request.query_params.get('project_id')
        if project_id:
            media_files = media_files.filter(update__project_id=project_id)
            
        # Filter by update if provided
        update_id = request.query_params.get('update_id')
        if update_id:
            media_files = media_files.filter(update_id=update_id)
            
        serializer = self.get_serializer(media_files, many=True)
        return Response(serializer.data)


    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Securely download a file from S3"""
        media_object = self.get_object()
        
        if not media_object.file:
            return Response(
                {"detail": "No file associated with this media"},
                status=status.HTTP_404_NOT_FOUND
            )
            
        # Get the file key from the file field
        file_key = str(media_object.file)
        
        # Initialize S3 client
        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        
        try:
            # Get the file from S3
            s3_response = s3.get_object(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME, 
                Key=file_key
            )
            
            # Set the appropriate headers for file download
            response = HttpResponse(
                s3_response["Body"].read(), 
                content_type=s3_response["ContentType"]
            )
            
            # Use the original filename if available, otherwise extract from the key
            filename = media_object.title or file_key.split("/")[-1]
            
            # Ensure filename has the correct extension
            if "." not in filename:
                extension = file_key.split(".")[-1] if "." in file_key else ""
                if extension:
                    filename = f"{filename}.{extension}"
            
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            response["Content-Length"] = s3_response["ContentLength"]
            
            return response
            
        except s3.exceptions.NoSuchKey:
            return Response(
                {"detail": "File not found on storage server"},
                status=status.HTTP_404_NOT_FOUND
            )
        except (NoCredentialsError, PartialCredentialsError):
            return Response(
                {"detail": "Server configuration error. Please contact support."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response(
                {"detail": f"Error downloading file: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
@api_view(['GET'])
def project_model_info(request):
    """
    Debug endpoint to get information about the Project model structure
    """
    from django.apps import apps
    
    project_model = apps.get_model('project', 'Project')
    fields = [f.name for f in project_model._meta.get_fields()]
    
    # Get relationship information
    relationships = {}
    for field in project_model._meta.get_fields():
        if field.is_relation:
            related_name = field.related_name or f"{field.model.__name__.lower()}_set"
            relationships[field.name] = {
                'related_model': field.related_model.__name__ if hasattr(field, 'related_model') else None,
                'related_name': related_name,
                'many_to_many': field.many_to_many,
                'one_to_many': field.one_to_many,
                'many_to_one': field.many_to_one,
                'one_to_one': field.one_to_one,
            }
    
    return Response({
        'model_name': project_model.__name__,
        'app_label': project_model._meta.app_label,
        'fields': fields,
        'relationships': relationships
    })

class UserRelatedProjectsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for retrieving projects related to the authenticated user.
    """
    serializer_class = UserProjectRoleSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    filterset_fields = ['status', 'category'] 
    
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'updated_at', 'target_end_date', 'budget']
    ordering = ['-updated_at']
    
    def get_queryset(self):
        user = self.request.user
        
        # Get all projects where the user has any relationship
        queryset = Project.objects.filter(
            Q(manager=user) |  # User is manager
            Q(officials=user) |  # User is an official
            Q(created_by=user) |  # User created the project
            Q(team_members__user=user)  # User is a team member
        ).distinct()
        
        # Additional custom filtering
        role_filter = self.request.query_params.get('role')
        if role_filter:
            if role_filter == 'manager':
                queryset = queryset.filter(manager=user)
            elif role_filter == 'official':
                queryset = queryset.filter(officials=user)
            elif role_filter == 'creator':
                queryset = queryset.filter(created_by=user)
            elif role_filter == 'team_member':
                queryset = queryset.filter(team_members__user=user)
        
        return queryset
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

class BaseMediaViewSet(viewsets.ModelViewSet):
    """Base ViewSet for all media models"""
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description', 'caption', 'media_type']
    ordering_fields = ['uploaded_at', 'updated_at']
    ordering = ['-uploaded_at']
    def get_serializer_class(self):
        """Use different serializers for different actions"""
        if self.action in ['create', 'update', 'partial_update']:
            return self.create_serializer_class
        return self.serializer_class
    
    def perform_create(self, serializer):
        """Set uploaded_by to current user when creating media"""
        media = serializer.save(uploaded_by=self.request.user)
        
        # Determine the related object type and object
        if hasattr(media, 'project'):
            notify_media_uploaded(media, media.media_type, 'project', media.project)
        elif hasattr(media, 'milestone'):
            notify_media_uploaded(media, media.media_type, 'milestone', media.milestone)
    
    @action(detail=False, methods=['get'])
    def by_media_type(self, request):
        """Get media files filtered by media_type"""
        media_type = request.query_params.get('media_type')
        if not media_type:
            return Response(
                {"detail": "media_type parameter is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        queryset = self.filter_queryset(self.get_queryset().filter(media_type=media_type))
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def images(self, request):
        """Get all image media files"""
        queryset = self.filter_queryset(self.get_queryset().filter(media_type='image'))
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def videos(self, request):
        """Get all video media files"""
        queryset = self.filter_queryset(self.get_queryset().filter(media_type='video'))
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def documents(self, request):
        """Get all document media files"""
        queryset = self.filter_queryset(self.get_queryset().filter(media_type='document'))
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Securely download a file from S3"""
        media_object = self.get_object()
        
        if not media_object.file:
            return Response(
                {"detail": "No file associated with this media"},
                status=status.HTTP_404_NOT_FOUND
            )
            
        # Get the file key from the file field
        file_key = str(media_object.file)
        
        # Initialize S3 client
        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        
        try:
            # Get the file from S3
            s3_response = s3.get_object(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME, 
                Key=file_key
            )
            
            # Set the appropriate headers for file download
            response = HttpResponse(
                s3_response["Body"].read(), 
                content_type=s3_response["ContentType"]
            )
            
            # Use the original filename if available, otherwise extract from the key
            filename = media_object.title or file_key.split("/")[-1]
            
            # Ensure filename has the correct extension
            if "." not in filename:
                extension = file_key.split(".")[-1] if "." in file_key else ""
                if extension:
                    filename = f"{filename}.{extension}"
            
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            response["Content-Length"] = s3_response["ContentLength"]
            
            return response
            
        except s3.exceptions.NoSuchKey:
            return Response(
                {"detail": "File not found on storage server"},
                status=status.HTTP_404_NOT_FOUND
            )
        except (NoCredentialsError, PartialCredentialsError):
            return Response(
                {"detail": "Server configuration error. Please contact support."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response(
                {"detail": f"Error downloading file: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    

class ProjectMediaViewSet(BaseMediaViewSet):
    """ViewSet for managing project media files"""
    serializer_class = ProjectMediaSerializer
    create_serializer_class = ProjectMediaCreateSerializer
    
    def get_queryset(self):
        """Filter queryset based on query parameters"""
        queryset = ProjectMedia.objects.all()
        
        project_id = self.request.query_params.get('project_id')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
            
        is_featured = self.request.query_params.get('is_featured')
        if is_featured is not None:
            is_featured = is_featured.lower() == 'true'
            queryset = queryset.filter(is_featured=is_featured)
            
        return queryset
    
    @action(detail=False, methods=['get'])
    def by_project(self, request):
        """Get all media files for a specific project"""
        project_id = request.query_params.get('project_id')
        if not project_id:
            return Response(
                {"detail": "project_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        project = get_object_or_404(Project, id=project_id)
        queryset = self.filter_queryset(ProjectMedia.objects.filter(project=project))
        
        media_type = request.query_params.get('media_type')
        if media_type:
            queryset = queryset.filter(media_type=media_type)
            
        is_featured = request.query_params.get('is_featured')
        if is_featured is not None:
            is_featured = is_featured.lower() == 'true'
            queryset = queryset.filter(is_featured=is_featured)
            
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    

    @action(detail=True, methods=['post'])
    def toggle_featured(self, request, pk=None):
        """Toggle the featured status of a media file"""
        media_file = self.get_object()
        media_file.is_featured = not media_file.is_featured
        media_file.save()
        serializer = self.get_serializer(media_file)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured media files"""
        queryset = self.filter_queryset(ProjectMedia.objects.filter(is_featured=True))
        
        project_id = request.query_params.get('project_id')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
            
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

class MilestoneMediaViewSet(BaseMediaViewSet):
    """ViewSet for managing milestone media files"""
    serializer_class = MilestoneMediaSerializer
    create_serializer_class = MilestoneMediaCreateSerializer

    def get_queryset(self):
        """Filter queryset based on query parameters"""
        queryset = MilestoneMedia.objects.all()
        
        # Filter by milestone if milestone_id is provided
        milestone_id = self.request.query_params.get('milestone_id')
        if milestone_id:
            queryset = queryset.filter(milestone_id=milestone_id)
            
        # Filter by project if project_id is provided
        project_id = self.request.query_params.get('project_id')
        if project_id:
            queryset = queryset.filter(milestone__project_id=project_id)
            
        # Filter by deliverable status if provided
        represents_deliverable = self.request.query_params.get('represents_deliverable')
        if represents_deliverable is not None:
            represents_deliverable = represents_deliverable.lower() == 'true'
            queryset = queryset.filter(represents_deliverable=represents_deliverable)
            
        return queryset
    
    @action(detail=False, methods=['get'])
    def by_milestone(self, request):
        """Get all media files for a specific milestone"""
        milestone_id = request.query_params.get('milestone_id')
        if not milestone_id:
            return Response(
                {"detail": "milestone_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        milestone = get_object_or_404(ProjectMilestone, id=milestone_id)
        queryset = self.filter_queryset(MilestoneMedia.objects.filter(milestone=milestone))
        
        # Apply additional filters
        media_type = request.query_params.get('media_type')
        if media_type:
            queryset = queryset.filter(media_type=media_type)
            
        represents_deliverable = request.query_params.get('represents_deliverable')
        if represents_deliverable is not None:
            represents_deliverable = represents_deliverable.lower() == 'true'
            queryset = queryset.filter(represents_deliverable=represents_deliverable)
            
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_project(self, request):
        """Get all milestone media files for a specific project"""
        project_id = request.query_params.get('project_id')
        if not project_id:
            return Response(
                {"detail": "project_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        project = get_object_or_404(Project, id=project_id)
        queryset = self.filter_queryset(MilestoneMedia.objects.filter(milestone__project=project))
        
        # Apply additional filters
        media_type = request.query_params.get('media_type')
        if media_type:
            queryset = queryset.filter(media_type=media_type)
            
        represents_deliverable = request.query_params.get('represents_deliverable')
        if represents_deliverable is not None:
            represents_deliverable = represents_deliverable.lower() == 'true'
            queryset = queryset.filter(represents_deliverable=represents_deliverable)
            
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def toggle_deliverable(self, request, pk=None):
        """Toggle the represents_deliverable status of a milestone media file"""
        media_file = self.get_object()
        media_file.represents_deliverable = not media_file.represents_deliverable
        media_file.save()
        serialiser=self.get_serializer(media_file)
        return Response(serialiser.data)

        
    @action(detail=False, methods=['get'])
    def deliverables(self, request):
        """Get media files that represent deliverables"""
        queryset = self.filter_queryset(MilestoneMedia.objects.filter(represents_deliverable=True))
        
        # Filter by milestone if provided
        milestone_id = request.query_params.get('milestone_id')
        if milestone_id:
            queryset = queryset.filter(milestone_id=milestone_id)
            
        # Filter by project if provided
        project_id = request.query_params.get('project_id')
        if project_id:
            queryset = queryset.filter(milestone__project_id=project_id)
            
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
