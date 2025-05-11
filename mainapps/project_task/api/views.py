from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from ..models import Task, Project, ProjectMilestone, TaskStatus
from .serializers import (
    TaskSerializer, TaskDetailSerializer,
    ProjectSerializer, ProjectDetailSerializer,
    MilestoneSerializer
)

class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'priority', 'project', 'milestone']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'due_date', 'updated_at', 'priority']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return TaskDetailSerializer
        return TaskSerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    def get_queryset(self):
        queryset = Task.objects.all()
        
        # Filter by parent (top-level tasks)
        if self.request.query_params.get('top_level') == 'true':
            queryset = queryset.filter(parent__isnull=True)
        
        # Filter by status
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)
        
        # Filter by priority
        priority_param = self.request.query_params.get('priority')
        if priority_param:
            queryset = queryset.filter(priority=priority_param)
        
        # Filter by project
        project_param = self.request.query_params.get('project')
        if project_param:
            queryset = queryset.filter(project=project_param)
        
        # Filter by milestone
        milestone_param = self.request.query_params.get('milestone')
        if milestone_param:
            queryset = queryset.filter(milestone=milestone_param)
        
        # Filter by assigned user
        assigned_param = self.request.query_params.get('assigned_to')
        if assigned_param:
            queryset = queryset.filter(assigned_to=assigned_param)
        
        # Filter by due date range
        due_start = self.request.query_params.get('due_start')
        due_end = self.request.query_params.get('due_end')
        if due_start:
            queryset = queryset.filter(due_date__gte=due_start)
        if due_end:
            queryset = queryset.filter(due_date__lte=due_end)
        
        # Filter overdue tasks
        if self.request.query_params.get('overdue') == 'true':
            queryset = queryset.filter(
                due_date__lt=timezone.now().date(),
                status__in=[TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.REVIEW, TaskStatus.BLOCKED]
            )
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        task = self.get_object()
        task.mark_completed()
        serializer = self.get_serializer(task)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_subtask(self, request, pk=None):
        parent_task = self.get_object()
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            serializer.save(parent=parent_task, created_by=request.user, project=parent_task.project)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def subtasks(self, request, pk=None):
        parent_task = self.get_object()
        subtasks = parent_task.get_children()
        serializer = self.get_serializer(subtasks, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        task = self.get_object()
        user_id = request.data.get('user_id')
        
        try:
            user = User.objects.get(pk=user_id)
            task.assign_user(user)
            return Response({'status': 'user assigned'})
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=True, methods=['post'])
    def unassign(self, request, pk=None):
        task = self.get_object()
        user_id = request.data.get('user_id')
        
        try:
            user = User.objects.get(pk=user_id)
            task.unassign_user(user)
            return Response({'status': 'user unassigned'})
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False)
    def my_tasks(self, request):
        tasks = Task.objects.filter(assigned_to=request.user)
        serializer = self.get_serializer(tasks, many=True)
        return Response(serializer.data)
    
    @action(detail=False)
    def overdue(self, request):
        today = timezone.now().date()
        tasks = Task.objects.filter(
            due_date__lt=today,
            status__in=[TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.REVIEW, TaskStatus.BLOCKED]
        )
        serializer = self.get_serializer(tasks, many=True)
        return Response(serializer.data)

class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'updated_at', 'start_date', 'end_date']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProjectDetailSerializer
        return ProjectSerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True)
    def tasks(self, request, pk=None):
        project = self.get_object()
        tasks = project.tasks.filter(parent__isnull=True)  # Get only root tasks
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)
    
    @action(detail=True)
    def milestones(self, request, pk=None):
        project = self.get_object()
        milestones = project.milestones.all()
        serializer = MilestoneSerializer(milestones, many=True)
        return Response(serializer.data)

class MilestoneViewSet(viewsets.ModelViewSet):
    queryset = ProjectMilestone.objects.all()
    serializer_class = MilestoneSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['project']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'updated_at', 'due_date']
    
    @action(detail=True)
    def tasks(self, request, pk=None):
        milestone = self.get_object()
        tasks = milestone.tasks.all()
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)
