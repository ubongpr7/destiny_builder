from django.apps import AppConfig

class NotificationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mainapps.notification'
    
    def ready(self):
        import mainapps.notification.signals
