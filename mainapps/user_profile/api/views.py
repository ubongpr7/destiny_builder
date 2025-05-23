import threading
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
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from django.utils import timezone
from django.db.models import Q

from rest_framework.response import Response

from mainapps.user_profile.api.utils import ReferenceGenerator, generate_certificate_pdf, send_certificate_email
from .serializers import CAddressSerializer, CombinedReadUserSerializer, CombinedUserProfileSerializer, DisabilityTypeSerializer, ProfileRoleSerializer
from django.shortcuts import get_object_or_404
from mainapps.common.models import Address
from mainapps.accounts.models import Disability, Industry, Expertise,VerificationCode, Membership, PartnershipType, PartnershipLevel, Skill, UserProfile
from .serializers import (
    IndustrySerializer, ExpertiseSerializer, MembershipSerializer, PartnershipTypeSerializer,
    PartnershipLevelSerializer, ProfileSerialIzer, ProfileSerialIzerAttachment, SkillSerializer
)
from django.contrib.auth import get_user_model
from rest_framework import generics

# Import notification service
from mainapps.notification.services import NotificationService

User = get_user_model()


# Notification helper functions
def send_notification_safely(func, *args, **kwargs):
    """Safely send a notification without disrupting the main flow if it fails"""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        print(f"Error sending notification: {str(e)}")
        return None


def send_kyc_approved_notification(profile, request=None):
    """Send notification when KYC is approved"""
    try:
        user = profile.user
        if not user:
            return False
            
        # Create context data for the notification
        context_data = {
            'app_name': settings.SITE_NAME,
            'user_first_name': user.first_name or user.username or 'there',
            'dashboard_url': f"{settings.SITE_URL}/dashboard"
        }
        
        # Send the notification
        NotificationService.create_notification(
            recipient=user,
            notification_type_name='verification_approved',
            context_data=context_data,
            action_url='/dashboard',
            priority='high',
            icon='check-circle',
            color='#4CAF50',  # Green color
            send_email=True,
            send_sms=True if hasattr(profile, 'phone_number') and profile.phone_number else False
        )
        
        return True
    except Exception as e:
        print(f"Error sending KYC approved notification: {e}")
        return False


def send_kyc_rejected_notification(profile, reason=None):
    """Send notification when KYC is rejected"""
    try:
        user = profile.user
        if not user:
            return False
            
        # Create context data for the notification
        context_data = {
            'app_name': settings.SITE_NAME,
            'user_first_name': user.first_name or user.username or 'there',
            'rejection_reason': reason or 'Please check your details and try again.',
            'profile_url': f"{settings.SITE_URL}/profile/update"
        }
        
        # Send the notification
        NotificationService.create_notification(
            recipient=user,
            notification_type_name='verification_rejected',
            context_data=context_data,
            action_url='/profile/update',
            priority='high',
            icon='alert-circle',
            color='#F44336',  # Red color
            send_email=True,
            send_sms=True if hasattr(profile, 'phone_number') and profile.phone_number else False
        )
        
        return True
    except Exception as e:
        print(f"Error sending KYC rejected notification: {e}")
        return False


def send_kyc_flagged_notification(profile, reason=None):
    """Send notification when KYC is flagged"""
    try:
        user = profile.user
        if not user:
            return False
            
        # Create context data for the notification
        context_data = {
            'app_name': settings.SITE_NAME,
            'user_first_name': user.first_name or user.username or 'there',
            'flag_reason': reason or 'Your verification requires additional review.',
            'profile_url': f"{settings.SITE_URL}/profile/update"
        }
        
        # Send the notification
        NotificationService.create_notification(
            recipient=user,
            notification_type_name='verification_flagged',
            context_data=context_data,
            action_url='/profile/update',
            priority='high',
            icon='alert-triangle',
            color='#FF9800',  # Orange color
            send_email=True,
            send_sms=True if hasattr(profile, 'phone_number') and profile.phone_number else False
        )
        
        return True
    except Exception as e:
        print(f"Error sending KYC flagged notification: {e}")
        return False


