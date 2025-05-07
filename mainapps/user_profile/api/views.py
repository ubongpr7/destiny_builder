
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, Prefetch
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .serializers import CAddressSerializer, DisabilityTypeSerializer
from django.shortcuts import get_object_or_404
from mainapps.common.models import Address
from mainapps.accounts.models import Disability, Industry, Expertise, Membership, PartnershipType, PartnershipLevel, Skill, UserProfile
from .serializers import (
    IndustrySerializer, ExpertiseSerializer, MembershipSerializer, PartnershipTypeSerializer,
    PartnershipLevelSerializer, ProfileSerialIzer, ProfileSerialIzerAttachment, SkillSerializer
)

class BaseReferenceViewSet(viewsets.ReadOnlyModelViewSet):
    """Base viewset for reference data with caching"""
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    ordering = ['name']
    
    @method_decorator(cache_page(60 * 60 * 24))  # Cache for 24 hours
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    @method_decorator(cache_page(60 * 60 * 24))  # Cache for 24 hours
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)


class IndustryViewSet(BaseReferenceViewSet):
    queryset = Industry.objects.all()
    serializer_class = IndustrySerializer
    search_fields = ['name']


class ExpertiseViewSet(BaseReferenceViewSet):
    queryset = Expertise.objects.all()
    serializer_class = ExpertiseSerializer
    search_fields = ['name']

class MembershipViewSet(BaseReferenceViewSet):
    queryset = Membership.objects.all()
    serializer_class = MembershipSerializer
    search_fields = ['name']


class SkillViewSet(BaseReferenceViewSet):
    queryset = Skill.objects.all()
    serializer_class = SkillSerializer
    search_fields = ['name', 'description']


class PartnershipTypeViewSet(BaseReferenceViewSet):
    queryset = PartnershipType.objects.all()
    serializer_class = PartnershipTypeSerializer
    search_fields = ['name', 'description']

class DisabilityViewSet(BaseReferenceViewSet):
    queryset = Disability.objects.all()
    serializer_class = DisabilityTypeSerializer
    search_fields = ['name', 'description']


class PartnershipLevelViewSet(BaseReferenceViewSet):
    queryset = PartnershipLevel.objects.all()
    serializer_class = PartnershipLevelSerializer
    search_fields = ['name', 'description']
class ProfileViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.all()
    serializer_class = ProfileSerialIzerAttachment
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        expertise_ids = None
        if 'expertise' in request.data:
            # Handle both JSON and form data formats
            if isinstance(request.data, dict):  # JSON data
                expertise_ids = request.data.get('expertise')
            else:  # Form data
                expertise_ids = request.data.getlist('expertise')
            
            # Convert string IDs to integers if needed
            if expertise_ids and isinstance(expertise_ids[0], str):
                expertise_ids = [int(id) for id in expertise_ids]
        
        if request.content_type and 'multipart/form-data' in request.content_type:
            # Create a mutable copy of request.data
            mutable_data = request.data.copy()
            
            if 'expertise' in mutable_data:
                mutable_data.pop('expertise')
            
            serializer = self.get_serializer(instance, data=mutable_data, partial=partial)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            
            # Update KYC submission date if KYC documents are being submitted
            if any(field in request.data for field in ['id_document_image_front', 'id_document_image_back', 'selfie_image']):
                from django.utils import timezone
                instance.kyc_submission_date = timezone.now()
                instance.save()
        else:
            mutable_data = request.data.copy() if isinstance(request.data, dict) else dict(request.data)
            
            # Remove expertise from data as we'll handle it separately
            if 'expertise' in mutable_data:
                mutable_data.pop('expertise')
            
            serializer = self.get_serializer(instance, data=mutable_data, partial=partial)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
        
        # Handle expertise many-to-many relationship if expertise_ids is provided
        if expertise_ids is not None:
            instance.expertise.clear()
            
            from mainapps.accounts.models import Expertise  # Replace with your actual model import
            for expertise_id in expertise_ids:
                try:
                    expertise = Expertise.objects.get(id=expertise_id)
                    instance.expertise.add(expertise)
                except Expertise.DoesNotExist:
                    pass
        
        serializer = self.get_serializer(instance)
        print(serializer.data)
        return Response(serializer.data)




class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = CAddressSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'pk'
    
    def get_queryset(self):
        """
        Filter addresses by the user_profile_id parameter
        """
        user_profile_id = self.kwargs.get('user_profile_id')
        return Address.objects.filter(user_profile__id=user_profile_id)
    
    def perform_create(self, serializer):
        """
        Create a new address for the specified user profile
        """
        user_profile_id = self.kwargs.get('user_profile_id')
        user_profile = get_object_or_404(UserProfile, id=user_profile_id)
        
        # Check if the current user has permission to modify this profile
        if user_profile.user != self.request.user and not self.request.user.is_staff:
            return Response(
                {"detail": "You do not have permission to perform this action."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Create the address linked to the user profile
        serializer.save()
        user_profile.address= serializer.instance
        user_profile.save()
    
    def perform_update(self, serializer):
        """
        Update an address for the specified user profile
        """
        user_profile_id = self.kwargs.get('user_profile_id')
        user_profile = get_object_or_404(UserProfile, id=user_profile_id)
        
        # Check if the current user has permission to modify this profile
        if user_profile.user != self.request.user and not self.request.user.is_staff:
            return Response(
                {"detail": "You do not have permission to perform this action."},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer.save()
        print(serializer.data)
    
    def perform_destroy(self, instance):
        """
        Delete an address for the specified user profile
        """
        user_profile_id = self.kwargs.get('user_profile_id')
        user_profile = get_object_or_404(UserProfile, id=user_profile_id)
        
        # Check if the current user has permission to modify this profile
        if user_profile.user != self.request.user and not self.request.user.is_staff:
            return Response(
                {"detail": "You do not have permission to perform this action."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        instance.delete()