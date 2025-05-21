from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType

from ..models import (
    Notification, NotificationType, NotificationPreference,
    NotificationBatch, ScheduledNotification
)
from .serializers import (
    NotificationSerializer, NotificationTypeSerializer, 
    NotificationPreferenceSerializer, NotificationBatchSerializer,
    ScheduledNotificationSerializer, CreateNotificationSerializer,
    ScheduleNotificationSerializer
)
from ..services import NotificationService

class NotificationViewSet(viewsets.ModelViewSet):
    """ViewSet for managing notifications"""
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_read', 'priority', 'notification_type']
    search_fields = ['title', 'body']
    ordering_fields = ['created_at', 'updated_at', 'priority']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter notifications for the current user"""
        user = self.request.user
        queryset = Notification.objects.filter(recipient=user)
        
        # Filter by category if provided
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(notification_type__category=category)
            
        # Filter by related object if provided
        related_type = self.request.query_params.get('related_type')
        related_id = self.request.query_params.get('related_id')
        
        if related_type and related_id:
            try:
                app_label, model = related_type.split('.')
                content_type = ContentType.objects.get(app_label=app_label, model=model)
                queryset = queryset.filter(content_type=content_type, object_id=related_id)
            except (ValueError, ContentType.DoesNotExist):
                pass
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def unread(self, request):
        """Get all unread notifications for the current user"""
        queryset = self.filter_queryset(self.get_queryset().filter(is_read=False))
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Mark all notifications as read for the current user"""
        count = self.get_queryset().filter(is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )
        return Response({'status': 'success', 'count': count})
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark a notification as read"""
        notification = self.get_object()
        notification.mark_as_read()
        return Response({'status': 'success'})
    
    @action(detail=True, methods=['post'])
    def mark_unread(self, request, pk=None):
        """Mark a notification as unread"""
        notification = self.get_object()
        notification.mark_as_unread()
        return Response({'status': 'success'})
    
    @action(detail=False, methods=['post'])
    def create_notification(self, request):
        """Create a notification for one or more users"""
        serializer = CreateNotificationSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            
            # Get related object if provided
            related_object = None
            if data.get('related_object_type') and data.get('related_object_id'):
                try:
                    app_label, model = data['related_object_type'].split('.')
                    content_type = ContentType.objects.get(app_label=app_label, model=model)
                    model_class = content_type.model_class()
                    related_object = model_class.objects.get(id=data['related_object_id'])
                except Exception:
                    pass
            
            # Create notifications
            notifications = NotificationService.create_notification_for_many(
                recipients=data['recipients'],
                notification_type_name=data['notification_type'],
                context_data=data.get('context_data'),
                related_object=related_object,
                action_url=data.get('action_url'),
                priority=data.get('priority'),
                icon=data.get('icon'),
                color=data.get('color'),
                send_email=data.get('send_email'),
                send_sms=data.get('send_sms'),
                send_push=data.get('send_push')
            )
            
            return Response({
                'status': 'success',
                'count': len(notifications),
                'notifications': NotificationSerializer(notifications, many=True).data
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def schedule_notification(self, request):
        """Schedule a notification to be sent at a future time"""
        serializer = ScheduleNotificationSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            
            scheduled = NotificationService.schedule_notification(
                recipient=data['recipient'],
                notification_type_name=data['notification_type'],
                scheduled_time=data['scheduled_time'],
                context_data=data.get('context_data'),
                is_recurring=data.get('is_recurring', False),
                recurrence_pattern=data.get('recurrence_pattern', '')
            )
            
            if scheduled:
                return Response({
                    'status': 'success',
                    'scheduled': ScheduledNotificationSerializer(scheduled).data
                })
            else:
                return Response({
                    'status': 'error',
                    'message': 'Failed to schedule notification'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class NotificationTypeViewSet(viewsets.ModelViewSet):
    """ViewSet for managing notification types"""
    queryset = NotificationType.objects.all()
    serializer_class = NotificationTypeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'is_active', 'can_disable']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'category', 'created_at']
    ordering = ['category', 'name']

class NotificationPreferenceViewSet(viewsets.ModelViewSet):
    """ViewSet for managing notification preferences"""
    serializer_class = NotificationPreferenceSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter preferences for the current user"""
        return NotificationPreference.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['post'])
    def update_preferences(self, request):
        """Update multiple preferences at once"""
        preferences = request.data.get('preferences', [])
        if not preferences or not isinstance(preferences, list):
            return Response({
                'status': 'error',
                'message': 'Invalid preferences data'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        updated = []
        for pref in preferences:
            notification_type_id = pref.get('notification_type')
            if not notification_type_id:
                continue
                
            try:
                notification_type = NotificationType.objects.get(id=notification_type_id)
                if not notification_type.can_disable:
                    continue
                    
                preference, created = NotificationPreference.objects.get_or_create(
                    user=request.user,
                    notification_type=notification_type,
                    defaults={
                        'receive_in_app': True,
                        'receive_email': notification_type.send_email,
                        'receive_sms': notification_type.send_sms,
                        'receive_push': notification_type.send_push
                    }
                )
                
                # Update preference fields
                for field in ['receive_in_app', 'receive_email', 'receive_sms', 'receive_push']:
                    if field in pref:
                        setattr(preference, field, pref[field])
                
                preference.save()
                updated.append(preference)
                
            except NotificationType.DoesNotExist:
                pass
        
        return Response({
            'status': 'success',
            'count': len(updated),
            'preferences': NotificationPreferenceSerializer(updated, many=True).data
        })
    
    @action(detail=False, methods=['get'])
    def get_all(self, request):
        """Get all notification types with user preferences"""
        # Get all notification types
        notification_types = NotificationType.objects.filter(is_active=True)
        
        # Get user's existing preferences
        user_preferences = {
            pref.notification_type_id: pref 
            for pref in NotificationPreference.objects.filter(user=request.user)
        }
        
        # Build response data
        result = []
        for nt in notification_types:
            pref = user_preferences.get(nt.id)
            
            # Use default values if no preference exists
            if not pref:
                pref_data = {
                    'receive_in_app': True,
                    'receive_email': nt.send_email,
                    'receive_sms': nt.send_sms,
                    'receive_push': nt.send_push
                }
            else:
                pref_data = {
                    'receive_in_app': pref.receive_in_app,
                    'receive_email': pref.receive_email,
                    'receive_sms': pref.receive_sms,
                    'receive_push': pref.receive_push
                }
            
            result.append({
                'id': nt.id,
                'name': nt.name,
                'description': nt.description,
                'category': nt.category,
                'can_disable': nt.can_disable,
                'preferences': pref_data
            })
        
        # Group by category
        categories = {}
        for item in result:
            category = item['category']
            if category not in categories:
                categories[category] = []
            categories[category].append(item)
        
        return Response(categories)
