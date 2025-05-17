from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TaskViewSet, TaskCommentViewSet, TaskAttachmentViewSet, TaskTimeLogViewSet

router = DefaultRouter()
router.register(r'tasks', TaskViewSet)
router.register(r'task-comments', TaskCommentViewSet)
router.register(r'task-attachments', TaskAttachmentViewSet)
router.register(r'task-time-logs', TaskTimeLogViewSet)

urlpatterns = [
    path('', include(router.urls)),
]