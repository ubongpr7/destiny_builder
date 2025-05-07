from django.contrib.auth import authenticate
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.parsers import FileUploadParser
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from rest_framework.generics import ListAPIView 
from django.db.models import Prefetch
from rest_framework_simplejwt.views import TokenObtainPairView
from mainapps.accounts.models import User, UserProfile,VerificationCode
from mainapps.email_system.emails import send_html_email

from mainapps.common.settings import get_company_or_profile
from .serializers import *
from rest_framework.permissions import IsAuthenticated
from mainapps.permit.permit import HasModelRequestPermission

from django.contrib.auth import get_user_model
from rest_framework import generics
from .serializers import UserActivationSerializer
from rest_framework.throttling import AnonRateThrottle
User = get_user_model()


class UserActivationAPIView(generics.RetrieveAPIView):
    """
    Check if user account is active by user ID
    """
    serializer_class = UserActivationSerializer
    lookup_url_kwarg = 'user_id'
    lookup_field = 'id'
    
    def get_queryset(self):
        return User.objects.filter(id=self.kwargs.get('user_id'))

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return Response(serializer.data)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
 
class UploadProfileView(APIView):
    parser_classes=[FileUploadParser]
    def post(self, request ):
        user=request.user
        picture=request.data["file"]
        user.picture=picture
        user.save()
        #serializer=UserPictureSerializer(picture,data=request.data)
        if user.picture==picture:
            return Response("Profile picture updated Successfully",status=200)
        else:
            return Response("Error uploading picture!",status=400)

@api_view(['GET'])
def ge_route(request):
    route=['/api/token','api/token/refresh']
    return Response(route,status=201)


class VerificationAPI(APIView):
    throttle_classes = [AnonRateThrottle]
    
    def get(self, request):
        """Send verification code via email (GET)"""
        email = request.query_params.get('email')
        password= request.query_params.get('password')


        if not email:
            return Response(
                {"error": "Email parameter is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            
            user = User.objects.get(email=email)
            
            code = VerificationCode.objects.get(
                user=user
            )
            code.save()
            
            send_html_email(
                subject=f'Your Verification Code: {code.code}',
                message=f'Use this code to verify your login: {code.code}',
                to_email=[user.email],
                html_file='accounts/verify.html'
            )
            
            return Response(
                {"message": "Verification code sent successfully"},
                status=status.HTTP_200_OK
            )
            
        except User.DoesNotExist:
            return Response(
                {"error": "User not found with this email"},
                status=status.HTTP_404_NOT_FOUND
            )

    def post(self, request):
        """Verify code submission (POST)"""
        email = request.data.get('email')
        code_input = request.data.get('code')
        
        if not email or not code_input:
            return Response(
                {"error": "Both email and code are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email=email)
            verification_code = VerificationCode.objects.get(slug=user.email)
            

            if str(verification_code.code) != code_input.strip():
                return Response(
                    {"error": "Invalid verification code"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            return Response(
                {
                    "message": "Verification successful",
                    "user_id": user.id,
                    "email": user.email
                },
                status=status.HTTP_200_OK
            )
            
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except VerificationCode.DoesNotExist:
            return Response(
                {"error": "No active verification code for this user"},
                status=status.HTTP_400_BAD_REQUEST
            )


class UserDetailView(APIView):
    permission_classes = [IsAuthenticated]
    

    def get(self, request, *args, **kwargs):
        """Return details of the logged-in user"""
        user = request.user
        if not user.profile:
            profile=UserProfile.objects.create()
            user.profile = profile
            user.save()

        serializer = MyUserSerializer(user)
        return Response(serializer.data)
    

class TokenGenerator(TokenObtainPairView):
    def post(self, request: Request, *args, **kwargs)  :
        username=request.data.get('username')
        password=request.data.get('password')
        user=authenticate(username=username,password=password)
        if user is not None:
            response=super().post(request,*args,**kwargs)
            response.status_code=200
            return response
        else:
            return Response(status=400)

class UserProfileView(APIView):
    
    permission_classes=[permissions.IsAuthenticated]
    def get(self,request):
        serializer=MyUserSerializer
        email=request.COOKIES.get('email')
        user=User.objects.get(username=email)
        return Response({'user':user},status=200)
from rest_framework_simplejwt.exceptions import TokenError

class LogoutAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        
        if not refresh_token:
            return Response({"error": "Refresh token is required"}, status=400)

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"message": "Logged out successfully"}, status=200)
        except TokenError as e:
            return Response({"message": "Logged out successfully"}, status=200)
        except Exception as e:
            return Response({"error": str(e)}, status=400)
class RootUserRegistrationAPIView(APIView):
    """
    Create new user with first name, email and password
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = RootUserCreateSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            code=VerificationCode.objects.get(slug=user.email)
            subject=f'Verification code: {code}. {user.first_name} {user.last_name}'
            message= code
            html_file='accounts/verify.html'
            to_email=user.email
            send_html_email(subject, message, [to_email],html_file)
            return Response({
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class StaffUserRegistrationAPIView(APIView):
    """
    Create new user with first name, email and password
    """
    # authentication_classes = []
    permission_classes = [IsAuthenticated,HasModelRequestPermission]

    def post(self, request):

        serializer = StaffUserCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.save()
            company=get_company_or_profile(request.user)
            user.profile=company
            user.save()
            password = serializer.validated_data.get('password')  # Get from validated data
                
            code=VerificationCode.objects.get(slug=user.email)
            subject=f'Verification code: {code}. {user.first_name}'
            message= f'Code: {code}, Password: {password}'
            
            html_file='accounts/verify.html'
            to_email=user.email
            send_html_email(subject, message, [to_email],html_file)
            return Response({
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UpdateUserView(generics.UpdateAPIView):
    queryset = User.objects.all()
    serializer_class = MyUserSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'  

    # def get_object(self):
    #     """Override to get the user object based on the request user"""
    #     return self.request.user

