from celery import shared_task
from .models import ActivityLog

@shared_task
def log_activity(user_id, action, model_name, object_id, details):
    ActivityLog.objects.create(
        user_id=user_id,
        action=action,
        model_name=model_name,
        object_id=object_id,
        details=details
    )
