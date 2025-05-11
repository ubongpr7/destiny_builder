from rest_framework import serializers
from django.contrib.auth import get_user_model
from ..models import DailyProjectUpdate, Project, ProjectCategory, ProjectUpdateMedia

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