from django.dispatch import receiver
from .models import ActivityLog
from .signals import activity_log_signal

@receiver(activity_log_signal)
def log_activity(sender, request, user, action, instance, **kwargs):
    ActivityLog.objects.create(
        user=user,
        action=action,
        model_name=sender.__name__,
        object_id=instance.get('id'),  
        details={'data': instance},
        changes={}
    )
