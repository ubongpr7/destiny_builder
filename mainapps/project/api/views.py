from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Avg, Count, Q, F, ExpressionWrapper, fields
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import timedelta
from ..models import Project, ProjectCategory
from .serializers import (
    ProjectSerializer, ProjectListSerializer, ProjectStatusUpdateSerializer,
    ProjectBudgetUpdateSerializer, ProjectOfficialSerializer, ProjectDateUpdateSerializer
)

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
    def my_projects(self, request):
        """Get projects managed by the current user"""
        projects = Project.objects.filter(manager=request.user)
        serializer = self.get_serializer(projects, many=True)
        return Response(serializer.data)
    
    @action(detail=False)
    def monitored_projects(self, request):
        """Get projects where the current user is an official"""
        projects = Project.objects.filter(officials=request.user)
        serializer = self.get_serializer(projects, many=True)
        return Response(serializer.data)
    
    @action(detail=False)
    def active_projects(self, request):
        """Get all active projects"""
        projects = Project.objects.filter(status='active')
        serializer = self.get_serializer(projects, many=True)
        return Response(serializer.data)
    
    @action(detail=False)
    def delayed_projects(self, request):
        """Get projects that are past their target end date but not completed"""
        today = timezone.now().date()
        projects = Project.objects.filter(
            target_end_date__lt=today,
            status__in=['planning', 'active', 'on_hold']
        )
        serializer = self.get_serializer(projects, many=True)
        return Response(serializer.data)
    
    @action(detail=False)
    def overbudget_projects(self, request):
        """Get projects that have spent more than their budget"""
        projects = Project.objects.filter(funds_spent__gt=F('budget'))
        serializer = self.get_serializer(projects, many=True)
        return Response(serializer.data)
    
    @action(detail=False)
    def upcoming_projects(self, request):
        """Get projects starting in the next 30 days"""
        today = timezone.now().date()
        thirty_days_later = today + timedelta(days=30)
        projects = Project.objects.filter(
            start_date__gte=today,
            start_date__lte=thirty_days_later,
            status='planning'
        )
        serializer = self.get_serializer(projects, many=True)
        return Response(serializer.data)
    
    @action(detail=False)
    def ending_soon_projects(self, request):
        """Get active projects ending in the next 30 days"""
        today = timezone.now().date()
        thirty_days_later = today + timedelta(days=30)
        projects = Project.objects.filter(
            target_end_date__gte=today,
            target_end_date__lte=thirty_days_later,
            status='active'
        )
        serializer = self.get_serializer(projects, many=True)
        return Response(serializer.data)
    
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