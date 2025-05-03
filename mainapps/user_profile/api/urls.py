from django.urls import path,include
from rest_framework import routers
from .views import *
router=routers.DefaultRouter()
router.register(r'industries', IndustryViewSet)
router.register(r'expertise', ExpertiseViewSet)
router.register(r'partnership-types', PartnershipTypeViewSet)
router.register(r'partnership-levels', PartnershipLevelViewSet)
router.register(r'skills', SkillViewSet)
router.register(r'profile', ProfileViewSet)
router.register(r'membership', MembershipViewSet)

urlpatterns=[
    path('',include(router.urls)),


]