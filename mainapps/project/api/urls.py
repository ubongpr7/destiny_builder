from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AllUserViewSet, CEOUserViewSet, MilestoneMediaViewSet, ProjectExpenseViewSet, ProjectMediaViewSet, ProjectViewSet, ProjectCategoryViewSet, 
    DailyProjectUpdateViewSet, ProjectUpdateMediaViewSet,
    ProjectTeamMemberViewSet,ProjectMilestoneViewSet, TeambleUserViewSet, UserRelatedProjectsViewSet, get_project_team_members, project_model_info
)

router = DefaultRouter()

# Register viewsets with the router
router.register(r'all-users', AllUserViewSet,basename='all-users')
router.register(r'teamable', TeambleUserViewSet, basename='teamable-users')
router.register(r'ceos', CEOUserViewSet,basename='ceo')
router.register(r'projects', ProjectViewSet)
router.register(r'project-categories', ProjectCategoryViewSet)

router.register(r'team-members', ProjectTeamMemberViewSet, basename='team-members')
router.register(r'milestones', ProjectMilestoneViewSet, basename='milestones')
router.register(r'expenses', ProjectExpenseViewSet, basename='expenses')
router.register(r'updates', DailyProjectUpdateViewSet, basename='update')
router.register(r'media', ProjectUpdateMediaViewSet, basename='media')
router.register(r'user-projects', UserRelatedProjectsViewSet, basename='user-projects')
router.register(r'project-media', ProjectMediaViewSet, basename='project-media')
router.register(r'milestone-media', MilestoneMediaViewSet, basename='milestone-media')


urlpatterns = [
    path('', include(router.urls)),
    path('projects/<int:project_id>/team/', 
         ProjectTeamMemberViewSet.as_view({'get': 'by_project'}), 
         name='project-team'),
         
    # Add custom milestone endpoints that aren't covered by the router
    path('projects/<int:project_id>/milestones/', 
         ProjectMilestoneViewSet.as_view({'get': 'by_project'}), 
         name='project-milestones'),

    path('projects/<int:project_id>/expenses/', 
         ProjectExpenseViewSet.as_view({'get': 'by_project'}), 
         name='project-expenses'),

    path('project-team-members/', get_project_team_members, name='project-team-members'),
    path('project-model-info/', project_model_info, name='project-model-info'),
]
