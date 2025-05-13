from rest_framework import serializers
from django.contrib.auth import get_user_model

from mainapps.inventory.models import Asset
from ..models import DailyProjectUpdate, Project, ProjectAsset, ProjectCategory, ProjectExpense, ProjectMilestone, ProjectTeamMember, ProjectUpdateMedia
from django.utils import timezone
User = get_user_model()



class ProjectUserSerializer(serializers.ModelSerializer):
    profile_image = serializers.SerializerMethodField()
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'profile_image']
        read_only_fields = ['profile_image']
    def get_profile_image(self, obj):
        if obj.profile:
            return obj.profile.profile_image.url if obj.profile.profile_image else None

class ProjectCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectCategory
        fields = ['id', 'name', 'description']

class ProjectSerializer(serializers.ModelSerializer):
    manager_details = ProjectUserSerializer(source='manager', read_only=True)
    officials_details = ProjectUserSerializer(source='officials', many=True, read_only=True)
    category_details = ProjectCategorySerializer(source='category', read_only=True)
    team_members = serializers.SerializerMethodField()
    manager = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    officials = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), many=True, required=False)
    category = serializers.PrimaryKeyRelatedField(queryset=ProjectCategory.objects.all(), allow_null=True)
    
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
            'created_at', 'updated_at', 'days_remaining', 'team_members'
        ]
        read_only_fields = ['created_at', 'updated_at']
    def get_team_members(self, obj):
        """Get team members for the project"""
        team_members = ProjectTeamMember.objects.filter(project=obj)
        users= User.objects.filter(id__in=[member.user.id for member in team_members])
        # Serialize the user details
        return ProjectUserSerializer(users, many=True).data
    
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






class ProjectMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for Project references"""
    class Meta:
        model = Project
        fields = ['id', 'title', 'status']

class ProjectUpdateMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for DailyProjectUpdate references"""
    class Meta:
        model = DailyProjectUpdate
        fields = ['id', 'date', 'summary']

class ProjectExpenseSerializer(serializers.ModelSerializer):
    """Serializer for ProjectExpense model with related data"""
    incurred_by_details = ProjectUserSerializer(source='incurred_by', read_only=True)
    approved_by_details = ProjectUserSerializer(source='approved_by', read_only=True)
    project_details = ProjectMinimalSerializer(source='project', read_only=True)
    update_details = ProjectUpdateMinimalSerializer(source='update', read_only=True)
    receipt_url = serializers.SerializerMethodField()
    
    class Meta:
        model = ProjectExpense
        fields = [
            'id', 'project', 'project_details', 'update', 'update_details',
            'title', 'description', 'amount', 'date_incurred',
            'incurred_by', 'incurred_by_details', 'receipt', 'receipt_url',
            'category', 'status', 'approved_by', 'approved_by_details',
            'approval_date', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'approved_by', 'approval_date']
    
    def get_receipt_url(self, obj):
        if obj.receipt:
            return self.context['request'].build_absolute_uri(obj.receipt.url)
        return None

class ProjectExpenseCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating ProjectExpense"""
    
    class Meta:
        model = ProjectExpense
        fields = [
            'project', 'update', 'title', 'description', 'amount',
            'date_incurred', 'incurred_by', 'receipt', 'category',
            'status', 'notes'
        ]
        read_only_fields = ['approved_by', 'approval_date']
    
    def validate(self, data):
        """
        Validate expense data
        """
        if 'date_incurred' in data:
            if data['date_incurred'] > timezone.now().date():
                raise serializers.ValidationError(
                    {"date_incurred": "Expense date cannot be in the future."}
                )
        
        if 'amount' in data and data['amount'] <= 0:
            raise serializers.ValidationError(
                {"amount": "Expense amount must be greater than zero."}
            )
        
        if 'update' in data and data['update'] and 'project' in data:
            if data['update'].project.id != data['project'].id:
                raise serializers.ValidationError(
                    {"update": "The update must belong to the same project."}
                )
        
        if not self.instance and 'status' in data and data['status'] != 'pending':
            if not self.context['request'].user.is_staff: 
                data['status'] = 'pending'
        
        return data

class ExpenseApprovalSerializer(serializers.Serializer):
    """Serializer for approving or rejecting expenses"""
    notes = serializers.CharField(required=False, allow_blank=True)

class ExpenseReimbursementSerializer(serializers.Serializer):
    """Serializer for marking expenses as reimbursed"""
    notes = serializers.CharField(required=False, allow_blank=True)
    reimbursement_date = serializers.DateField(default=timezone.now().date())




class AssetSerializer(serializers.ModelSerializer):
    """Serializer for Asset model"""
    class Meta:
        model = Asset
        fields = ['id', 'name', 'asset_type', 'model', 'serial_number']

class ProjectAssetSerializer(serializers.ModelSerializer):
    """Serializer for ProjectAsset model with related data"""
    assigned_by_details = ProjectUserSerializer(source='assigned_by', read_only=True)
    project_details = ProjectMinimalSerializer(source='project', read_only=True)
    asset = AssetSerializer(read_only=True)
    
    class Meta:
        model = ProjectAsset
        fields = [
            'id', 'project', 'project_details', 'asset',
            'assigned_date', 'assigned_by', 'assigned_by_details',
            'return_date', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
class ProjectAssetCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating ProjectAsset"""
    
    class Meta:
        model = ProjectAsset
        fields = [
            'project', 'asset', 'assigned_by', 'assigned_date',
            'return_date', 'notes'
        ]
    
    def validate(self, data):
        """
        Validate asset assignment data
        """
        # Check that assigned_date is not in the future
        if 'assigned_date' in data:
            if data['assigned_date'] > timezone.now().date():
                raise serializers.ValidationError(
                    {"assigned_date": "Assignment date cannot be in the future."}
                )
        
        # Check that return_date is not before assigned_date
        if 'return_date' in data and data['return_date'] and 'assigned_date' in data:
            if data['return_date'] < data['assigned_date']:
                raise serializers.ValidationError(
                    {"return_date": "Return date cannot be before assignment date."}
                )
        
        # Check that the asset is not already assigned to another project
        if self.instance is None:  # Only check on create
            asset = data.get('asset')
            active_assignments = ProjectAsset.objects.filter(
                asset=asset,
                return_date__isnull=True
            )
            if active_assignments.exists():
                raise serializers.ValidationError(
                    {"asset": "This asset is already assigned to another project."}
                )
        
        return data

