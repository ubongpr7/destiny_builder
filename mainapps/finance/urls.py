from django.urls import path
from .views import flutterwave_webhook
urlpatterns = [
    path('test_webhook/', flutterwave_webhook, name='flutterwave_webhook'),
]