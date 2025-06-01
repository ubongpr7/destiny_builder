from django.urls import path
from .views import FlutterwaveWebhookView
urlpatterns = [
    path('test_webhook/', FlutterwaveWebhookView.as_view(), name='flutterwave_webhook'),
]