from celery import shared_task
from .models import ActivityLog
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
import logging
User= get_user_model()
logger = logging.getLogger(__name__)

@shared_task
def log_activity(user_id, action, model_name, object_id, details):
    ActivityLog.objects.create(
        user_id=user_id,
        action=action,
        model_name=model_name,
        object_id=object_id,
        details=details
    )



@shared_task
def async_log_activity(log_data: dict):
    """
    Celery task for asynchronous activity logging
    """
    try:
        user_id = log_data.pop('user_id', None)
        user = None
        
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                logger.warning(f"User with ID {user_id} not found for activity logging")

        ActivityLog.objects.create(
            user=user,
            **log_data
        )
        
    except KeyError as e:
        logger.error(f"Missing required field in activity log: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to create async activity log: {str(e)}", exc_info=True)