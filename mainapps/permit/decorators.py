
from functools import wraps
from django.dispatch import Signal

activity_log_signal = Signal(providing_args=["request", "user", "action", "instance"])

def track_activity(action):
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            response = func(self, request, *args, **kwargs)
            activity_log_signal.send(sender=self.__class__, request=request, user=request.user, action=action, instance=response.data)
            return response
        return wrapper
    return decorator
