from rest_framework import viewsets
from .signals import activity_log_signal

class ActivityTrackingMixin:
    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        activity_log_signal.send(sender=self.__class__, request=request, user=request.user, action='CREATE', instance=response.data)
        return response

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        activity_log_signal.send(sender=self.__class__, request=request, user=request.user, action='UPDATE', instance=response.data)
        return response

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        response = super().destroy(request, *args, **kwargs)
        activity_log_signal.send(sender=self.__class__, request=request, user=request.user, action='DELETE', instance=instance)
        return response
