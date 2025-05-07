from rest_framework import serializers,exceptions
from rest_framework.validators import UniqueValidator
from mainapps.accounts.models import User
from django.contrib.auth import authenticate
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from mainapps.permit.models import CustomUserPermission
from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer
from django.contrib.auth import get_user_model

from django.contrib.auth.password_validation import validate_password
import logging

logger = logging.getLogger(__name__)






class RootUserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True,)
    re_password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ('first_name', 'email', 'password', 're_password')
        extra_kwargs = {
            'first_name': {'required': True},
            'email': {'required': True}
        }


    def create(self, validated_data):
        re_password = validated_data.pop("re_password", None)
        
        user = User.objects.create_user(**validated_data)
        user.is_main=True
        user.save()

    

        return user

class StaffUserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField( required=True,)

    class Meta:
        model = User
        fields = ('first_name', 'email', 'password','phone',)
        extra_kwargs = {
            'first_name': {'required': True},
            'email': {'required': True}
        }


    def create(self, validated_data):
        
        user = User.objects.create_user(**validated_data)
        user.is_main=False
        user.is_worker=True
        user.save()

    

        return user
class UserActivationSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'is_active']
        read_only_fields = ['id', 'email', 'is_active']

class LogoutSerializer(serializers.Serializer):
    refresh=serializers.CharField()



User = get_user_model()

class UserCreateSerializer(BaseUserCreateSerializer):
    class Meta(BaseUserCreateSerializer.Meta):
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'password')
        
    def create(self, validated_data):
        # Log the validated data
        logger.info(f"Creating user with data: {validated_data}")
        
        # Explicitly extract first_name and last_name
        first_name = validated_data.get('first_name', '')
        last_name = validated_data.get('last_name', '')
        
        # Create the user with explicit parameters
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=first_name,
            last_name=last_name
        )
        
        # Log the created user
        logger.info(f"Created user: {user.email} with first_name={user.first_name}, last_name={user.last_name}")
        
        return user

class MyUserSerializer(serializers.ModelSerializer):
    
    class Meta:
        # depth=1
        model = User
        exclude = ['last_login', 'is_superuser','is_verified', 
                 'is_staff', 'groups', 'user_permissions','date_joined', 'is_active']
        extra_kwargs = {
            'password': {'write_only': True},
            'email': {'required': True}
        }
    
    
class UserPictureSerializer(serializers.ModelSerializer):
    class Meta:
        model=User
        fields=("picture",)
    
class VerificationSerializer(serializers.Serializer):
    code=serializers.IntegerField()
    
class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    
    
    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user  
        
        data.update({
            'id': user.id,
            'username': user.username,
            'is_verified': user.is_verified,
            'profile': user.profile.id if user.profile else None,
            'email': user.email,
            'first_name': user.first_name,
            'profile':user.profile.id if user.profile else None,
        })
        
        return data 
    
           


class UserPermissionSerializer(serializers.ModelSerializer):
    permissions = serializers.SlugRelatedField(
        many=True,
        slug_field='codename',
        queryset=CustomUserPermission.objects.all(),
        source='custom_permissions'
    )

    class Meta:
        model = User
        fields = ('permissions',)
        extra_kwargs = {
            'permissions': {
                'help_text': 'List of permission codenames to assign to the user'
            }
        }

