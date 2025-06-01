import json
import hashlib
import hmac
import logging
import os
import traceback
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from django.utils import timezone
from django.db import transaction
from .models import Donation, RecurringDonation, InKindDonation

# Set up comprehensive logging
logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class FlutterwaveWebhookView(View):
    """Enhanced webhook handler with comprehensive debugging"""
    
    def dispatch(self, request, *args, **kwargs):
        """Log all incoming requests"""
        logger.info(f"=== WEBHOOK REQUEST START ===")
        logger.info(f"Method: {request.method}")
        logger.info(f"Path: {request.path}")
        logger.info(f"Content-Type: {request.content_type}")
        logger.info(f"Content-Length: {request.META.get('CONTENT_LENGTH', 'Unknown')}")
        
        # Log all headers (be careful with sensitive data)
        headers_to_log = {}
        for key, value in request.META.items():
            if key.startswith('HTTP_'):
                header_name = key[5:].replace('_', '-').title()
                # Don't log sensitive headers in full
                if 'signature' in header_name.lower() or 'hash' in header_name.lower():
                    headers_to_log[header_name] = f"{value[:10]}..." if len(value) > 10 else value
                else:
                    headers_to_log[header_name] = value
        
        logger.info(f"Headers: {headers_to_log}")
        
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request):
        """Handle POST requests with comprehensive debugging"""
        try:
            # Log raw request body
            raw_body = request.body
            logger.info(f"Raw body length: {len(raw_body)}")
            logger.info(f"Raw body (first 500 chars): {raw_body[:500]}")
            
            # Check if body is empty
            if not raw_body:
                logger.error("ERROR: Request body is empty")
                return JsonResponse({
                    'error': 'Empty request body',
                    'status': 'failed'
                }, status=400)
            
            # Try to decode body
            try:
                body_str = raw_body.decode('utf-8')
                logger.info(f"Decoded body: {body_str}")
            except UnicodeDecodeError as e:
                logger.error(f"ERROR: Failed to decode request body: {e}")
                return JsonResponse({
                    'error': 'Invalid request body encoding',
                    'status': 'failed'
                }, status=400)
            
            # Try to parse JSON
            try:
                payload = json.loads(body_str)
                logger.info(f"Parsed JSON payload: {json.dumps(payload, indent=2)}")
            except json.JSONDecodeError as e:
                logger.error(f"ERROR: Failed to parse JSON: {e}")
                logger.error(f"JSON error at position: {e.pos}")
                logger.error(f"JSON error message: {e.msg}")
                return JsonResponse({
                    'error': 'Invalid JSON format',
                    'json_error': str(e),
                    'status': 'failed'
                }, status=400)
            
            # Verify webhook signature
            signature_valid, signature_error = self.verify_webhook_signature(request, raw_body)
            if not signature_valid:
                logger.error(f"ERROR: Signature verification failed: {signature_error}")
                return JsonResponse({
                    'error': 'Invalid signature',
                    'signature_error': signature_error,
                    'status': 'failed'
                }, status=400)
            
            logger.info("SUCCESS: Signature verification passed")
            
            # Extract event data
            event_type = payload.get('event')
            data = payload.get('data', {})
            
            logger.info(f"Event type: {event_type}")
            logger.info(f"Event data: {json.dumps(data, indent=2)}")
            
            if not event_type:
                logger.error("ERROR: No event type in payload")
                return JsonResponse({
                    'error': 'Missing event type',
                    'status': 'failed'
                }, status=400)
            
            # Process different event types
            result = self.process_webhook_event(event_type, data, payload)
            
            if result['success']:
                logger.info(f"SUCCESS: Webhook processed successfully")
                return JsonResponse({
                    'status': 'success',
                    'message': 'Webhook processed successfully',
                    'event_type': event_type
                }, status=200)
            else:
                logger.error(f"ERROR: Webhook processing failed: {result['error']}")
                return JsonResponse({
                    'error': result['error'],
                    'status': 'failed',
                    'event_type': event_type
                }, status=400)
            
        except Exception as e:
            logger.error(f"CRITICAL ERROR: Unexpected exception in webhook handler")
            logger.error(f"Exception type: {type(e).__name__}")
            logger.error(f"Exception message: {str(e)}")
            logger.error(f"Exception traceback: {traceback.format_exc()}")
            
            return JsonResponse({
                'error': 'Internal server error',
                'exception': str(e),
                'status': 'failed'
            }, status=500)
        
        finally:
            logger.info(f"=== WEBHOOK REQUEST END ===\n")
    
    def verify_webhook_signature(self, request, raw_body):
        """Verify Flutterwave webhook signature with detailed logging"""
        try:
            # Get secret hash from environment
            secret_hash = getattr(settings, 'FLUTTERWAVE_SECRET_HASH', None)
            if not secret_hash:
                secret_hash = os.getenv('FLUTTERWAVE_SECRET_HASH')
            
            logger.info(f"Secret hash configured: {'Yes' if secret_hash else 'No'}")
            
            if not secret_hash:
                return False, "No secret hash configured in settings or environment"
            
            # Get signature from headers - try multiple header names
            signature = None
            possible_headers = ['verif-hash', 'X-FLW-SIGNATURE', 'x-flw-signature']
            
            for header_name in possible_headers:
                signature = request.headers.get(header_name)
                if signature:
                    logger.info(f"Found signature in header '{header_name}': {signature[:10]}...")
                    break
                else:
                    logger.info(f"No signature found in header '{header_name}'")
            
            if not signature:
                return False, f"No signature found in any of these headers: {possible_headers}"
            
            # Method 1: Flutterwave standard verification (hash of secret)
            try:
                expected_signature_1 = hashlib.sha256(secret_hash.encode()).hexdigest()
                logger.info(f"Method 1 - Expected signature: {expected_signature_1[:10]}...")
                
                if hmac.compare_digest(signature, expected_signature_1):
                    logger.info("SUCCESS: Signature verified using Method 1 (hash of secret)")
                    return True, "Verified using Method 1"
            except Exception as e:
                logger.error(f"Method 1 verification error: {e}")
            
            # Method 2: Hash of body + secret
            try:
                body_str = raw_body.decode('utf-8') if isinstance(raw_body, bytes) else raw_body
                expected_signature_2 = hashlib.sha256((body_str + secret_hash).encode('utf-8')).hexdigest()
                logger.info(f"Method 2 - Expected signature: {expected_signature_2[:10]}...")
                
                if hmac.compare_digest(signature, expected_signature_2):
                    logger.info("SUCCESS: Signature verified using Method 2 (body + secret)")
                    return True, "Verified using Method 2"
            except Exception as e:
                logger.error(f"Method 2 verification error: {e}")
            
            # Method 3: HMAC with secret key
            try:
                expected_signature_3 = hmac.new(
                    secret_hash.encode('utf-8'),
                    raw_body,
                    hashlib.sha256
                ).hexdigest()
                logger.info(f"Method 3 - Expected signature: {expected_signature_3[:10]}...")
                
                if hmac.compare_digest(signature, expected_signature_3):
                    logger.info("SUCCESS: Signature verified using Method 3 (HMAC)")
                    return True, "Verified using Method 3"
            except Exception as e:
                logger.error(f"Method 3 verification error: {e}")
            
            return False, f"Signature verification failed with all methods. Received: {signature[:10]}..."
            
        except Exception as e:
            logger.error(f"Signature verification exception: {e}")
            return False, f"Signature verification exception: {str(e)}"
    
    def process_webhook_event(self, event_type, data, full_payload):
        """Process webhook events with comprehensive error handling"""
        try:
            logger.info(f"Processing event: {event_type}")
            
            # Extract metadata
            meta = data.get('meta', {})
            logger.info(f"Metadata: {meta}")
            
            donation_id = meta.get('donation_id')
            donation_type = meta.get('donation_type', 'one-time')
            
            logger.info(f"Donation ID: {donation_id}")
            logger.info(f"Donation type: {donation_type}")
            
            if event_type == 'charge.completed':
                return self.handle_payment_completed(data, meta)
            elif event_type == 'charge.failed':
                return self.handle_payment_failed(data, meta)
            elif event_type == 'charge.success':  # Alternative event name
                return self.handle_payment_completed(data, meta)
            elif event_type == 'subscription.activated':
                return self.handle_subscription_activated(data, meta)
            elif event_type == 'subscription.cancelled':
                return self.handle_subscription_cancelled(data, meta)
            else:
                logger.warning(f"Unhandled event type: {event_type}")
                return {
                    'success': True,
                    'message': f'Event type {event_type} acknowledged but not processed'
                }
                
        except Exception as e:
            logger.error(f"Error processing webhook event: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                'success': False,
                'error': f'Error processing event: {str(e)}'
            }
    
    def handle_payment_completed(self, data, meta):
        """Handle successful payment with detailed logging"""
        try:
            donation_id = meta.get('donation_id')
            donation_type = meta.get('donation_type', 'one-time')
            
            logger.info(f"Handling completed payment for {donation_type} donation ID: {donation_id}")
            
            if not donation_id:
                logger.error("No donation_id in metadata")
                return {'success': False, 'error': 'Missing donation_id in metadata'}
            
            # Extract transaction data
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
            
            logger.info(f"Transaction data: {transaction_data}")
            
            # Update donation based on type
            with transaction.atomic():
                if donation_type == 'one-time':
                    result = self.update_donation_status(donation_id, 'completed', transaction_data)
                elif donation_type == 'recurring':
                    result = self.update_recurring_donation_status(donation_id, 'completed', transaction_data)
                elif donation_type == 'in-kind':
                    result = self.update_in_kind_donation_status(donation_id, 'completed', transaction_data)
                else:
                    logger.error(f"Unknown donation type: {donation_type}")
                    return {'success': False, 'error': f'Unknown donation type: {donation_type}'}
            
            return result
            
        except Exception as e:
            logger.error(f"Error handling completed payment: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {'success': False, 'error': f'Error handling completed payment: {str(e)}'}
    
    def handle_payment_failed(self, data, meta):
        """Handle failed payment with detailed logging"""
        try:
            donation_id = meta.get('donation_id')
            donation_type = meta.get('donation_type', 'one-time')
            
            logger.info(f"Handling failed payment for {donation_type} donation ID: {donation_id}")
            
            if not donation_id:
                logger.error("No donation_id in metadata")
                return {'success': False, 'error': 'Missing donation_id in metadata'}
            
            transaction_data = {
                'flutterwave_ref': data.get('flw_ref'),
                'transaction_id': data.get('id'),
                'tx_ref': data.get('tx_ref'),
                'error_message': data.get('processor_response', 'Payment failed'),
                'failed_at': data.get('created_at'),
            }
            
            logger.info(f"Failed transaction data: {transaction_data}")
            
            # Update donation based on type
            with transaction.atomic():
                if donation_type == 'one-time':
                    result = self.update_donation_status(donation_id, 'failed', transaction_data)
                elif donation_type == 'recurring':
                    result = self.update_recurring_donation_status(donation_id, 'failed', transaction_data)
                elif donation_type == 'in-kind':
                    result = self.update_in_kind_donation_status(donation_id, 'failed', transaction_data)
                else:
                    logger.error(f"Unknown donation type: {donation_type}")
                    return {'success': False, 'error': f'Unknown donation type: {donation_type}'}
            
            return result
            
        except Exception as e:
            logger.error(f"Error handling failed payment: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {'success': False, 'error': f'Error handling failed payment: {str(e)}'}
    
    def update_donation_status(self, donation_id, status, transaction_data):
        """Update one-time donation status with detailed logging"""
        try:
            logger.info(f"Updating donation {donation_id} to status: {status}")
            
            donation = Donation.objects.get(id=donation_id)
            logger.info(f"Found donation: {donation}")
            
            old_status = donation.status
            donation.status = status
            
            # Update transaction fields
            if transaction_data.get('transaction_id'):
                donation.transaction_id = transaction_data['transaction_id']
            if transaction_data.get('flutterwave_ref'):
                donation.reference_number = transaction_data['flutterwave_ref']
            if transaction_data.get('tx_ref'):
                donation.bank_reference = transaction_data['tx_ref']
            
            if status == 'completed':
                donation.processed_date = timezone.now()
            
            # Add transaction notes
            transaction_notes = f"Flutterwave webhook: {transaction_data.get('transaction_id', 'N/A')}"
            donation.notes = f"{donation.notes or ''}\n{transaction_notes}".strip()
            
            donation.save()
            
            logger.info(f"Successfully updated donation {donation_id} from {old_status} to {status}")
            return {'success': True, 'message': f'Donation updated from {old_status} to {status}'}
            
        except Donation.DoesNotExist:
            logger.error(f"Donation {donation_id} not found")
            return {'success': False, 'error': f'Donation {donation_id} not found'}
        except Exception as e:
            logger.error(f"Error updating donation {donation_id}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {'success': False, 'error': f'Error updating donation: {str(e)}'}
    
    def update_recurring_donation_status(self, donation_id, status, transaction_data):
        """Update recurring donation status with detailed logging"""
        try:
            logger.info(f"Updating recurring donation {donation_id} to status: {status}")
            
            recurring_donation = RecurringDonation.objects.get(id=donation_id)
            logger.info(f"Found recurring donation: {recurring_donation}")
            
            if status == 'completed':
                # Create individual donation record
                donation = Donation.objects.create(
                    donor=recurring_donation.donor,
                    is_anonymous=recurring_donation.is_anonymous,
                    campaign=recurring_donation.campaign,
                    project=getattr(recurring_donation, 'project', None),
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
                
                logger.info(f"Created donation record: {donation}")
                
                # Update recurring donation
                recurring_donation.record_successful_payment(donation)
                logger.info(f"Recorded successful payment for recurring donation {donation_id}")
                
                return {'success': True, 'message': f'Recurring payment recorded successfully'}
                
            elif status == 'failed':
                recurring_donation.record_failed_payment()
                logger.info(f"Recorded failed payment for recurring donation {donation_id}")
                
                return {'success': True, 'message': f'Failed payment recorded'}
            
        except RecurringDonation.DoesNotExist:
            logger.error(f"Recurring donation {donation_id} not found")
            return {'success': False, 'error': f'Recurring donation {donation_id} not found'}
        except Exception as e:
            logger.error(f"Error updating recurring donation {donation_id}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {'success': False, 'error': f'Error updating recurring donation: {str(e)}'}
    
    def update_in_kind_donation_status(self, donation_id, status, transaction_data):
        """Update in-kind donation status with detailed logging"""
        try:
            logger.info(f"Updating in-kind donation {donation_id} to status: {status}")
            
            in_kind_donation = InKindDonation.objects.get(id=donation_id)
            logger.info(f"Found in-kind donation: {in_kind_donation}")
            
            old_status = in_kind_donation.status
            
            if status == 'completed':
                in_kind_donation.status = 'confirmed'
            elif status == 'failed':
                in_kind_donation.status = 'pledged'
            
            # Add transaction notes
            transaction_notes = f"Processing fee webhook: {transaction_data.get('transaction_id', 'N/A')}"
            in_kind_donation.notes = f"{in_kind_donation.notes or ''}\n{transaction_notes}".strip()
            
            in_kind_donation.save()
            
            logger.info(f"Successfully updated in-kind donation {donation_id} from {old_status} to {in_kind_donation.status}")
            return {'success': True, 'message': f'In-kind donation updated from {old_status} to {in_kind_donation.status}'}
            
        except InKindDonation.DoesNotExist:
            logger.error(f"In-kind donation {donation_id} not found")
            return {'success': False, 'error': f'In-kind donation {donation_id} not found'}
        except Exception as e:
            logger.error(f"Error updating in-kind donation {donation_id}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {'success': False, 'error': f'Error updating in-kind donation: {str(e)}'}

# Alternative function-based webhook for testing
@csrf_exempt
def flutterwave_webhook_debug(request):
    """Alternative webhook handler for debugging"""
    logger.info("=== FUNCTION-BASED WEBHOOK START ===")
    
    if request.method != 'POST':
        logger.error(f"Invalid method: {request.method}")
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        # Log request details
        logger.info(f"Content-Type: {request.content_type}")
        logger.info(f"Content-Length: {len(request.body)}")
        
        # Get signature
        signature = request.headers.get('X-FLW-SIGNATURE') or request.headers.get('verif-hash')
        logger.info(f"Signature present: {'Yes' if signature else 'No'}")
        
        if signature:
            logger.info(f"Signature (first 10 chars): {signature[:10]}")
        
        # Get and log body
        body = request.body.decode('utf-8')
        logger.info(f"Request body: {body}")
        
        # Parse JSON
        data = json.loads(body)
        logger.info(f"Parsed data: {json.dumps(data, indent=2)}")
        
        # Verify signature if present
        if signature:
            secret_hash = getattr(settings, 'FLUTTERWAVE_SECRET_HASH', None)
            if secret_hash:
                generated_signature = hashlib.sha256((body + secret_hash).encode('utf-8')).hexdigest()
                logger.info(f"Generated signature: {generated_signature}")
                logger.info(f"Signatures match: {signature == generated_signature}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Webhook received and logged',
            'event': data.get('event', 'unknown')
        })
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return JsonResponse({
            'error': str(e),
            'status': 'failed'
        }, status=500)
    
    finally:
        logger.info("=== FUNCTION-BASED WEBHOOK END ===\n")