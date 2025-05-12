from rest_framework import serializers
from django.contrib.auth import get_user_model
from ..models import DailyProjectUpdate, Project, ProjectCategory, ProjectMilestone, ProjectTeamMember, ProjectUpdateMedia
from django.utils import timezone
User = get_user_model()

class ProjectUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email']

class ProjectCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectCategory
        fields = ['id', 'name', 'description']

class ProjectSerializer(serializers.ModelSerializer):
    manager_details = ProjectUserSerializer(source='manager', read_only=True)
    officials_details = ProjectUserSerializer(source='officials', many=True, read_only=True)
    category_details = ProjectCategorySerializer(source='category', read_only=True)
    
    # For write operations
    manager = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    officials = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), many=True, required=False)
    category = serializers.PrimaryKeyRelatedField(queryset=ProjectCategory.objects.all(), allow_null=True)
    
    # Calculated fields
    budget_utilization = serializers.SerializerMethodField()
    days_remaining = serializers.SerializerMethodField()
    is_overbudget = serializers.SerializerMethodField()
    
    class Meta:
        model = Project
        fields = [
            'id', 'title', 'description', 'project_type', 'category', 'category_details',
            'manager', 'manager_details', 'officials', 'officials_details',
            'start_date', 'target_end_date', 'actual_end_date',
            'budget', 'funds_allocated', 'funds_spent', 'budget_utilization', 'is_overbudget',
            'status', 'location', 'beneficiaries', 'success_criteria', 'risks', 'notes',
            'created_at', 'updated_at', 'days_remaining'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_budget_utilization(self, obj):
        """Calculate percentage of budget spent"""
        if obj.budget == 0:
            return 0
        return round((obj.funds_spent / obj.budget) * 100, 2)
    
    def get_days_remaining(self, obj):
        """Calculate days remaining until target end date"""
        from django.utils import timezone
        import datetime
        
        if obj.status == 'completed' or obj.status == 'cancelled':
            return 0
            
        today = timezone.now().date()
        if obj.target_end_date < today:
            return -1 * (today - obj.target_end_date).days  # Negative days if overdue
        return (obj.target_end_date - today).days
    
    def get_is_overbudget(self, obj):
        """Check if project is over budget"""
        return obj.funds_spent > obj.budget

class ProjectListSerializer(serializers.ModelSerializer):
    """Simplified serializer for list views"""
    manager_name = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Project
        fields = [
            'id', 'title', 'project_type', 'category_name',
            'manager_name', 'start_date', 'target_end_date',
            'budget', 'status', 'location'
        ]
    
    def get_manager_name(self, obj):
        if obj.manager.first_name and obj.manager.last_name:
            return f"{obj.manager.first_name} {obj.manager.last_name}"
        return obj.manager.username
    
    def get_category_name(self, obj):
        return obj.category.name if obj.category else None


class ProjectBudgetUpdateSerializer(serializers.Serializer):
    budget = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    funds_allocated = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    funds_spent = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    notes = serializers.CharField(required=False, allow_blank=True)

class ProjectOfficialSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()

class ProjectDateUpdateSerializer(serializers.Serializer):
    start_date = serializers.DateField(required=False)
    target_end_date = serializers.DateField(required=False)
    actual_end_date = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)

class ProjectUpdateMediaSerializer(serializers.ModelSerializer):
    """Serializer for ProjectUpdateMedia model"""
    
    class Meta:
        model = ProjectUpdateMedia
        fields = [
            'id', 'media_type', 'file' 'caption', 'uploaded_at'
        ]
        read_only_fields = ['uploaded_at']
    

class DailyProjectUpdateSerializer(serializers.ModelSerializer):
    """Serializer for DailyProjectUpdate model"""
    submitted_by_details = ProjectUserSerializer(source='submitted_by', read_only=True)
    project_details = ProjectListSerializer(source='project', read_only=True)
    media_files = ProjectUpdateMediaSerializer(many=True, read_only=True)
    
    class Meta:
        model = DailyProjectUpdate
        fields = [
            'id', 'project', 'project_details', 'date', 
            'submitted_by', 'submitted_by_details', 'summary',
            'challenges', 'achievements', 'next_steps',
            'funds_spent_today', 'created_at', 'updated_at',
            'media_files'
        ]
        read_only_fields = ['created_at', 'updated_at', 'submitted_by']

class DailyProjectUpdateListSerializer(serializers.ModelSerializer):
    """Simplified serializer for list views of DailyProjectUpdate"""
    project_title = serializers.CharField(source='project.title', read_only=True)
    submitted_by_name = serializers.SerializerMethodField()
    media_count = serializers.SerializerMethodField()
    
    class Meta:
        model = DailyProjectUpdate
        fields = [
            'id', 'project', 'project_title', 'date', 
            'submitted_by_name', 'summary', 'funds_spent_today',
            'created_at', 'media_count'
        ]
    
    def get_submitted_by_name(self, obj):
        if obj.submitted_by.first_name and obj.submitted_by.last_name:
            return f"{obj.submitted_by.first_name} {obj.submitted_by.last_name}"
        return obj.submitted_by.username
    
    def get_media_count(self, obj):
        return obj.media_files.count()
    

