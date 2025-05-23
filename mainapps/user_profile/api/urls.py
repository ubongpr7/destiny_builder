from django.urls import path,include
from rest_framework import routers
from .views import *
router=routers.DefaultRouter()
router.register(r'industries', IndustryViewSet)
router.register(r'expertise', ExpertiseViewSet)
router.register(r'partnership-types', PartnershipTypeViewSet)
router.register(r'preview-profiles', UserProfilePreviewViewSet, basename='preview-profiles')
router.register(r'partnership-levels', PartnershipLevelViewSet)
router.register(r'skills', SkillViewSet)
router.register(r'profile', ProfileViewSet)
router.register(r'membership', MembershipViewSet)
router.register(r'disabilities', DisabilityViewSet)
router.register(r'users', UserViewSet)
router.register(r'user-profiles', UserProfileViewSet,basename='user-profiles')



urlpatterns = [
    path('', include(router.urls)),
    path('profile-roles/', UserProfileRoleView.as_view(), name='profile-role'),
    path('profiles/<str:user_profile_id>/addresses/', 
         AddressViewSet.as_view({'get': 'list', 'post': 'create'}),
         name='profile-addresses-list'),
    path('profiles/<str:user_profile_id>/addresses/<str:pk>/', 
         AddressViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}),
         name='profile-addresses-detail'),


         
]




