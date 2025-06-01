import json
import hashlib
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
 

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from django.shortcuts import get_object_or_404
from django.utils import timezone
import requests
import os
from .models import Donation, RecurringDonation, InKindDonation



from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
import json
import hashlib
import hmac
import os

@method_decorator(csrf_exempt, name='dispatch')
class FlutterwaveWebhookView(View):
    """Enhanced webhook handler that processes all payment updates"""
    
    def post(self, request):
        # Verify webhook signature
        if not self.verify_webhook_signature(request):
            return HttpResponse('Invalid signature', status=400)
        
        try:
            payload = json.loads(request.body)
            event_type = payload.get('event')
            data = payload.get('data', {})
            
            print(f"Webhook received: {event_type}")
            print(f"Data: {data}")
            
            if event_type == 'charge.completed':
                self.handle_payment_completed(data)
            elif event_type == 'charge.failed':
                self.handle_payment_failed(data)
            elif event_type == 'subscription.activated':
                self.handle_subscription_activated(data)
            elif event_type == 'subscription.cancelled':
                self.handle_subscription_cancelled(data)
            
            return HttpResponse('OK', status=200)
            
        except Exception as e:
            print(f"Webhook error: {str(e)}")
            return HttpResponse('Error processing webhook', status=500)
    
    def verify_webhook_signature(self, request):
        """Verify Flutterwave webhook signature"""
        secret_hash = os.getenv('FLUTTERWAVE_SECRET_HASH')
        
        if not secret_hash:
            print("No secret hash configured")
            return False
        
        signature = request.headers.get('verif-hash')
        
        if not signature:
            print("No signature in headers")
            return False
        
        expected_signature = hashlib.sha256(secret_hash.encode()).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    def handle_payment_completed(self, data):
        """Handle successful payment using metadata"""
        # Extract custom metadata from Flutterwave response
        meta = data.get('meta', {})
        donation_id = meta.get('donation_id')
        donation_type = meta.get('donation_type')
        
        print(f"Processing completed payment for {donation_type} donation ID: {donation_id}")
        
        if not donation_id or not donation_type:
            print("Missing donation metadata in webhook")
            return
        
        transaction_data = {
            'flutterwave_ref': data.get('flw_ref'),
            'transaction_id': data.get('id'),
            'tx_ref': data.get('tx_ref'),
            'amount': data.get('amount'),
            'currency': data.get('currency'),
            'payment_method': data.get('payment_type', 'card'),
            'processed_at': data.get('created_at'),
            'customer_email': data.get('customer', {}).get('email'),
            'customer_name': data.get('customer', {}).get('name'),
        }
        
        try:
            if donation_type == 'one-time':
                self.update_donation_status(donation_id, 'completed', transaction_data)
            elif donation_type == 'recurring':
                self.update_recurring_donation_status(donation_id, 'completed', transaction_data)
            elif donation_type == 'in-kind':
                self.update_in_kind_donation_status(donation_id, 'completed', transaction_data)
        except Exception as e:
            print(f"Error updating donation status: {str(e)}")
    
    def handle_payment_failed(self, data):
        """Handle failed payment using metadata"""
        meta = data.get('meta', {})
        donation_id = meta.get('donation_id')
        donation_type = meta.get('donation_type')
        
        print(f"Processing failed payment for {donation_type} donation ID: {donation_id}")
        
        if not donation_id or not donation_type:
            return
        
        transaction_data = {
            'flutterwave_ref': data.get('flw_ref'),
            'transaction_id': data.get('id'),
            'tx_ref': data.get('tx_ref'),
            'error_message': data.get('processor_response', 'Payment failed'),
            'failed_at': data.get('created_at'),
        }
        
        try:
            if donation_type == 'one-time':
                self.update_donation_status(donation_id, 'failed', transaction_data)
            elif donation_type == 'recurring':
                self.update_recurring_donation_status(donation_id, 'failed', transaction_data)
            elif donation_type == 'in-kind':
                self.update_in_kind_donation_status(donation_id, 'failed', transaction_data)
        except Exception as e:
            print(f"Error updating donation status: {str(e)}")
    
    def handle_subscription_activated(self, data):
        """Handle recurring donation subscription activation"""
        meta = data.get('meta', {})
        donation_id = meta.get('donation_id')
        
        if donation_id:
            try:
                recurring_donation = RecurringDonation.objects.get(id=donation_id)
                recurring_donation.status = 'active'
                recurring_donation.subscription_id = data.get('id')
                recurring_donation.save()
                print(f"Activated recurring donation {donation_id}")
            except RecurringDonation.DoesNotExist:
                print(f"Recurring donation {donation_id} not found")
    
    def handle_subscription_cancelled(self, data):
        """Handle recurring donation subscription cancellation"""
        meta = data.get('meta', {})
        donation_id = meta.get('donation_id')
        
        if donation_id:
            try:
                recurring_donation = RecurringDonation.objects.get(id=donation_id)
                recurring_donation.cancel_subscription("Cancelled via payment processor")
                print(f"Cancelled recurring donation {donation_id}")
            except RecurringDonation.DoesNotExist:
                print(f"Recurring donation {donation_id} not found")
    
    def update_donation_status(self, donation_id, status, transaction_data):
        """Update one-time donation status"""
        try:
            donation = Donation.objects.get(id=donation_id)
            donation.status = status
            
            # Update transaction fields
            donation.transaction_id = transaction_data.get('transaction_id')
            donation.reference_number = transaction_data.get('flutterwave_ref')
            donation.bank_reference = transaction_data.get('tx_ref')
            
            if status == 'completed':
                donation.processed_date = timezone.now()
            
            # Add transaction notes
            transaction_notes = f"Flutterwave: {transaction_data.get('transaction_id', 'N/A')}"
            donation.notes = f"{donation.notes or ''}\n{transaction_notes}".strip()
            
            donation.save()
            print(f"Updated donation {donation_id} to {status}")
            
        except Donation.DoesNotExist:
            print(f"Donation {donation_id} not found")
    
    def update_recurring_donation_status(self, donation_id, status, transaction_data):
        """Update recurring donation status"""
        try:
            recurring_donation = RecurringDonation.objects.get(id=donation_id)
            
            if status == 'completed':
                # Create individual donation record
                donation = Donation.objects.create(
                    donor=recurring_donation.donor,
                    is_anonymous=recurring_donation.is_anonymous,
                    campaign=recurring_donation.campaign,
                    project=recurring_donation.project,
                    amount=recurring_donation.amount,
                    currency=recurring_donation.currency,
                    payment_method=recurring_donation.payment_method,
                    transaction_id=transaction_data.get('transaction_id'),
                    reference_number=transaction_data.get('flutterwave_ref'),
                    bank_reference=transaction_data.get('tx_ref'),
                    status='completed',
                    processed_date=timezone.now(),
                    donation_source='website',
                    notes=f"Recurring donation payment #{recurring_donation.payment_count + 1}"
                )
                
                # Update recurring donation
                recurring_donation.record_successful_payment(donation)
                print(f"Recorded successful recurring payment for {donation_id}")
                
            elif status == 'failed':
                recurring_donation.record_failed_payment()
                print(f"Recorded failed recurring payment for {donation_id}")
                
        except RecurringDonation.DoesNotExist:
            print(f"Recurring donation {donation_id} not found")
    
    def update_in_kind_donation_status(self, donation_id, status, transaction_data):
        """Update in-kind donation status"""
        try:
            in_kind_donation = InKindDonation.objects.get(id=donation_id)
            
            if status == 'completed':
                in_kind_donation.status = 'confirmed'
            elif status == 'failed':
                in_kind_donation.status = 'pledged'
            
            # Add transaction notes
            transaction_notes = f"Processing fee: {transaction_data.get('transaction_id', 'N/A')}"
            in_kind_donation.notes = f"{in_kind_donation.notes or ''}\n{transaction_notes}".strip()
            
            in_kind_donation.save()
            print(f"Updated in-kind donation {donation_id} to {status}")
            
        except InKindDonation.DoesNotExist:

            print(f"In-kind donation {donation_id} not found")
@csrf_exempt
def flutterwave_webhook(request):
    if request.method == 'POST':
        try:
            signature = request.headers.get('X-FLW-SIGNATURE')
            body = request.body.decode('utf-8')
            secret_hash = settings.FLUTTERWAVE_SECRET_HASH  
            
            generated_signature = hashlib.sha256((body + secret_hash).encode('utf-8')).hexdigest()
            
            if generated_signature != signature:
                return HttpResponse('Invalid signature', status=400)
            
            data = json.loads(body)
            event_type = data.get('event')
            
            # Process the webhook data based on the event_type
            if event_type == 'charge.success':
                # Handle successful payment
                print("Payment successful:", data)
            elif event_type == 'charge.failed':
                # Handle failed payment
                print("Payment failed:", data)
            
            return HttpResponse('Webhook received', status=200)
        except Exception as e:
            print(f"Error processing webhook: {e}")
            return HttpResponse('Error processing webhook', status=500)
    else:
        return HttpResponse('Method not allowed', status=405)