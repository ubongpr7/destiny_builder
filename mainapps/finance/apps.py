from django.apps import AppConfig


class FinanceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "mainapps.finance"

    def ready(self):
        try:
            import mainapps.finance.signals  
        except ImportError:
            pass
