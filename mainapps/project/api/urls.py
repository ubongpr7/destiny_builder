from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProjectViewSet, ProjectCategoryViewSet, 
    DailyProjectUpdateViewSet, ProjectUpdateMediaViewSet,
    ProjectTeamMemberViewSet
)

router = DefaultRouter()

# Register viewsets with the router
router.register(r'projects', ProjectViewSet)
router.register(r'project-categories', ProjectCategoryViewSet)
router.register(r'updates', DailyProjectUpdateViewSet)
router.register(r'media', ProjectUpdateMediaViewSet)
router.register(r'team-members', ProjectTeamMemberViewSet, basename='team-members')

urlpatterns = [
    path('', include(router.urls)),
]