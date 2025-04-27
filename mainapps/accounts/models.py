import os
import random
from PIL import Image
from django.db import models
from django.urls import reverse
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.conf import settings
from django.db.models import Q
from django.conf import settings
from django.contrib.auth.models import PermissionsMixin
from django.utils.translation import gettext_lazy as _
from mainapps.common.models import Address
from mainapps.inventory.helpers.field_validators import *
from django.utils import timezone

from mainapps.permit.models import CustomUserPermission



PREFER_NOT_TO_SAY="not_to_mention"
SEX=(
    ("male",_("Male")),
    ("female",_("Female")),
)


def get_upload_path(instance,filename):
    return os.path.join('images','avartar',str(instance.pk,filename))




class CustomUserManager(BaseUserManager):
    
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user


    def create_superuser(self, email, password=None, **extra_fields):
            extra_fields.setdefault("is_staff", True)
            extra_fields.setdefault("is_superuser", True)

            if not extra_fields.get("is_staff"):
                raise ValueError("Superuser must have is_staff=True.")
            if not extra_fields.get("is_superuser"):
                raise ValueError("Superuser must have is_superuser=True.")

            user = self.create_user(email, password, **extra_fields)
            return user

class User(AbstractUser, PermissionsMixin,models.Model):
    phone = models.CharField(
        max_length=60, 
        blank=True, 
        null=True
    )
    
    picture = models.ImageField(
        upload_to='profile_pictures/%y/%m/%d/', 
        default='default.png', 
        null=True
    
        )
    email = models.EmailField(blank=False, null=True,unique=True)
    sex=models.CharField(
        max_length=20,
        choices=SEX,
        default=PREFER_NOT_TO_SAY,
        blank=True,
        null=True
    )
    is_verified=models.BooleanField(default=False)
    is_staff=models.BooleanField(default=False)
    is_worker=models.BooleanField(default=False, editable=False)
    is_main = models.BooleanField(editable=False,default=False)
    date_of_birth = models.DateField(
        validators=[adult_validator], 
        verbose_name='Date Of Birth',
        help_text='You must be above 18 years of age.',
        blank=True,
        null=True,
    )
    profile=models.ForeignKey(
        'management.CompanyProfile',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='staff',
        editable=False
        
    )

    custom_permissions = models.ManyToManyField(
        CustomUserPermission,
        related_name='users',
        blank=True
    )
    
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = CustomUserManager()
  
    def save(self, *args, **kwargs):
        self.username = self.email
        super().save(*args, **kwargs)


        try:
            img = Image.open(self.picture.path)
            if img.height > 300 or img.width > 300:
                output_size = (300, 300)
                img.thumbnail(output_size)
                img.save(self.picture.path)
        except:
            pass
        

    @property
    def get_full_name(self):
        full_name = self.email
        if self.first_name and self.last_name:
            full_name = self.first_name + " " + self.last_name
        return full_name

    def __str__(self):
        return self.email

        

    def get_picture(self):
        try:
            return self.picture.url
        except:
            no_picture = settings.MEDIA_URL + 'default.png'
            return no_picture


    def delete(self, *args, **kwargs):
        if self.picture.url != settings.MEDIA_URL + 'default.png':
            self.picture.delete()
        super().delete(*args, **kwargs)
    
    
class VerificationCode(models.Model):
    user=models.OneToOneField(User,on_delete=models.CASCADE)
    code=models.CharField(max_length=6,blank=True)
    slug=models.SlugField(editable=False,blank=True)
    time_requested=models.DateTimeField(auto_now=True)
    successful_attempts=models.IntegerField(default=0)
    total_attempts=models.IntegerField(default=0)

    def __str__(self):
        return self.code
    def save(self, *args,**kwargs):
        nums=[i for i in range(1,9)]
        code_list=[]
        for i in range(6):
            n=random.choice(nums)
            code_list.append(n)
        code_string="".join(str(i)  for i in code_list)
        self.code=code_string
        self.slug=self.user.email
        super().save( *args,**kwargs)
    
    class Meta:
        # extra permissions
        permissions= (
            ('code','message'),
            ('can_copy_code','Can copy code'),
            ('can_share_code','Can share code'),

        )




class UserProfile(models.Model):
    """Extended user profile with additional information"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    address = models.ForeignKey('common.Address', on_delete=models.SET_NULL, null=True, blank=True, related_name='user_profile')
    bio = models.TextField(blank=True, null=True)
    profile_image = models.ImageField(upload_to='profile_images/', blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    
    # KYC Verification Fields
    is_kyc_verified = models.BooleanField(default=False)
    id_document_type = models.CharField(max_length=50, blank=True, null=True)
    id_document_number = models.CharField(max_length=50, blank=True, null=True)
    id_document_image_front = models.ImageField(upload_to='kyc_documents/', blank=True, null=True)
    id_document_image_back = models.ImageField(upload_to='kyc_documents/', blank=True, null=True)
    selfie_image = models.ImageField(upload_to='kyc_documents/', blank=True, null=True)
    kyc_submission_date = models.DateTimeField(blank=True, null=True)
    kyc_verification_date = models.DateTimeField(blank=True, null=True)
    kyc_rejection_reason = models.TextField(blank=True, null=True)
    
    # Additional fields
    is_project_manager = models.BooleanField(default=False)
    is_donor = models.BooleanField(default=False)
    is_volunteer = models.BooleanField(default=False)
    is_partner = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username}'s Profile"



class Skill(models.Model):
    """Skills that users can have"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return self.name

class UserSkill(models.Model):
    """Many-to-many relationship between users and skills"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_skills')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='user_skills')
    proficiency_level = models.CharField(max_length=50, blank=True, null=True)
    
    class Meta:
        unique_together = ('user', 'skill')
    
    def __str__(self):
        return f"{self.user.username} - {self.skill.name}"
    

