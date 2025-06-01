from django.urls import path
from .views import FlutterwaveWebhookView, flutterwave_webhook
urlpatterns = [
    path('test_webhook/', FlutterwaveWebhookView.as_view(), name='flutterwave_webhook'),
]