class AssetReturnSerializer(serializers.Serializer):
    """Serializer for returning assets"""
    return_date = serializers.DateField(default=timezone.now().date())
    notes = serializers.CharField(required=False, allow_blank=True)



class ProjectUpdateMediaSerializer(serializers.ModelSerializer):
    """Serializer for ProjectUpdateMedia model"""
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = ProjectUpdateMedia
        fields = [
            'id', 'update', 'media_type', 'file', 'file_url',
            'caption', 'uploaded_at'
        ]
        read_only_fields = ['uploaded_at']
    
    def get_file_url(self, obj):
        if obj.file:
            return self.context['request'].build_absolute_uri(obj.file.url)
        return None

class DailyProjectUpdateSerializer(serializers.ModelSerializer):
    """Serializer for DailyProjectUpdate model with related data"""
    submitted_by_details = ProjectUserSerializer(source='submitted_by', read_only=True)
    project_details = ProjectMinimalSerializer(source='project', read_only=True)
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
        read_only_fields = ['created_at', 'updated_at']
    
class DailyProjectUpdateCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating DailyProjectUpdate"""
    
    class Meta:
        model = DailyProjectUpdate
        fields = [
            'project', 'date', 'submitted_by', 'summary',
            'challenges', 'achievements', 'next_steps',
            'funds_spent_today'
        ]
    
    def validate(self, data):
        """
        Validate update data
        """
        # Check that date is not in the future
        if 'date' in data:
            if data['date'] > timezone.now().date():
                raise serializers.ValidationError(
                    {"date": "Update date cannot be in the future."}
                )
        
        # Ensure funds_spent_today is non-negative
        if 'funds_spent_today' in data and data['funds_spent_today'] < 0:
            raise serializers.ValidationError(
                {"funds_spent_today": "Funds spent must be non-negative."}
            )
        
        # Check for duplicate update for the same project and date
        project = data.get('project')
        date = data.get('date')
        
        if project and date:
            # Skip validation if updating an existing instance with the same project and date
            if self.instance and self.instance.project == project and self.instance.date == date:
                return data
                
            if DailyProjectUpdate.objects.filter(project=project, date=date).exists():
                raise serializers.ValidationError(
                    {"date": "An update for this project on this date already exists."}
                )
        
        return data

class ProjectUpdateMediaCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating ProjectUpdateMedia"""
    
    class Meta:
        model = ProjectUpdateMedia
        fields = [
            'update', 'media_type', 'file', 'caption'
        ]
    
    def validate(self, data):
        """
        Validate media data
        """
        # Validate file type based on media_type
        media_type = data.get('media_type')
        file = data.get('file')
        
        if media_type and file:
            file_extension = file.name.split('.')[-1].lower()
            
            if media_type == 'image' and file_extension not in ['jpg', 'jpeg', 'png', 'gif']:
                raise serializers.ValidationError(
                    {"file": "Invalid image format. Supported formats: jpg, jpeg, png, gif."}
                )
            elif media_type == 'video' and file_extension not in ['mp4', 'mov', 'avi', 'wmv']:
                raise serializers.ValidationError(
                    {"file": "Invalid video format. Supported formats: mp4, mov, avi, wmv."}
                )
            elif media_type == 'document' and file_extension not in ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt']:
                raise serializers.ValidationError(
                    {"file": "Invalid document format. Supported formats: pdf, doc, docx, xls, xlsx, ppt, pptx, txt."}
                )
            elif media_type == 'audio' and file_extension not in ['mp3', 'wav', 'ogg']:
                raise serializers.ValidationError(
                    {"file": "Invalid audio format. Supported formats: mp3, wav, ogg."}
                )
        
        return data