def send_kyc_reminder_notification(profile):
    """Send notification to remind user to complete KYC"""
    try:
        user = profile.user
        if not user:
            return False
            
        # Create context data for the notification
        context_data = {
            'app_name': settings.SITE_NAME,
            'user_first_name': user.first_name or user.username or 'there',
            'profile_url': f"{settings.SITE_URL}/profile/update"
        }
        
        # Send the notification
        NotificationService.create_notification(
            recipient=user,
            notification_type_name='profile_incomplete',
            context_data=context_data,
            action_url='/profile/update',
            priority='normal',
            icon='user-check',
            color='#FFC107',  # Yellow/amber color
            send_email=True
        )
        
        return True
    except Exception as e:
        print(f"Error sending KYC reminder notification: {e}")
        return False


def send_profile_updated_notification(profile):
    """Send notification when profile is updated"""
    try:
        user = profile.user
        if not user:
            return False
            
        # Create context data for the notification
        context_data = {
            'app_name': settings.SITE_NAME,
            'user_first_name': user.first_name or user.username or 'there',
            'profile_url': f"{settings.SITE_URL}/profile"
        }
        
        # Send the notification
        NotificationService.create_notification(
            recipient=user,
            notification_type_name='profile_updated',
            context_data=context_data,
            action_url='/profile',
            priority='low',
            icon='user',
            color='#2196F3',  # Blue color
            send_email=True
        )
        
        return True
    except Exception as e:
        print(f"Error sending profile updated notification: {e}")
        return False


def send_edit_code_notification(user, code, admin_user, admin_profile=None):
    """Send notification when edit code is requested"""
    try:
        if not user:
            return False
            
        # Create context data for the notification
        admin_name = f"{admin_user.first_name} {admin_user.last_name}".strip() or admin_user.username
        
        context_data = {
            'app_name': settings.SITE_NAME,
            'user_first_name': user.first_name or user.username or 'there',
            'verification_code': code,
            'admin_name': admin_name,
            'admin_email': admin_user.email
        }
        
        # Send the notification
        NotificationService.create_notification(
            recipient=user,
            notification_type_name='edit_code_requested',
            context_data=context_data,
            action_url=None,  # No action needed
            priority='high',
            icon='key',
            color='#9C27B0',  # Purple color
            send_email=True,
            send_sms=True  # Important security notification
        )
        
        return True
    except Exception as e:
        print(f"Error sending edit code notification: {e}")
        return False


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

class UserProfileRoleView(generics.RetrieveAPIView):
    serializer_class = ProfileRoleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):

        profile=self.request.user.profile
        if not profile:
            return Response({"detail": "Profile not found."}, status=status.HTTP_404_NOT_FOUND)
        return profile
    
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
        
        # Send notification for profile update
        send_notification_safely(send_profile_updated_notification, instance)
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

class IsAdminUser(permissions.BasePermission):
    """
    Permission to only allow admin users to access the view.
    """
    def has_permission(self, request, view):
        return request.user.profile.is_DB_admin and request.user.is_verified

class UserProfilePreviewViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for looking up user profiles by reference number
    """
    queryset = UserProfile.objects.filter(is_kyc_verified=True, kyc_status='approved')
    serializer_class = CombinedUserProfileSerializer 
    permission_classes = [permissions.IsAuthenticated,IsAdminUser] 
    lookup_field = 'reference'
    
    def get_serializer_class(self):
        """
        Return different serializers based on the request
        """
        # Use a more limited serializer for public access
        # if self.request.user and self.request.user.is_authenticated and self.request.user.is_staff:
        #     return CombinedUserProfileSerializer
        return CombinedUserProfileSerializer
    
    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve a user profile by reference number
        """
        reference = kwargs.get('reference')
        
        try:
            # Only return verified profiles
            profile = get_object_or_404(
                UserProfile, 
                reference=reference,
                # is_kyc_verified=True,
                # kyc_status='approved'
            )
            print('profile: ',profile)
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {"error": "Invalid reference number or profile not found."},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def list(self, request, *args, **kwargs):
        """
        Override list method to prevent listing all profiles
        """
        return Response(
            {"error": "Please provide a reference number to look up a specific profile."},
            status=status.HTTP_400_BAD_REQUEST
        )

    

