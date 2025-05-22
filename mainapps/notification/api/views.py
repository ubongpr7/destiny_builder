from rest_framework import viewsets, status, filters, pagination
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count
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

class NotificationPagination(pagination.PageNumberPagination):
    """Custom pagination for notifications"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class NotificationViewSet(viewsets.ModelViewSet):
    """ViewSet for managing notifications"""
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_read', 'priority', 'notification_type']
    search_fields = ['title', 'body']
    ordering_fields = ['created_at', 'updated_at', 'priority']
    ordering = ['-created_at']
    pagination_class = NotificationPagination
    
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
        
        # Filter by date range if provided
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def unread(self, request):
        """Get all unread notifications for the current user"""
        queryset = self.filter_queryset(self.get_queryset().filter(is_read=False))
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recent notifications for the current user (for notification bell)"""
        limit = int(request.query_params.get('limit', 12))
        queryset = self.get_queryset().order_by('-created_at')[:limit]
        serializer = self.get_serializer(queryset, many=True)
        
        # Get unread count
        unread_count = self.get_queryset().filter(is_read=False).count()
        
        return Response({
            'notifications': serializer.data,
            'unread_count': unread_count
        })
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get notification statistics for the current user"""
        queryset = self.get_queryset()
        
        # Get counts by category
        category_counts = queryset.values('notification_type__category').annotate(
            count=Count('id'),
            unread=Count('id', filter=Q(is_read=False))
        ).order_by('notification_type__category')
        
        # Get counts by priority
        priority_counts = queryset.values('priority').annotate(
            count=Count('id'),
            unread=Count('id', filter=Q(is_read=False))
        ).order_by('priority')
        
        # Get total and unread counts
        total_count = queryset.count()
        unread_count = queryset.filter(is_read=False).count()
        
        return Response({
            'total': total_count,
            'unread': unread_count,
            'by_category': category_counts,
            'by_priority': priority_counts
        })
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Mark all notifications as read for the current user"""
        # Allow filtering by category
        category = request.data.get('category')
        queryset = self.get_queryset().filter(is_read=False)
        
        if category:
            queryset = queryset.filter(notification_type__category=category)
            
        count = queryset.update(
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
                except Exception as e:
                    return Response({
                        'status': 'error',
                        'message': f'Error retrieving related object: {str(e)}'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create notifications
            try:
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
            except Exception as e:
                return Response({
                    'status': 'error',
                    'message': f'Error creating notifications: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def schedule_notification(self, request):
        """Schedule a notification to be sent at a future time"""
        serializer = ScheduleNotificationSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            
            try:
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
            except Exception as e:
                return Response({
                    'status': 'error',
                    'message': f'Error scheduling notification: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['delete'])
    def delete_multiple(self, request):
        """Delete multiple notifications"""
        notification_ids = request.data.get('ids', [])
        if not notification_ids:
            return Response({
                'status': 'error',
                'message': 'No notification IDs provided'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        deleted, _ = Notification.objects.filter(
            id__in=notification_ids,
            recipient=request.user
        ).delete()
        
        return Response({
            'status': 'success',
            'count': deleted
        })

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
    
    @action(detail=False, methods=['get'])
    def categories(self, request):
        """Get all notification categories"""
        from ..models import NotificationCategory
        categories = [
            {'value': choice[0], 'label': choice[1]}
            for choice in NotificationCategory.choices
        ]
        return Response(categories)

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
        errors = []
        
        for pref in preferences:
            notification_type_id = pref.get('notification_type')
            if not notification_type_id:
                errors.append({'message': 'Missing notification_type', 'data': pref})
                continue
                
            try:
                notification_type = NotificationType.objects.get(id=notification_type_id)
                if not notification_type.can_disable and not request.user.is_staff:
                    errors.append({
                        'message': f'Cannot modify preference for {notification_type.name}',
                        'data': pref
                    })
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
                errors.append({
                    'message': f'Notification type with ID {notification_type_id} does not exist',
                    'data': pref
                })
            except Exception as e:
                errors.append({
                    'message': str(e),
                    'data': pref
                })
        
        response_data = {
            'status': 'success' if not errors else 'partial_success',
            'count': len(updated),
            'preferences': NotificationPreferenceSerializer(updated, many=True).data
        }
        
        if errors:
            response_data['errors'] = errors
            
        return Response(response_data)
    
    @action(detail=False, methods=['get'])
    def get_all(self, request):
        """Get all notification types with user preferences"""
        # Get all notification types
        notification_types = NotificationType.objects.filter(is_active=True)
        
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
                'icon': nt.icon,
                'color': nt.color,
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
    
    @action(detail=False, methods=['get'])
    def reset_to_default(self, request):
        """Reset all preferences to default values"""
        user = request.user
        
        # Get all notification types
        notification_types = NotificationType.objects.filter(is_active=True)
        
        # Delete existing preferences
        NotificationPreference.objects.filter(user=user).delete()
        
        # Create default preferences
        preferences = []
        for nt in notification_types:
            preference = NotificationPreference.objects.create(
                user=user,
                notification_type=nt,
                receive_in_app=True,
                receive_email=nt.send_email,
                receive_sms=nt.send_sms,
                receive_push=nt.send_push
            )
            preferences.append(preference)
        
        return Response({
            'status': 'success',
            'message': 'All preferences reset to default values',
            'count': len(preferences)
        })
