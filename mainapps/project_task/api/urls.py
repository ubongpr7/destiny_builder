from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TaskViewSet, ProjectViewSet, MilestoneViewSet

router = DefaultRouter()
router.register(r'tasks', TaskViewSet)
router.register(r'projects', ProjectViewSet)
router.register(r'milestones', MilestoneViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
