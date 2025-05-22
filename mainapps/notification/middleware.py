from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Q
from .models import Notification

User = get_user_model()

class NotificationTrackingMiddleware:
    """Middleware to track notification-related user activity"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        response = self.get_response(request)
        
        # Only process for authenticated users
        if request.user.is_authenticated:
            # Check if user is on the profile update page
            if request.path.endswith('/profile/update/') or request.path.endswith('/profile/update'):
                self._track_profile_page_visit(request.user)
                
        return response
    
    def _track_profile_page_visit(self, user):
        """Track when a user visits the profile update page"""
        # This could be used to avoid sending reminders to users who are actively updating their profile
        # You could store this in a cache or a model
        pass
