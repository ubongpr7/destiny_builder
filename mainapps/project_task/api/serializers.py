from rest_framework import serializers
from ..models import Task, TaskComment, TaskAttachment, TaskTimeLog, TaskStatus, TaskPriority, TaskType
from django.contrib.auth import get_user_model
from mainapps.project.api.serializers import ProjectMilestoneSerializer, ProjectMinimalSerializer
from mainapps.project.models import ProjectMilestone

User = get_user_model()


class TaskUserSerializer(serializers.ModelSerializer):
    profile_image = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'profile_image']
        read_only_fields = ['profile_image']
    def get_profile_image(self, obj):
        if obj.profile:
            return obj.profile.profile_image.url if obj.profile.profile_image else None



class TaskAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by = TaskUserSerializer(read_only=True)
    
    class Meta:
        model = TaskAttachment
        fields = '__all__'
        read_only_fields = ['uploaded_by', 'uploaded_at']
        
    def create(self, validated_data):
        validated_data['uploaded_by'] = self.context['request'].user
        return super().create(validated_data)


class TaskTimeLogSerializer(serializers.ModelSerializer):
    user = TaskUserSerializer(read_only=True)
    
    class Meta:
        model = TaskTimeLog
        fields = '__all__'
        read_only_fields = ['user', 'logged_at']
        
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class TaskCommentSerializer(serializers.ModelSerializer):
    user = TaskUserSerializer(read_only=True)
    
    class Meta:
        model = TaskComment
        fields = '__all__'
        read_only_fields = ['user', 'created_at', 'updated_at']
        
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class SimpleTaskSerializer(serializers.ModelSerializer):
    """Simplified Task serializer for nested relationships"""
    class Meta:
        model = Task
        fields = ['id', 'title', 'status', 'priority', 'due_date', 'completion_percentage']


class TaskSerializer(serializers.ModelSerializer):
    assigned_to = TaskUserSerializer(many=True, read_only=True)
    created_by = TaskUserSerializer(read_only=True)
    milestone = ProjectMilestoneSerializer(read_only=True)
    project = ProjectMinimalSerializer(read_only=True)
    dependencies = SimpleTaskSerializer(many=True, read_only=True)
    dependents = SimpleTaskSerializer(many=True, read_only=True)
    subtasks = serializers.SerializerMethodField()
    parent_details = SimpleTaskSerializer(source='parent', read_only=True)
    comments_count = serializers.IntegerField(read_only=True)
    attachments_count = serializers.IntegerField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    is_unblocked = serializers.BooleanField(read_only=True)
    days_until_due = serializers.IntegerField(read_only=True)
    time_spent_formatted = serializers.CharField(read_only=True)
    
    milestone_id = serializers.PrimaryKeyRelatedField(
        queryset=ProjectMilestone.objects.all(),
        source='milestone',
        required=False,
        allow_null=True,
        write_only=True
    )
    assigned_to_ids = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='assigned_to',
        required=False,
        many=True,
        write_only=True
    )
    dependency_ids = serializers.PrimaryKeyRelatedField(
        queryset=Task.objects.all(),
        source='dependencies',
        required=False,
        many=True,
        write_only=True
    )
    parent_id = serializers.PrimaryKeyRelatedField(
        queryset=Task.objects.all(),
        source='parent',
        required=False,
        allow_null=True,
        write_only=True
    )
    
    class Meta:
        model = Task
        fields = '__all__'
        read_only_fields = [
            'created_at', 'updated_at', 'is_overdue', 'is_unblocked',
            'days_until_due', 'time_spent_formatted', 'completion_percentage',
            'project' 
        ]
        
    def get_subtasks(self, obj):
        """Get direct subtasks with their own subtasks recursively"""
        subtasks = obj.get_children()
        if not subtasks:
            return []
            
        class TaskSubtaskSerializer(serializers.ModelSerializer):
            subtasks = serializers.SerializerMethodField()
            assigned_to = TaskUserSerializer(many=True, read_only=True)
            parent_details = SimpleTaskSerializer(source='parent', read_only=True)
            
            class Meta:
                model = Task
                # fields = ['id', 'title', 'description', 'status', 'priority', 
                #           'due_date', 'completion_percentage', 'assigned_to', 
                #           'parent_details', 'subtasks']
                fields = '__all__'
                
            def get_subtasks(self, obj):
                """Recursive subtasks"""
                child_subtasks = obj.get_children()
                if child_subtasks:
                    return TaskSubtaskSerializer(child_subtasks, many=True).data
                return []
                
        return TaskSubtaskSerializer(subtasks, many=True).data

    def validate(self, data):
        # Validate start_date and due_date
        start_date = data.get('start_date')
        due_date = data.get('due_date')
        
        if start_date and due_date and start_date > due_date:
            raise serializers.ValidationError("Start date cannot be after due date")
        
        # Validate recurrence_end_date
        is_recurring = data.get('is_recurring', False)
        recurrence_end_date = data.get('recurrence_end_date')
        
        if is_recurring and recurrence_end_date and start_date and recurrence_end_date < start_date:
            raise serializers.ValidationError("Recurrence end date cannot be before start date")
        
        return data
        
    def create(self, validated_data):
        assigned_to = validated_data.pop('assigned_to', [])
        dependencies = validated_data.pop('dependencies', [])
        
        milestone = validated_data.get('milestone')
        if milestone and not validated_data.get('project'):
            validated_data['project'] = milestone.project
            
        # Set created_by from context
        validated_data['created_by'] = self.context['request'].user
        
        task = Task.objects.create(**validated_data)
        parent= task.parent
        if parent:
            if parent.status== 'completed':
                parent.update_status(TaskStatus.TODO)
            parent.save()
        
        if assigned_to:
            task.assigned_to.set(assigned_to)
            
        if dependencies:
            task.dependencies.set(dependencies)
            
        return task
    
    def update(self, instance, validated_data):
        old_status = instance.status
        new_status = validated_data.pop('status')
        
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        
        if new_status and new_status != old_status:
            instance.refresh_from_db()
            instance.update_status(new_status)
        
        return instance
class DetailedTaskSerializer(TaskSerializer):
    """Detailed Task serializer with comments and attachments"""
    comments = TaskCommentSerializer(many=True, read_only=True)
    attachments = TaskAttachmentSerializer(many=True, read_only=True)
    time_logs = TaskTimeLogSerializer(many=True, read_only=True)
    
    class Meta(TaskSerializer.Meta):
        fields = '__all__'


class TaskTreeSerializer(serializers.ModelSerializer):
    """Serializer for hierarchical task view"""
    children = serializers.SerializerMethodField()
    assigned_to = TaskUserSerializer(many=True, read_only=True)
    
    class Meta:
        model = Task
        fields = [
            'id', 'title', 'status', 'priority', 'due_date', 
            'completion_percentage', 'assigned_to', 'children'
        ]
        
    def get_children(self, obj):
        children = obj.get_children()
        return TaskTreeSerializer(children, many=True).data


class TaskStatisticsSerializer(serializers.Serializer):
    """Serializer for task statistics"""
    total = serializers.IntegerField()
    completed = serializers.IntegerField()
    in_progress = serializers.IntegerField()
    todo = serializers.IntegerField()
    blocked = serializers.IntegerField()
    overdue = serializers.IntegerField()
    completion_rate = serializers.IntegerField()
    
    # Additional statistics
    by_priority = serializers.DictField(child=serializers.IntegerField())
    by_type = serializers.DictField(child=serializers.IntegerField())
    recent_activity = serializers.ListField(child=serializers.DictField())