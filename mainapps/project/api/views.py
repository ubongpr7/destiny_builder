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

from mainapps.user_profile.api.views import BaseReferenceViewSet
from ..models import Project, ProjectCategory, DailyProjectUpdate, ProjectUpdateMedia
from .serializers import *


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
        Customize queryset based on query parameters
        """
        queryset = Project.objects.all()
        
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
        
        # Filter overbudget projects
        overbudget = self.request.query_params.get('overbudget')
        if overbudget and overbudget.lower() == 'true':
            queryset = queryset.filter(funds_spent__gt=F('budget'))
        
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
        instance= serializer.instance
        instance.create_by=self.request.user
        instance.save()
    
    @action(detail=False, methods=['get'])
    def assigned(self, request):
        """Get projects assigned to the current user (as official)"""
        projects = Project.objects.filter(officials=request.user)
        serializer = self.get_serializer(projects, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def created(self, request):
        """Get projects created by the current user"""
        projects = Project.objects.filter(created_by=request.user)
        serializer = self.get_serializer(projects, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def managed(self, request):
        """Get projects managed by the current user"""
        projects = Project.objects.filter(manager=request.user)
        serializer = self.get_serializer(projects, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        """Update project status"""
        project = self.get_object()
        serializer = ProjectStatusUpdateSerializer(data=request.data)
        
        if serializer.is_valid():
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
            
            # Update budget fields if provided
            if 'budget' in data:
                project.budget = data['budget']
            if 'funds_allocated' in data:
                project.funds_allocated = data['funds_allocated']
            if 'funds_spent' in data:
                project.funds_spent = data['funds_spent']
            
            # Add note about budget update
            if notes:
                project.notes = (project.notes or '') + f"\n\nBudget updated on {timezone.now().date()}: {notes}"
            
            project.save()
            
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
            
            # Update date fields if provided
            if 'start_date' in data:
                project.start_date = data['start_date']
            if 'target_end_date' in data:
                project.target_end_date = data['target_end_date']
            if 'actual_end_date' in data:
                project.actual_end_date = data['actual_end_date']
            
            # Add note about date update
            if notes:
                project.notes = (project.notes or '') + f"\n\nDates updated on {timezone.now().date()}: {notes}"
            
            project.save()
            
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
                return Response({'status': 'official removed'})
            except User.DoesNotExist:
                return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False)
    def statistics(self, request):
        """Get project statistics"""
        # Count projects by status
        status_counts = dict(Project.objects.values('status').annotate(count=Count('id')).values_list('status', 'count'))
        
        # Count projects by type
        type_counts = dict(Project.objects.values('project_type').annotate(count=Count('id')).values_list('project_type', 'count'))
        
        # Budget statistics
        budget_stats = Project.objects.aggregate(
            total_budget=Sum('budget'),
            total_allocated=Sum('funds_allocated'),
            total_spent=Sum('funds_spent'),
            avg_budget=Avg('budget')
        )
        
        # Project timeline statistics
        today = timezone.now().date()
        active_projects = Project.objects.filter(status='active').count()
        delayed_projects = Project.objects.filter(
            target_end_date__lt=today,
            status__in=['planning', 'active', 'on_hold']
        ).count()
        completed_on_time = Project.objects.filter(
            status='completed',
            actual_end_date__lte=F('target_end_date')
        ).count()
        completed_late = Project.objects.filter(
            status='completed',
            actual_end_date__gt=F('target_end_date')
        ).count()
        
        # Projects by category
        category_counts = dict(
            Project.objects.values('category__name')
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


class DailyProjectUpdateViewSet(viewsets.ModelViewSet):
    """
    ViewSet for DailyProjectUpdate model
    """
    queryset = DailyProjectUpdate.objects.all()
    serializer_class = DailyProjectUpdateSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['project', 'date', 'submitted_by']
    search_fields = ['summary', 'challenges', 'achievements', 'next_steps']
    ordering_fields = ['date', 'created_at', 'funds_spent_today']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return DailyProjectUpdateListSerializer
        return DailyProjectUpdateSerializer
    
    def get_queryset(self):
        """Customize queryset based on query parameters"""
        queryset = DailyProjectUpdate.objects.all()
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
            
        # Filter by project
        project_id = self.request.query_params.get('project_id')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        
        return queryset
    
    def perform_create(self, serializer):
        """Set current user as submitter"""
        serializer.save(submitted_by=self.request.user)
    
    @action(detail=False)
    def my_updates(self, request):
        """Get updates submitted by the current user"""
        updates = DailyProjectUpdate.objects.filter(submitted_by=request.user)
        page = self.paginate_queryset(updates)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(updates, many=True)
        return Response(serializer.data)
    
    @action(detail=False)
    def recent(self, request):
        """Get recent updates across all projects"""
        updates = DailyProjectUpdate.objects.all().order_by('-date')[:10]
        serializer = self.get_serializer(updates, many=True)
        return Response(serializer.data)
    
    @action(detail=False)
    def by_project(self, request):
        """Get updates grouped by project"""
        from django.db.models import Max
        
        # Get the latest update for each project
        latest_updates = DailyProjectUpdate.objects.values('project').annotate(
            latest_date=Max('date')
        ).order_by('project')
        
        results = []
        for item in latest_updates:
            project_id = item['project']
            latest_date = item['latest_date']
            
            # Get the update for this project and date
            update = DailyProjectUpdate.objects.filter(
                project_id=project_id, 
                date=latest_date
            ).first()
            
            if update:
                serializer = self.get_serializer(update)
                results.append(serializer.data)
        
        return Response(results)
    
    @action(detail=False)
    def summary(self, request):
        """Get summary statistics for updates"""
        # Get total updates count
        total_updates = DailyProjectUpdate.objects.count()
        
        # Get updates by project
        updates_by_project = DailyProjectUpdate.objects.values('project__title').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Get total funds spent through updates
        total_funds_spent = DailyProjectUpdate.objects.aggregate(
            total=Sum('funds_spent_today')
        )['total'] or 0
        
        # Get updates by user
        updates_by_user = DailyProjectUpdate.objects.values(
            'submitted_by__username', 
            'submitted_by__first_name', 
            'submitted_by__last_name'
        ).annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Get updates by date (last 30 days)
        today = timezone.now().date()
        thirty_days_ago = today - timedelta(days=30)
        
        updates_by_date = DailyProjectUpdate.objects.filter(
            date__gte=thirty_days_ago
        ).values('date').annotate(
            count=Count('id')
        ).order_by('date')
        
        return Response({
            'total_updates': total_updates,
            'updates_by_project': updates_by_project,
            'total_funds_spent': total_funds_spent,
            'updates_by_user': updates_by_user,
            'updates_by_date': updates_by_date
        })


class ProjectUpdateMediaViewSet(viewsets.ModelViewSet):
    """
    ViewSet for ProjectUpdateMedia model
    """
    queryset = ProjectUpdateMedia.objects.all()
    serializer_class = ProjectUpdateMediaSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['update', 'media_type']
    
    def perform_create(self, serializer):
        """Save the media file"""
        serializer.save()
    
    @action(detail=False)
    def by_update(self, request):
        """Get media files grouped by update"""
        update_id = request.query_params.get('update_id')
        if not update_id:
            return Response(
                {"error": "update_id parameter is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        media_files = ProjectUpdateMedia.objects.filter(update_id=update_id)
        serializer = self.get_serializer(media_files, many=True)
        return Response(serializer.data)
    
    @action(detail=False)
    def by_project(self, request):
        """Get media files for a specific project"""
        project_id = request.query_params.get('project_id')
        if not project_id:
            return Response(
                {"error": "project_id parameter is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        media_files = ProjectUpdateMedia.objects.filter(update__project_id=project_id)
        serializer = self.get_serializer(media_files, many=True)
        return Response(serializer.data)
    
    @action(detail=False)
    def by_type(self, request):
        """Get media files by type"""
        media_type = request.query_params.get('media_type')
        if not media_type:
            return Response(
                {"error": "media_type parameter is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        media_files = ProjectUpdateMedia.objects.filter(media_type=media_type)
        serializer = self.get_serializer(media_files, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def bulk_upload(self, request):
        """Upload multiple media files at once"""
        update_id = request.data.get('update_id')
        if not update_id:
            return Response(
                {"error": "update_id is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            update = DailyProjectUpdate.objects.get(pk=update_id)
        except DailyProjectUpdate.DoesNotExist:
            return Response(
                {"error": "Update not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        files = request.FILES.getlist('files')
        if not files:
            return Response(
                {"error": "No files provided"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        media_type = request.data.get('media_type', 'image')
        caption = request.data.get('caption', '')
        
        created_files = []
        for file in files:
            media = ProjectUpdateMedia.objects.create(
                update=update,
                media_type=media_type,
                file=file,
                caption=caption
            )
            created_files.append(media)
        
        serializer = self.get_serializer(created_files, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    


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
        print(new_role)
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
            
        team_member.role = new_role
        team_member.save()
        
        serializer = self.get_serializer(team_member)
        return Response(serializer.data)
