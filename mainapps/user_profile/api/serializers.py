from mainapps.accounts.models import Disability, Membership, Industry, Expertise, PartnershipType, PartnershipLevel, Skill, UserProfile
from rest_framework import serializers

from mainapps.common.api.serializers import CitySerializer, CountrySerializer, RegionSerializer, SubRegionSerializer
from mainapps.common.models import Address
from django.contrib.auth import get_user_model


User = get_user_model()

class IndustrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Industry
        fields = ['id', 'name']

class MembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = ['id', 'name']


class ExpertiseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expertise
        fields = ['id', 'name']


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ['id', 'name', 'description']


class PartnershipTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartnershipType
        fields = ['id', 'name', 'description']
class DisabilityTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Disability
        fields = ['id', 'name', 'description']


class PartnershipLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartnershipLevel
        fields = ['id', 'name', 'description', 'benefits']


class ProfileSerialIzer(serializers.ModelSerializer):
    class Meta:
        model=UserProfile
        fields="__all__"
        depth=1


class ProfileSerialIzerAttachment(serializers.ModelSerializer):
    
    class Meta:
        # depth=1
        model = UserProfile
        fields = '__all__'
        
    def update(self, instance, validated_data):
        file_fields = ['id_document_image_front', 'id_document_image_back', 'selfie_image', 'profile_image']
        
        for field in file_fields:
            if field in validated_data:
                setattr(instance, field, validated_data.pop(field))
        
        # Update the rest of the fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
            
        instance.save()
        return instance


class CombinedUserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer that combines User and UserProfile data into a single efficient response.
    """
    # User fields
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    is_verified = serializers.BooleanField(source='user.is_verified', read_only=True)
    is_staff = serializers.BooleanField(source='user.is_staff', read_only=True)
    is_worker = serializers.BooleanField(source='user.is_worker', read_only=True)
    user_date_of_birth = serializers.DateField(source='user.date_of_birth', read_only=True)
    disabled = serializers.BooleanField(source='user.disabled', read_only=True)
    linkedin_profile = serializers.URLField(source='user.linkedin_profile', read_only=True)
    profile_link = serializers.URLField(source='user.profile_link', read_only=True)
    sex = serializers.CharField(source='user.sex', read_only=True)
    
    # Related fields with nested serialization
    disability = serializers.SerializerMethodField()
    industry_details = serializers.SerializerMethodField()
    expertise_details = serializers.SerializerMethodField()
    partnership_type_details = serializers.SerializerMethodField()
    partnership_level_details = serializers.SerializerMethodField()
    address_details = serializers.SerializerMethodField()
    
    # Computed fields
    role_summary = serializers.SerializerMethodField()
    kyc_status = serializers.SerializerMethodField()
    
    class Meta:
        model = UserProfile
        fields = [
            # User fields
            'id','user_id',  'email', 'first_name', 'last_name', 'username', 'full_name',
            'is_verified', 'is_staff', 'is_worker', 'user_date_of_birth',
            'disabled', 'linkedin_profile', 'profile_link', 'sex',
            
            # UserProfile basic fields
            'membership_type', 'phone_number', 'bio', 'profile_image',
            'date_of_birth', 'organization', 'position', 'industry',
            'company_size', 'company_website', 'created_at', 'updated_at',
            
            # UserProfile KYC fields
            'is_kyc_verified', 'id_document_type', 'id_document_number',
            'id_document_image_front', 'id_document_image_back', 'selfie_image',
            'kyc_submission_date', 'kyc_verification_date', 'kyc_rejection_reason',
            
            # UserProfile role fields
            'is_executive', 'is_ceo', 'is_project_manager', 'is_donor',
            'is_volunteer', 'is_partner', 'is_DB_staff', 'is_standard_member',
            'is_DB_executive', 'is_DB_admin', 'is_country_director', 'is_regional_head',
            
            # UserProfile relationship fields
            'industry', 'partnership_type', 'partnership_level', 'assigned_region',
            'partnership_start_date',
            
            # Nested and computed fields
            'disability', 'industry_details', 'expertise_details',
            'partnership_type_details', 'partnership_level_details',
            'address_details', 'role_summary', 'kyc_status'
        ]
    
    def get_disability(self, obj):
        """Return disability details if user has a disability"""
        if hasattr(obj, 'user') and obj.user and obj.user.disability:
            return {
                'id': obj.user.disability.id,
                'name': obj.user.disability.name,
                'description': obj.user.disability.description
            }
        return None
    
    def get_industry_details(self, obj):
        """Return industry details if available"""
        if obj.industry:
            return {
                'id': obj.industry.id,
                'name': obj.industry.name,
                'description': getattr(obj.industry, 'description', None)
            }
        return None
    
    def get_expertise_details(self, obj):
        """Return list of expertise details"""
        if hasattr(obj, 'expertise'):
            return [
                {
                    'id': exp.id,
                    'name': exp.name,
                    'description': getattr(exp, 'description', None)
                }
                for exp in obj.expertise.all()
            ]
        return []
    
    def get_partnership_type_details(self, obj):
        """Return partnership type details if available"""
        if obj.partnership_type:
            return {
                'id': obj.partnership_type.id,
                'name': obj.partnership_type.name,
                'description': getattr(obj.partnership_type, 'description', None)
            }
        return None
    
    def get_partnership_level_details(self, obj):
        """Return partnership level details if available"""
        if obj.partnership_level:
            return {
                'id': obj.partnership_level.id,
                'name': obj.partnership_level.name,
                'description': getattr(obj.partnership_level, 'description', None)
            }
        return None
    
    def get_address_details(self, obj):
        """Return address details if available"""
        if obj.address:
            return {
                'id': obj.address.id,
                'street': obj.address.street,
                'street_number': obj.address.street_number,
                'apt_number': obj.address.apt_number,
                'postal_code': obj.address.postal_code,
                'country': getattr(obj.address.country, 'name', None) if hasattr(obj.address, 'country') else None,
                'region': getattr(obj.address.region, 'name', None) if hasattr(obj.address, 'region') else None,
                'subregion': getattr(obj.address.subregion, 'name', None) if hasattr(obj.address, 'subregion') else None,
                'city': getattr(obj.address.city, 'name', None) if hasattr(obj.address, 'city') else None,
            }
        return None
    
    def get_role_summary(self, obj):
        """Return a summary of user roles"""
        roles = []
        role_fields = [
            'is_executive', 'is_ceo', 'is_project_manager', 'is_donor',
            'is_volunteer', 'is_partner', 'is_DB_staff', 'is_standard_member',
            'is_DB_executive', 'is_DB_admin', 'is_country_director', 'is_regional_head'
        ]
        
        role_display_names = {
            'is_executive': 'Executive',
            'is_ceo': 'CEO',
            'is_project_manager': 'Project Manager',
            'is_donor': 'Donor',
            'is_volunteer': 'Volunteer',
            'is_partner': 'Partner',
            'is_DB_staff': 'DBEF Staff',
            'is_standard_member': 'Standard Member',
            'is_DB_executive': 'DBEF Executive',
            'is_DB_admin': 'DBEF Administrator',
            'is_country_director': 'Country Director',
            'is_regional_head': 'Regional Head'
        }
        
        for field in role_fields:
            if getattr(obj, field, False):
                roles.append(role_display_names.get(field, field.replace('is_', '').replace('_', ' ').replace('DB', 'DBEF').title()))
        
        return roles
    
    def get_kyc_status(self, obj):
        """Return KYC verification status with details"""
        if obj.is_kyc_verified:
            return {
                'status': 'verified',
                'verified_date': obj.kyc_verification_date
            }
        elif obj.kyc_submission_date:
            return {
                'status': 'pending',
                'submitted_date': obj.kyc_submission_date
            }
        elif obj.kyc_rejection_reason:
            return {
                'status': 'rejected',
                'reason': obj.kyc_rejection_reason
            }
        return {
            'status': 'not_submitted'
        }
    


class CombinedReadUserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model with profile data included
    """
    profile_data = CombinedUserProfileSerializer(source='profile', read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'username',
            'is_verified', 'is_staff', 'is_worker', 'date_of_birth',
            'disabled', 'linkedin_profile', 'profile_link', 'sex',
            'profile_data'
        ]

class KYCDocumentsSerializer(serializers.ModelSerializer):
    user_full_name = serializers.SerializerMethodField()
    user_email = serializers.SerializerMethodField()
    
    class Meta:
        model = UserProfile
        fields = [
            'id', 'user_full_name', 'user_email',
            'id_document_type', 'id_document_number',
            'id_document_image_front', 'id_document_image_back',
            'selfie_image', 'kyc_submission_date',
            'kyc_status', 'kyc_verification_date',
            'kyc_rejection_reason'
        ]
    
    def get_user_full_name(self, obj):
        if hasattr(obj, 'user') and obj.user:
            return f"{obj.user.first_name} {obj.user.last_name}"
        return ""
    
    def get_user_email(self, obj):
        if hasattr(obj, 'user') and obj.user:
            return obj.user.email
        return ""

class CAddressSerializer(serializers.ModelSerializer):
    country_details = CountrySerializer(source='country', read_only=True)
    region_details = RegionSerializer(source='region', read_only=True)
    subregion_details = SubRegionSerializer(source='subregion', read_only=True)
    city_details = CitySerializer(source='city', read_only=True)
    
    class Meta:
        model = Address
        fields = [
            'id', 'country', 'region', 'subregion', 'city', 
            'apt_number', 'street_number', 'street', 'postal_code',
            'country_details', 'region_details', 'subregion_details', 'city_details'
        ]
        read_only_fields = ['id']