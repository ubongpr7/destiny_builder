

from ..models import Task
from mainapps.accounts.api.serializers import MyUserSerializer
from rest_framework import serializers
from django.contrib.auth import get_user_model

from mainapps.project.models import Project, ProjectMilestone
User= get_user_model()

class MilestoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectMilestone
        fields = ['id', 'title', 'description', 'project', 'due_date', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class TaskDependencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ['id', 'title', 'status']

class TaskAssigneeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email']

class TaskSerializer(serializers.ModelSerializer):
    assigned_to = TaskAssigneeSerializer(many=True, read_only=True)
    created_by = MyUserSerializer(read_only=True)
    is_completed = serializers.BooleanField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    has_subtasks = serializers.BooleanField(read_only=True)
    completion_percentage = serializers.IntegerField(read_only=True)
    is_unblocked = serializers.BooleanField(read_only=True)
    
    # For write operations
    assigned_to_ids = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        write_only=True,
        many=True,
        required=False,
        source='assigned_to'
    )
    
    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'project', 'milestone', 'parent',
            'assigned_to', 'assigned_to_ids', 'created_by', 'status', 'priority',
            'start_date', 'due_date', 'completion_date', 'estimated_hours',
            'actual_hours', 'notes', 'created_at', 'updated_at',
            'is_completed', 'is_overdue', 'has_subtasks', 'completion_percentage',
            'is_unblocked', 'level'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'level']

class TaskDetailSerializer(TaskSerializer):
    subtasks = serializers.SerializerMethodField()
    dependencies = TaskDependencySerializer(many=True, read_only=True)
    blocked_by = TaskDependencySerializer(many=True, read_only=True)
    milestone = MilestoneSerializer(read_only=True)
    
    # For write operations
    dependency_ids = serializers.PrimaryKeyRelatedField(
        queryset=Task.objects.all(),
        write_only=True,
        many=True,
        required=False,
        source='dependencies'
    )
    
    class Meta(TaskSerializer.Meta):
        fields = TaskSerializer.Meta.fields + ['subtasks', 'dependencies', 'dependency_ids', 'blocked_by']
    
    def get_subtasks(self, obj):
        # Get direct children only
        children = obj.get_children()
        return TaskSerializer(children, many=True).data

class ProjectSerializer(serializers.ModelSerializer):
    created_by = MyUserSerializer(read_only=True)
    
    class Meta:
        model = Project
        fields = [
            'id', 'title', 'description', 'start_date', 'end_date',
            'created_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']

class ProjectDetailSerializer(ProjectSerializer):
    tasks = serializers.SerializerMethodField()
    milestones = MilestoneSerializer(many=True, read_only=True)
    
    class Meta(ProjectSerializer.Meta):
        fields = ProjectSerializer.Meta.fields + ['tasks', 'milestones']
    
    def get_tasks(self, obj):
        # Get only root tasks (no parent)
        root_tasks = obj.tasks.filter(parent__isnull=True)
        return TaskSerializer(root_tasks, many=True).data
