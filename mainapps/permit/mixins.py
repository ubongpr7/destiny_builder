# mixins.py
from django.db import transaction
from rest_framework import status
from rest_framework.response import Response

from mainapps.permit.models_activity.changes import get_field_changes
from .models import ActivityLog  

class ActivityTrackingMixin:
    """
    Mixin to log user activities for CRUD operations in ModelViewSets
    """
    
    def log_activity(self, user, action, instance, details):
        """
        Helper method to create activity log
        """
        model_name = instance.__class__.__name__
        object_id = instance.pk
        
        # Create log entry
        ActivityLog.objects.create(
            user=user,
            action=action,
            model_name=model_name,
            object_id=object_id,
            details=details
        )
    
    def get_request_metadata(self, request):
        """Extracts common request metadata"""
        return {
            'ip_address': request.META.get('REMOTE_ADDR'),
            'user_agent': request.META.get('HTTP_USER_AGENT')
        }
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Save instance within transaction
        instance = serializer.save()
        
        # Log creation activity
        metadata = self.get_request_metadata(request)
        metadata['initial_data'] = request.data
        metadata['created_data'] = serializer.data
        
        self.log_activity(
            user=request.user,
            action='CREATE',
            instance=instance,
            details=metadata
        )
        
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        old_data = self.get_serializer(instance).data
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        # Save updated instance
        updated_instance = serializer.save()
        
        # Log update activity
        new_data = serializer.data
        metadata = self.get_request_metadata(request)
        metadata['changes'] = get_field_changes(old_data, new_data)
        
        self.log_activity(
            user=request.user,
            action='UPDATE',
            instance=updated_instance,
            details=metadata
        )
        
        return Response(serializer.data)
    
    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Log deletion activity before actual deletion
        metadata = self.get_request_metadata(request)
        metadata['deleted_data'] = self.get_serializer(instance).data
        
        self.log_activity(
            user=request.user,
            action='DELETE',
            instance=instance,
            details=metadata
        )
        
        # Perform actual deletion
        return super().destroy(request, *args, **kwargs)