from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ..models import Task, Project
from .serializers import (
    TaskSerializer, TaskDetailSerializer,
    ProjectSerializer, ProjectDetailSerializer
)

class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return TaskDetailSerializer
        return TaskSerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    def get_queryset(self):
        queryset = Task.objects.all()
        
        # Filter by parent (top-level tasks)
        if self.request.query_params.get('top_level'):
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
        
        # Filter by assigned user
        assigned_param = self.request.query_params.get('assigned_to')
        if assigned_param:
            queryset = queryset.filter(assigned_to=assigned_param)
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        task = self.get_object()
        task.status = 'completed'
        task.save()
        serializer = self.get_serializer(task)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_subtask(self, request, pk=None):
        parent_task = self.get_object()
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            serializer.save(parent=parent_task, created_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def subtasks(self, request, pk=None):
        parent_task = self.get_object()
        subtasks = Task.objects.filter(parent=parent_task)
        serializer = self.get_serializer(subtasks, many=True)
        return Response(serializer.data)

class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProjectDetailSerializer
        return ProjectSerializer
