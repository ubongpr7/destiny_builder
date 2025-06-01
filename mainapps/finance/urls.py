from django.urls import path
from .views import FlutterwaveWebhookView,flutterwave_webhook_debug
urlpatterns = [
    path('test_webhook/', flutterwave_webhook_debug, name='flutterwave_webhook'),
    # path('test_webhook/', FlutterwaveWebhookView.as_view(), name='flutterwave_webhook'),
]