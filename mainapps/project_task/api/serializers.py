

from ..models import Task
from mainapps.accounts.api.serializers import MyUserSerializer
from rest_framework import serializers
from django.contrib.auth import get_user_model

from mainapps.project.models import Project
User= get_user_model()

class TaskSerializer(serializers.ModelSerializer):
    assigned_to = MyUserSerializer(read_only=True)
    created_by = MyUserSerializer(read_only=True)
    assigned_to_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), 
        source='assigned_to',
        write_only=True,
        required=False,
        allow_null=True
    )
    parent_id = serializers.PrimaryKeyRelatedField(
        queryset=Task.objects.all(),
        source='parent',
        write_only=True,
        required=False,
        allow_null=True
    )
    project_id = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(),
        source='project',
        write_only=True,
        required=False,
        allow_null=True
    )
    is_completed = serializers.BooleanField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    has_subtasks = serializers.BooleanField(read_only=True)
    completion_percentage = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'status', 'priority',
            'parent', 'parent_id', 'assigned_to', 'assigned_to_id',
            'created_by', 'due_date', 'created_at', 'updated_at',
            'completed_at', 'project', 'project_id', 'is_completed',
            'is_overdue', 'has_subtasks', 'completion_percentage'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']


class SubtaskSerializer(serializers.ModelSerializer):
    assigned_to = MyUserSerializer(read_only=True)
    assigned_to_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), 
        source='assigned_to',
        write_only=True,
        required=False,
        allow_null=True
    )
    is_completed = serializers.BooleanField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'status', 'priority',
            'assigned_to', 'assigned_to_id', 'due_date', 
            'created_at', 'updated_at', 'completed_at',
            'is_completed', 'is_overdue'
        ]
        read_only_fields = ['created_at', 'updated_at']


class TaskDetailSerializer(TaskSerializer):
    subtasks = SubtaskSerializer(many=True, read_only=True)
    
    class Meta(TaskSerializer.Meta):
        fields = TaskSerializer.Meta.fields + ['subtasks']


class ProjectSerializer(serializers.ModelSerializer):
    created_by = MyUserSerializer(read_only=True)
    completion_percentage = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Project
        fields = [
            'id', 'name', 'description', 'created_by',
            'created_at', 'updated_at', 'completion_percentage'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']


class ProjectDetailSerializer(ProjectSerializer):
    tasks = TaskSerializer(many=True, read_only=True)
    
    class Meta(ProjectSerializer.Meta):
        fields = ProjectSerializer.Meta.fields + ['tasks']