class ProjectTeamMemberSerializer(serializers.ModelSerializer):
    """Serializer for ProjectTeamMember model"""
    user_details = ProjectUserSerializer(source='user', read_only=True)
    
    class Meta:
        model = ProjectTeamMember
        fields = [
            'id', 'project', 'user', 'user_details', 'role', 
            'responsibilities', 'join_date', 'end_date', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

class ProjectTeamMemberCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating ProjectTeamMember with validation"""
    
    class Meta:
        model = ProjectTeamMember
        fields = [
            'project', 'user', 'role', 'responsibilities', 
            'join_date', 'end_date'
        ]
    
    def validate(self, data):
        """
        Check that the user is not already a team member for this project
        """
        project = data.get('project')
        user = data.get('user')
        
        # Skip validation if updating an existing instance
        if self.instance:
            # If we're not changing the project or user, skip validation
            if self.instance.project == project and self.instance.user == user:
                return data
        
        # Check if this user is already a team member for this project
        if ProjectTeamMember.objects.filter(project=project, user=user).exists():
            raise serializers.ValidationError(
                "This user is already a team member for this project."
            )
        
        return data






class MilestoneDependencySerializer(serializers.ModelSerializer):
    """Serializer for milestone dependencies"""
    class Meta:
        model = ProjectMilestone
        fields = ['id', 'title', 'status', 'due_date']

class ProjectMilestoneSerializer(serializers.ModelSerializer):
    """Serializer for ProjectMilestone model with related data"""
    assigned_to = ProjectUserSerializer(many=True, read_only=True)
    dependencies = MilestoneDependencySerializer(many=True, read_only=True)
    days_remaining = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    created_by_details = ProjectUserSerializer(source='created_by', read_only=True)
    
    class Meta:
        model = ProjectMilestone
        fields = [
            'id', 'project', 'title', 'description', 'due_date',
            'completion_date', 'status', 'priority', 'completion_percentage',
            'assigned_to', 'dependencies', 'deliverables', 'notes',
            'created_at', 'updated_at', 'created_by', 'created_by_details',
            'days_remaining', 'is_overdue'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']
    
    def get_days_remaining(self, obj):
        return obj.days_remaining()
    
    def get_is_overdue(self, obj):
        return obj.is_overdue()

class ProjectMilestoneCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating ProjectMilestone"""
    assigned_to_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        write_only=True
    )
    dependency_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        write_only=True
    )
    
    class Meta:
        model = ProjectMilestone
        fields = [
            'project', 'title', 'description', 'due_date',
            'completion_date', 'status', 'priority', 'completion_percentage',
            'assigned_to_ids', 'dependency_ids', 'deliverables', 'notes'
        ]
    
    def create(self, validated_data):
        assigned_to_ids = validated_data.pop('assigned_to_ids', [])
        dependency_ids = validated_data.pop('dependency_ids', [])
        
        # Set the created_by field to the current user
        validated_data['created_by'] = self.context['request'].user
        
        milestone = ProjectMilestone.objects.create(**validated_data)
        
        # Add assigned users
        if assigned_to_ids:
            milestone.assigned_to.set(User.objects.filter(id__in=assigned_to_ids))
        
        # Add dependencies
        if dependency_ids:
            milestone.dependencies.set(ProjectMilestone.objects.filter(id__in=dependency_ids))
        
        return milestone
    
    def update(self, instance, validated_data):
        assigned_to_ids = validated_data.pop('assigned_to_ids', None)
        dependency_ids = validated_data.pop('dependency_ids', None)
        
        # Update the instance with validated data
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        
        # Update assigned users if provided
        if assigned_to_ids is not None:
            instance.assigned_to.set(User.objects.filter(id__in=assigned_to_ids))
        
        # Update dependencies if provided
        if dependency_ids is not None:
            instance.dependencies.set(ProjectMilestone.objects.filter(id__in=dependency_ids))
        
        return instance
    
    def validate(self, data):
        """
        Validate milestone data
        """
        # Check that due_date is not in the past for new milestones
        if not self.instance and 'due_date' in data:
            if data['due_date'] < timezone.now().date():
                raise serializers.ValidationError(
                    {"due_date": "Due date cannot be in the past."}
                )
        
        # Check that completion_date is not in the future
        if 'completion_date' in data and data['completion_date']:
            if data['completion_date'] > timezone.now().date():
                raise serializers.ValidationError(
                    {"completion_date": "Completion date cannot be in the future."}
                )
        
        # If status is completed, ensure completion_date is set
        if data.get('status') == 'completed' and not data.get('completion_date'):
            data['completion_date'] = timezone.now().date()
        
        # If status is completed, ensure completion_percentage is 100
        if data.get('status') == 'completed':
            data['completion_percentage'] = 100
        
        # Check for circular dependencies
        if self.instance and 'dependency_ids' in data:
            if self.instance.id in data['dependency_ids']:
                raise serializers.ValidationError(
                    {"dependency_ids": "A milestone cannot depend on itself."}
                )
        
        return data
