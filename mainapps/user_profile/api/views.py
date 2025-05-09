
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, Prefetch
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from mainapps.email_system.emails import EmailThread, send_html_email

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from django.utils import timezone
from django.db.models import Q

from rest_framework.response import Response
from .serializers import CAddressSerializer, CombinedReadUserSerializer, CombinedUserProfileSerializer, DisabilityTypeSerializer
from django.shortcuts import get_object_or_404
from mainapps.common.models import Address
from mainapps.accounts.models import Disability, Industry, Expertise, Membership, PartnershipType, PartnershipLevel, Skill, UserProfile
from .serializers import (
    IndustrySerializer, ExpertiseSerializer, MembershipSerializer, PartnershipTypeSerializer,
    PartnershipLevelSerializer, ProfileSerialIzer, ProfileSerialIzerAttachment, SkillSerializer
)
from django.contrib.auth import get_user_model

User = get_user_model()

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

class IsAdminUser(permissions.BasePermission):
    """
    Permission to only allow admin users to access the view.
    """
    def has_permission(self, request, view):
        return request.user.profile.is_DB_admin and request.user.is_verified

class UserProfileViewSet(viewsets.ModelViewSet):
    """
    API endpoint for user profiles
    """
    queryset = UserProfile.objects.all()
    serializer_class = CombinedUserProfileSerializer
    
    def get_queryset(self):
        queryset = UserProfile.objects.all()
        
        # Filter by KYC status if requested
        kyc_status = self.request.query_params.get('kyc_status', None)
        if kyc_status:
            queryset = queryset.filter(kyc_status=kyc_status)
            
        # Search functionality
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(user__first_name__icontains=search) | 
                Q(user__last_name__icontains=search) | 
                Q(user__email__icontains=search)
            )
            
        return queryset
    
    @action(detail=False, methods=['get'])
    def kyc_stats(self, request):
        """
        Get statistics about KYC submissions
        """
        pending_count = UserProfile.objects.filter(kyc_status='pending').count()
        approved_count = UserProfile.objects.filter(kyc_status='approved').count()
        rejected_count = UserProfile.objects.filter(kyc_status='rejected').count()
        flagged_count = UserProfile.objects.filter(kyc_status='flagged').count()
        scammer_count = UserProfile.objects.filter(kyc_status='scammer').count()
        
        return Response({
            'pending': pending_count,
            'approved': approved_count,
            'rejected': rejected_count,
            'flagged': flagged_count,
            'scammer': scammer_count,
            'total': pending_count + approved_count + rejected_count + flagged_count + scammer_count
        })
    
    @action(detail=False, methods=['get'])
    def kyc_all(self, request):
        """
        Get all KYC submissions grouped by status
        """
        pending = self.get_queryset().filter(kyc_status='pending')
        approved = self.get_queryset().filter(kyc_status='approved')
        rejected = self.get_queryset().filter(kyc_status='rejected')
        flagged = self.get_queryset().filter(kyc_status='flagged')
        scammer = self.get_queryset().filter(kyc_status='scammer')
        
        return Response({
            'pending': CombinedUserProfileSerializer(pending, many=True).data,
            'approved': CombinedUserProfileSerializer(approved, many=True).data,
            'rejected': CombinedUserProfileSerializer(rejected, many=True).data,
            'flagged': CombinedUserProfileSerializer(flagged, many=True).data,
            'scammer': CombinedUserProfileSerializer(scammer, many=True).data,
        })
    
    @action(detail=True, methods=['get'], permission_classes=[IsAdminUser])
    def kyc_documents(self, request, pk=None):
        """
        Retrieve KYC documents for a specific profile
        """
        profile = self.get_object()
        
        # Check if KYC has been submitted
        if not profile.kyc_submission_date:
            return Response(
                {"detail": "This user has not submitted KYC documents."},
                status=status.HTTP_404_NOT_FOUND
            )
            
        # Return document URLs and KYC information
        return Response({
            "id_document_type": profile.id_document_type,
            "id_document_number": profile.id_document_number,
            "id_document_image_front": request.build_absolute_uri(profile.id_document_image_front.url) if profile.id_document_image_front else None,
            "id_document_image_back": request.build_absolute_uri(profile.id_document_image_back.url) if profile.id_document_image_back else None,
            "selfie_image": request.build_absolute_uri(profile.selfie_image.url) if profile.selfie_image else None,
            "kyc_submission_date": profile.kyc_submission_date,
            "kyc_status": profile.kyc_status,
            "kyc_verification_date": profile.kyc_verification_date,
            "kyc_rejection_reason": profile.kyc_rejection_reason,
        })
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def verify_kyc(self, request, pk=None):
        """
        Update KYC status (approve, reject, flag, mark as scammer)
        """
        profile = self.get_object()
        action = request.data.get('action')
        
        if not profile.kyc_submission_date:
            return Response(
                {"error": "This user has not submitted KYC documents for verification."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if action == 'approve':
            profile.is_kyc_verified = True
            profile.kyc_status = 'approved'
            profile.kyc_verification_date = timezone.now()
            profile.kyc_rejection_reason = None
            profile.save()
            
            return Response({
                "message": "KYC verification approved successfully.",
                "profile": CombinedUserProfileSerializer(profile).data
            })
            
        elif action == 'reject':
            reason = request.data.get('reason')
            if not reason:
                return Response(
                    {"error": "A reason must be provided for rejection."},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            profile.is_kyc_verified = False
            profile.kyc_status = 'rejected'
            profile.kyc_verification_date = None
            profile.kyc_rejection_reason = reason
            profile.save()
            
            return Response({
                "message": "KYC verification rejected.",
                "profile": CombinedUserProfileSerializer(profile).data
            })
            
        elif action == 'flag':
            reason = request.data.get('reason')
            if not reason:
                return Response(
                    {"error": "A reason must be provided for flagging."},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            profile.is_kyc_verified = False
            profile.kyc_status = 'flagged'
            profile.kyc_verification_date = None
            profile.kyc_rejection_reason = reason
            profile.save()
            
            return Response({
                "message": "User flagged for review.",
                "profile": CombinedUserProfileSerializer(profile).data
            })
            
        elif action == 'mark_scammer':
            reason = request.data.get('reason')
            if not reason:
                return Response(
                    {"error": "A reason must be provided when marking as scammer."},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            profile.is_kyc_verified = False
            profile.kyc_status = 'scammer'
            profile.kyc_verification_date = None
            profile.kyc_rejection_reason = reason
            profile.save()
            
            return Response({
                "message": "User marked as scammer.",
                "profile": CombinedUserProfileSerializer(profile).data
            })
            
        else:
            return Response(
                {"error": "Invalid action. Use 'approve', 'reject', 'flag', or 'mark_scammer'."},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def bulk_verify(self, request):
        """
        Bulk update KYC status for multiple profiles
        """
        profile_ids = request.data.get('profile_ids', [])
        action = request.data.get('action')
        reason = request.data.get('reason', '')
        
        if not profile_ids:
            return Response(
                {"error": "No profile IDs provided."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if action not in ['approve', 'reject', 'flag', 'mark_scammer']:
            return Response(
                {"error": "Invalid action. Use 'approve', 'reject', 'flag', or 'mark_scammer'."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if action in ['reject', 'flag', 'mark_scammer'] and not reason:
            return Response(
                {"error": f"A reason must be provided for {action} action."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Get profiles with submitted KYC
        profiles = UserProfile.objects.filter(
            id__in=profile_ids,
            kyc_submission_date__isnull=False
        )
        
        if not profiles:
            return Response(
                {"error": "No valid profiles found with KYC submissions."},
                status=status.HTTP_404_NOT_FOUND
            )
            
        # Update profiles based on action
        updated_count = 0
        for profile in profiles:
            if action == 'approve':
                profile.is_kyc_verified = True
                profile.kyc_status = 'approved'
                profile.kyc_verification_date = timezone.now()
                profile.kyc_rejection_reason = None
            else:
                profile.is_kyc_verified = False
                profile.kyc_status = action.replace('mark_', '')
                profile.kyc_verification_date = None
                profile.kyc_rejection_reason = reason
                
            profile.save()
            updated_count += 1
            
        return Response({
            "message": f"Successfully updated {updated_count} profiles with '{action}' status.",
            "updated_count": updated_count
        })


    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def send_kyc_reminder(self, request, pk=None):
        """
        Send a reminder email to the user to complete their KYC verification
        """
        try:
            profile = self.get_object()
            user = profile.user
            
            if not user or not user.email:
                return Response(
                    {"error": "User does not have a valid email address."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if user has already completed KYC
            if profile.is_kyc_verified:
                return Response(
                    {"error": "This user has already been verified."},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            # Prepare email content
            subject = "Complete Your KYC Verification - Destiny Builders Africa"
            message = f"Hello {user.first_name or user.username},\n\nPlease complete your KYC verification to fully access all features of Destiny Builders Africa."
            to_email = [user.email]
            
            # Context for the email template
            context = {
                'user_name': user.first_name or user.username,
                'profile_url': 'https://www.destinybuilders.africa/profile/update',
                'current_year': timezone.now().year
            }
            
            # Send the email
            html_file = 'emails/kyc_reminder.html'
            html_content = render_to_string(html_file, context)
            text_content = strip_tags(html_content)
            
            msg = EmailMultiAlternatives(subject, text_content, settings.EMAIL_HOST_USER, to_email)
            msg.attach_alternative(html_content, "text/html")
            EmailThread(msg).start()
            
            
            return Response({
                "success": True,
                "message": f"KYC reminder email sent to {user.email}."
            })
            
        except Exception as e:
            print(f"Error sending KYC reminder email: {str(e)}")
            return Response(
                {"error": f"Failed to send reminder: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for retrieving users with their profile data
    """
    queryset = User.objects.select_related('profile', 'disability').all()
    serializer_class = CombinedReadUserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """
        Optionally restricts the returned users based on query parameters
        """
        queryset = super().get_queryset()
        
        # Filter by verified status if specified
        is_verified = self.request.query_params.get('is_verified')
        if is_verified is not None:
            is_verified = is_verified.lower() == 'true'
            queryset = queryset.filter(is_verified=is_verified)
        
        # Filter by staff status if specified
        is_staff = self.request.query_params.get('is_staff')
        if is_staff is not None:
            is_staff = is_staff.lower() == 'true'
            queryset = queryset.filter(is_staff=is_staff)
        
        # Filter by worker status if specified
        is_worker = self.request.query_params.get('is_worker')
        if is_worker is not None:
            is_worker = is_worker.lower() == 'true'
            queryset = queryset.filter(is_worker=is_worker)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """
        Return the currently authenticated user
        """
        serializer = self.get_serializer(request.user)
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