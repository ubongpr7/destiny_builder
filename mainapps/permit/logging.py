from django.dispatch import receiver
from .models import ActivityLog
from .signals import activity_log_signal

# @receiver(activity_log_signal)
# def log_activity(sender, request, user, action, instance, **kwargs):
#     ActivityLog.objects.create(
#         user=user,
#         action=action,
#         model_name=sender.__name__,
#         object_id=instance.get('id'),  
#         details={'data': instance},
#         changes={}
#     )
@receiver(activity_log_signal)
def log_activity(sender, request, user, action, instance, **kwargs):
    changes = {}
    if action == 'UPDATE':
        original_state = instance._original_state
        current_state = instance.__dict__
        for field in original_state:
            if field in current_state and original_state[field] != current_state[field]:
                changes[field] = {
                    'old': original_state[field],
                    'new': current_state[field]
                }

    ActivityLog.objects.create(
        user=user,
        action=action,
        model_name=sender.__name__,
        object_id=instance.id,
        details={'data': instance.__dict__},
        changes=changes
    )