class UserProfileViewSet(viewsets.ModelViewSet):
    """
    API endpoint for user profiles
    """
    queryset = UserProfile.objects.all()
    serializer_class = CombinedUserProfileSerializer
    
    # def get_queryset(self):
    #     queryset = UserProfile.objects.all()
        
    #     # Filter by KYC status if requested
    #     kyc_status = self.request.query_params.get('kyc_status', None)
    #     if kyc_status:
    #         queryset = queryset.filter(kyc_status=kyc_status)
            
    #     # Search functionality
    #     search = self.request.query_params.get('search', None)
    #     if search:
    #         queryset = queryset.filter(
    #             Q(user__first_name__icontains=search) | 
    #             Q(user__last_name__icontains=search) | 
    #             Q(user__email__icontains=search)
    #         )
            
    #     return queryset
    
    def get_queryset(self):
        queryset = UserProfile.objects.all()
        
        # Filter by KYC status if requested
        kyc_status = self.request.query_params.get('kyc_status', None)
        if kyc_status:
            queryset = queryset.filter(kyc_status=kyc_status)
            
        # Geographic filtering
        country_id = self.request.query_params.get('country_id', None)
        region_id = self.request.query_params.get('region_id', None)
        subregion_id = self.request.query_params.get('subregion_id', None)
        
        # Filter by country if provided
        if country_id:
            queryset = queryset.filter(address__country_id=country_id)
            
        # Filter by region if provided (only if country is also provided)
        if region_id and country_id:
            queryset = queryset.filter(address__region_id=region_id)
            
        # Filter by subregion if provided (only if region is also provided)
        if subregion_id and region_id:
            queryset = queryset.filter(address__subregion_id=subregion_id)
        
        # Geographic name search
        geo_search = self.request.query_params.get('geo_search', None)
        if geo_search:
            queryset = queryset.filter(
                Q(address__country__name__icontains=geo_search) |
                Q(address__region__name__icontains=geo_search) |
                Q(address__subregion__name__icontains=geo_search)
            )
            
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
        profile = self.get_object()
        action_type = request.data.get('action')
        print(profile)
        print(profile.kyc_submission_date)
        if not profile.kyc_submission_date:
            return Response({"error": "No KYC submission"}, status=400)

        if action_type == 'approve':
            try:
                with transaction.atomic():
                    if not profile.reference:
                        profile.reference = ReferenceGenerator.generate_reference(profile)
                    
                    profile.is_kyc_verified = True
                    profile.kyc_status = 'approved'
                    profile.kyc_verification_date = timezone.now()
                    profile.kyc_rejection_reason = None
                    profile.save()

                    pdf = generate_certificate_pdf(profile,request)
                    send_certificate_email(profile, pdf)
                    
                    # Send notification for KYC approval
                    send_notification_safely(send_kyc_approved_notification, profile, request)

                    return Response({
                        "message": "KYC approved",
                        "reference": profile.reference,
                        "profile": self.get_serializer(profile).data
                    })
            except Exception as e:
                print(f"Error during KYC approval: {str(e)}")
                return Response({"error": str(e)}, status=400)

            
        elif action_type == 'reject':
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
            
            # Send notification for KYC rejection
            send_notification_safely(send_kyc_rejected_notification, profile, reason)
            
            return Response({
                "message": "KYC verification rejected.",
                "profile": CombinedUserProfileSerializer(profile).data
            })
            
        elif action_type == 'flag':
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
            
            # Send notification for KYC flagging
            send_notification_safely(send_kyc_flagged_notification, profile, reason)
            
            return Response({
                "message": "User flagged for review.",
                "profile": CombinedUserProfileSerializer(profile).data
            })
            
        elif action_type == 'mark_scammer':
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
            
            # No notification for scammers
            
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
        profile_ids = request.data.get('profile_ids', [])
        action_type = request.data.get('action')

        if action_type != 'approve':
            # Handle other actions
            return super().bulk_verify(request)

        profiles = UserProfile.objects.filter(
            id__in=profile_ids,
            kyc_submission_date__isnull=False
        )

        updated = []
        errors = []

        for profile in profiles:
            try:
                with transaction.atomic():
                    if not profile.reference:
                        profile.reference = ReferenceGenerator.generate_reference(profile)
                    
                    profile.is_kyc_verified = True
                    profile.kyc_status = 'approved'
                    profile.kyc_verification_date = timezone.now()
                    profile.kyc_rejection_reason = None
                    profile.save()

                    pdf = generate_certificate_pdf(profile,request)
                    send_certificate_email(profile, pdf)
                    
                    # Send notification for KYC approval
                    send_notification_safely(send_kyc_approved_notification, profile, request)
                    
                    updated.append(profile.id)
            except Exception as e:
                errors.append({
                    'profile_id': profile.id,
                    'error': str(e)
                })

        return Response({
            'updated_count': len(updated),
            'errors': errors,
            'message': f'Processed {len(updated)} profiles with {len(errors)} errors'
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
            
            # Also send in-app notification
            send_notification_safely(send_kyc_reminder_notification, profile)
            
            return Response({
                "success": True,
                "message": f"KYC reminder email sent to {user.email}."
            })
            
        except Exception as e:
            return Response(
                {"error": f"Failed to send reminder: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def request_edit_code(self, request, pk=None):
        """
        Request a verification code to edit a user's profile
        """
        try:
            profile = self.get_object()
            user = profile.user
            admin_user = request.user
            
            if not user or not user.email:
                return Response(
                    {"error": "User does not have a valid email address."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get or create verification code
            verification_code, created = VerificationCode.objects.get_or_create(user=user)
            
            # If not created, regenerate the code
            if not created:
                verification_code.save()  # This will trigger the save method to generate a new code
            
            # Get admin profile for email
            admin_profile = UserProfile.objects.filter(user=admin_user).first()
            admin_name = f"{admin_user.first_name} {admin_user.last_name}".strip() or admin_user.username
            admin_email = admin_user.email
            admin_image = request.build_absolute_uri(admin_profile.profile_image.url) if admin_profile and admin_profile.profile_image else None
            
            # Prepare email content
            subject = "Profile Edit Authorization Code - Destiny Builders Africa"
            message = f"Hello {user.first_name or user.username},\n\nAn administrator has requested to edit your profile. Please share the verification code only if you are with the administrator."
            to_email = [user.email]
            
            # Context for the email template
            context = {
                'user_name': user.first_name or user.username,
                'verification_code': verification_code.code,
                'admin_name': admin_name,
                'admin_email': admin_email,
                'admin_image': admin_image,
                'current_year': timezone.now().year
            }
            
            # Send the email
            html_file = 'emails/edit_profile_code.html'
            html_content = render_to_string(html_file, context)
            text_content = strip_tags(html_content)
            
            msg = EmailMultiAlternatives(subject, text_content, settings.EMAIL_HOST_USER, to_email)
            msg.attach_alternative(html_content, "text/html")
            EmailThread(msg).start()
            
            # Also send in-app notification
            send_notification_safely(
                send_edit_code_notification,
                user=user,
                code=verification_code.code,
                admin_user=admin_user,
                admin_profile=admin_profile
            )
            
            return Response({
                "success": True,
                "message": f"Verification code sent to {user.email}.",
                "user_id": user.id
            })
            
        except Exception as e:
            print(f"Error sending verification code email: {str(e)}")
            return Response(
                {"error": f"Failed to send verification code: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def verify_edit_code(self, request, pk=None):
        """
        Verify the code to edit a user's profile
        """
        try:
            profile = self.get_object()
            user = profile.user
            code = request.data.get('code')
            
            if not code:
                return Response(
                    {"error": "Verification code is required."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                verification_code = VerificationCode.objects.get(user=user)
            except VerificationCode.DoesNotExist:
                return Response(
                    {"error": "No verification code found for this user."},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Update total attempts
            verification_code.total_attempts += 1
            
            # Check if code matches
            if verification_code.code != code:
                return Response(
                    {"error": "Invalid verification code."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if code is expired (15 minutes)
            time_diff = timezone.now() - verification_code.time_requested
            if time_diff.total_seconds() > 900:  # 15 minutes in seconds
                return Response(
                    {"error": "Verification code has expired. Please request a new code."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Update successful attempts
            verification_code.successful_attempts += 1
            verification_code.save()
            
            # Return success with user profile data
            return Response({
                "success": True,
                "message": "Verification successful. You can now edit the user's profile.",
                "profile": CombinedUserProfileSerializer(profile).data
            })
            
        except Exception as e:
            return Response(
                {"error": f"Failed to verify code: {str(e)}"},
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
