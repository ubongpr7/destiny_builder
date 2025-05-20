from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Q, Prefetch
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models.functions import TruncDate

from ..models import Task, TaskComment, TaskAttachment, TaskTimeLog, TaskStatus, TaskPriority, TaskType
from .serializers import (
    TaskSerializer, DetailedTaskSerializer, TaskCommentSerializer,
    TaskAttachmentSerializer, TaskTimeLogSerializer, TaskTreeSerializer,
    TaskStatisticsSerializer, SimpleTaskSerializer
)


class TaskViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Task model with comprehensive filtering and actions
    """
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'priority', 'task_type', 'project', 'milestone', 'is_recurring']
    search_fields = ['title', 'description', 'tags']
    ordering_fields = ['created_at', 'updated_at', 'due_date', 'start_date', 'priority']
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = Task.objects.all()
        
        # Annotate with counts
        queryset = queryset.annotate(
            comments_count=Count('comments', distinct=True),
            attachments_count=Count('attachments', distinct=True)
        )
        
        # Filter by parent (for subtasks)
        parent_id = self.request.query_params.get('parent_id')
        if parent_id:
            if parent_id == 'null':
                # Get top-level tasks
                queryset = queryset.filter(parent__isnull=True)
            else:
                # Get subtasks of a specific parent
                queryset = queryset.filter(parent_id=parent_id)
        
        # Filter by assigned user
        assigned_to = self.request.query_params.get('assigned_to')
        if assigned_to:
            if assigned_to == 'me':
                queryset = queryset.filter(assigned_to=self.request.user)
            else:
                queryset = queryset.filter(assigned_to=assigned_to)
        
        # Filter by created user
        created_by = self.request.query_params.get('created_by')
        if created_by:
            if created_by == 'me':
                queryset = queryset.filter(created_by=self.request.user)
            else:
                queryset = queryset.filter(created_by=created_by)
        
        # Filter by due date range
        due_date_start = self.request.query_params.get('due_date_start')
        due_date_end = self.request.query_params.get('due_date_end')
        if due_date_start:
            queryset = queryset.filter(due_date__gte=due_date_start)
        if due_date_end:
            queryset = queryset.filter(due_date__lte=due_date_end)
        
        # Filter by overdue
        is_overdue = self.request.query_params.get('is_overdue')
        if is_overdue == 'true':
            today = timezone.now().date()
            queryset = queryset.filter(
                due_date__lt=today,
                status__in=[TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED]
            )
        
        # Filter by upcoming (due in next X days)
        upcoming_days = self.request.query_params.get('upcoming_days')
        if upcoming_days:
            today = timezone.now().date()
            end_date = today + timezone.timedelta(days=int(upcoming_days))
            queryset = queryset.filter(
                due_date__gte=today,
                due_date__lte=end_date,
                status__in=[TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED]
            )
        
        # Filter by completion status
        is_completed = self.request.query_params.get('is_completed')
        if is_completed == 'true':
            queryset = queryset.filter(status=TaskStatus.COMPLETED)
        elif is_completed == 'false':
            queryset = queryset.exclude(status=TaskStatus.COMPLETED)
        
        # Filter by tags
        tags = self.request.query_params.get('tags')
        if tags:
            tag_list = [tag.strip() for tag in tags.split(',')]
            q_objects = Q()
            for tag in tag_list:
                q_objects |= Q(tags__icontains=tag)
            queryset = queryset.filter(q_objects)
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return DetailedTaskSerializer
        if self.action == 'tree':
            return TaskTreeSerializer
        return TaskSerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        task = self.get_object()
        task.update_status(TaskStatus.COMPLETED)
        
        serializer = self.get_serializer(task)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        task = self.get_object()
        status_value = request.data.get('status')
        
        if status_value not in dict(TaskStatus.choices).keys():
            return Response({'error': 'Invalid status'}, status=status.HTTP_400_BAD_REQUEST)
        
        task.update_status(status_value)
        
        # Return the updated task with its subtasks
        serializer = self.get_serializer(task)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def update_percentage(self, request, pk=None):
        task = self.get_object()
        percentage = request.data.get('completion_percentage')
        
        try:
            percentage = int(percentage)
            if percentage < 0 or percentage > 100:
                raise ValueError
        except (ValueError, TypeError):
            return Response({'error': 'Percentage must be between 0 and 100'}, 
                           status=status.HTTP_400_BAD_REQUEST)
        
        task.completion_percentage_manual = percentage
        task.save(update_fields=['completion_percentage_manual'])
        return Response({'status': 'completion percentage updated'})
    
    @action(detail=True, methods=['post'])
    def assign_users(self, request, pk=None):
        task = self.get_object()
        user_ids = request.data.get('user_ids', [])
        
        task.assigned_to.clear()
        for user_id in user_ids:
            task.assign_user(user_id)
        
        return Response({'status': 'users assigned'})
    
    @action(detail=True, methods=['post'])
    def add_time(self, request, pk=None):
        task = self.get_object()
        minutes = request.data.get('minutes')
        description = request.data.get('description', '')
        
        try:
            minutes = int(minutes)
            if minutes <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return Response({'error': 'Minutes must be a positive integer'}, 
                           status=status.HTTP_400_BAD_REQUEST)
        
        time_log = TaskTimeLog.objects.create(
            task=task,
            user=request.user,
            minutes=minutes,
            description=description
        )
        
        return Response(TaskTimeLogSerializer(time_log).data)
    

    @action(detail=False, methods=['get'])
    def by_milestone(self, request):
        milestone_id = request.query_params.get('milestone_id')
        if not milestone_id:
            return Response({'error': 'milestone_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        queryset = Task.objects.filter(milestone_id=milestone_id)
        
        queryset = queryset.filter(parent__isnull=True)
        
        status = request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        priority = request.query_params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)
        
        # Task type filter
        task_type = request.query_params.get('taskType')
        if task_type:
            queryset = queryset.filter(task_type=task_type)
        
        # Due date range filters
        due_date_start = request.query_params.get('dueDateStart')
        if due_date_start:
            queryset = queryset.filter(due_date__gte=due_date_start)
        
        due_date_end = request.query_params.get('dueDateEnd')
        if due_date_end:
            queryset = queryset.filter(due_date__lte=due_date_end)
        
        # Overdue tasks filter
        is_overdue = request.query_params.get('isOverdue')
        if is_overdue == 'true':
            today = timezone.now().date()
            queryset = queryset.filter(
                due_date__lt=today,
                status__in=[TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED]
            )
        
        is_completed = request.query_params.get('isCompleted')
        if is_completed == 'true':
            queryset = queryset.filter(status=TaskStatus.COMPLETED)
        elif is_completed == 'false':
            queryset = queryset.exclude(status=TaskStatus.COMPLETED)
        

        queryset = queryset.annotate(
            comments_count=Count('comments', distinct=True),
            attachments_count=Count('attachments', distinct=True)
        )
        
        # Apply ordering
        ordering = request.query_params.get('ordering', '-created_at')
        queryset = queryset.order_by(ordering)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


    @action(detail=False, methods=['get'])
    def by_user(self, request):
        user_id = request.query_params.get('user_id')
        if not user_id:
            # Default to current user
            user_id = request.user.id
        
        tasks = Task.get_user_tasks(user_id)
        serializer = self.get_serializer(tasks, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        tasks = Task.get_overdue_tasks()
        
        # Additional filtering
        project_id = request.query_params.get('project_id')
        if project_id:
            tasks = tasks.filter(project_id=project_id)
            
        user_id = request.query_params.get('user_id')
        if user_id:
            tasks = tasks.filter(assigned_to=user_id)
        
        serializer = self.get_serializer(tasks, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        days = request.query_params.get('days', 7)
        try:
            days = int(days)
        except (ValueError, TypeError):
            days = 7
            
        tasks = Task.get_upcoming_tasks(days)
        
        # Additional filtering
        project_id = request.query_params.get('project_id')
        if project_id:
            tasks = tasks.filter(project_id=project_id)
            
        user_id = request.query_params.get('user_id')
        if user_id:
            tasks = tasks.filter(assigned_to=user_id)
        
        serializer = self.get_serializer(tasks, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        project_id = request.query_params.get('project_id')
        
        # Get basic statistics
        stats = Task.get_task_statistics(project_id)
        
        # Add priority breakdown
        priority_counts = {}
        for priority, _ in TaskPriority.choices:
            query = Task.objects.filter(priority=priority)
            if project_id:
                query = query.filter(project_id=project_id)
            priority_counts[priority] = query.count()
        stats['by_priority'] = priority_counts
        
        # Add type breakdown
        type_counts = {}
        for task_type, _ in TaskType.choices:
            query = Task.objects.filter(task_type=task_type)
            if project_id:
                query = query.filter(project_id=project_id)
            type_counts[task_type] = query.count()
        stats['by_type'] = type_counts
        
        # Add recent activity
        recent_tasks = Task.objects.order_by('-updated_at')[:10]
        if project_id:
            recent_tasks = recent_tasks.filter(project_id=project_id)
        
        recent_activity = []
        for task in recent_tasks:
            recent_activity.append({
                'id': task.id,
                'title': task.title,
                'status': task.status,
                'updated_at': task.updated_at
            })
        stats['recent_activity'] = recent_activity
        
        serializer = TaskStatisticsSerializer(stats)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def tree(self, request):
        """Return tasks in a hierarchical structure"""
        project_id = request.query_params.get('project_id')
        
        # Get only root tasks (no parent)
        queryset = Task.objects.filter(parent__isnull=True)
        
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        
        serializer = TaskTreeSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def create_subtask(self, request, pk=None):
        parent_task = self.get_object()
        serializer = TaskSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            # Automatically set project and milestone from parent
            serializer.save(
                parent=parent_task,
                project=parent_task.project,
                milestone=parent_task.milestone,
                created_by=request.user
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class TaskCommentViewSet(viewsets.ModelViewSet):
    """ViewSet for task comments"""
    queryset = TaskComment.objects.all()
    serializer_class = TaskCommentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        task_id = self.request.query_params.get('task_id')
        if task_id:
            return TaskComment.objects.filter(task_id=task_id)
        return TaskComment.objects.none()
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class TaskAttachmentViewSet(viewsets.ModelViewSet):
    """ViewSet for task attachments"""
    queryset = TaskAttachment.objects.all()
    serializer_class = TaskAttachmentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        task_id = self.request.query_params.get('task_id')
        if task_id:
            return TaskAttachment.objects.filter(task_id=task_id)
        return TaskAttachment.objects.none()
    
    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)


class TaskTimeLogViewSet(viewsets.ModelViewSet):
    """ViewSet for task time logs"""
    queryset = TaskTimeLog.objects.all()
    serializer_class = TaskTimeLogSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        task_id = self.request.query_params.get('task_id')
        if task_id:
            return TaskTimeLog.objects.filter(task_id=task_id)
        return TaskTimeLog.objects.none()
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)