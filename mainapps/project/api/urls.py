from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProjectViewSet, ProjectCategoryViewSet, 
    DailyProjectUpdateViewSet, ProjectUpdateMediaViewSet,
    ProjectTeamMemberViewSet,ProjectMilestoneViewSet
)

router = DefaultRouter()

# Register viewsets with the router
router.register(r'projects', ProjectViewSet)
router.register(r'project-categories', ProjectCategoryViewSet)
router.register(r'updates', DailyProjectUpdateViewSet)
router.register(r'media', ProjectUpdateMediaViewSet)
router.register(r'team-members', ProjectTeamMemberViewSet, basename='team-members')
router.register(r'milestones', ProjectMilestoneViewSet, basename='milestones')

urlpatterns = [
    path('', include(router.urls)),
    path('projects/<int:project_id>/team/', 
         ProjectTeamMemberViewSet.as_view({'get': 'by_project'}), 
         name='project-team'),
         
    # Add custom milestone endpoints that aren't covered by the router
    path('projects/<int:project_id>/milestones/', 
         ProjectMilestoneViewSet.as_view({'get': 'by_project'}), 
         name='project-milestones'),
]