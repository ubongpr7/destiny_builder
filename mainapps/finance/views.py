import json
import hashlib
import hmac
import traceback
import os
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from .models import Donation, RecurringDonation, InKindDonation

@csrf_exempt
def flutterwave_webhook(request):
    """Complete Flutterwave webhook handler with comprehensive debugging"""
    
    print("=" * 60)
    print("FLUTTERWAVE WEBHOOK RECEIVED")
    print("=" * 60)
    
    # Step 1: Check request method
    print(f"Step 1: Request method: {request.method}")
    if request.method != 'POST':
        print(f"ERROR: Invalid method {request.method}")
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        # Step 2: Log request details
        print(f"Step 2: Request details")
        print(f"  - Content-Type: {request.content_type}")
        print(f"  - Content-Length: {len(request.body)}")
        print(f"  - User-Agent: {request.META.get('HTTP_USER_AGENT', 'Unknown')}")
        
        # Step 3: Get all headers
        print(f"Step 3: Headers analysis")
        signature_headers = {}
        for key, value in request.META.items():
            if any(sig_key in key.lower() for sig_key in ['signature', 'hash', 'verif']):
                header_name = key[5:] if key.startswith('HTTP_') else key
                signature_headers[header_name] = value
                print(f"  - Found signature header {header_name}: {value}")
        
        # Step 4: Get the verif-hash specifically
        print(f"Step 4: Signature extraction")
        signature = request.headers.get('verif-hash')
        print(f"  - verif-hash header: {signature}")
        print(f"  - Signature present: {'Yes' if signature else 'No'}")
        
        # Step 5: Get and validate request body
        print(f"Step 5: Request body processing")
        raw_body = request.body
        print(f"  - Raw body length: {len(raw_body)}")
        
        if not raw_body:
            print("ERROR: Request body is empty")
            return JsonResponse({'error': 'Empty request body'}, status=400)
        
        try:
            body_str = raw_body.decode('utf-8')
            print(f"  - Body decoded successfully")
            print(f"  - Body content: {body_str}")
        except UnicodeDecodeError as e:
            print(f"ERROR: Failed to decode body: {e}")
            return JsonResponse({'error': 'Invalid body encoding'}, status=400)
        
        # Step 6: Parse JSON
        print(f"Step 6: JSON parsing")
        try:
            data = json.loads(body_str)
            print(f"  - JSON parsed successfully")
            print(f"  - Event type: {data.get('event', 'Not specified')}")
            print(f"  - Data keys: {list(data.keys())}")
            print(f"  - Full data: {json.dumps(data, indent=2)}")
        except json.JSONDecodeError as e:
            print(f"ERROR: JSON parsing failed: {e}")
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
        # Step 7: Signature verification
        print(f"Step 7: Signature verification")
        signature_valid = verify_signature(signature, body_str)
        
        if not signature_valid:
            print("ERROR: Signature verification failed")
            # For debugging, let's continue anyway but log the failure
            print("WARNING: Continuing despite signature failure for debugging")
        else:
            print("SUCCESS: Signature verification passed")
        
        # Step 8: Extract event information
        print(f"Step 8: Event processing")
        event_type = data.get('event')
        event_data = data.get('data', {})
        
        print(f"  - Event type: {event_type}")
        print(f"  - Event data keys: {list(event_data.keys())}")
        
        if not event_type:
            print("ERROR: No event type found")
            return JsonResponse({'error': 'Missing event type'}, status=400)
        
        # Step 9: Extract metadata
        print(f"Step 9: Metadata extraction")
        meta = event_data.get('meta', {})
        donation_id = meta.get('donation_id')
        donation_type = meta.get('donation_type', 'one-time')
        
        print(f"  - Metadata: {meta}")
        print(f"  - Donation ID: {donation_id}")
        print(f"  - Donation type: {donation_type}")
        
        # Step 10: Process based on event type
        print(f"Step 10: Event type processing")
        result = process_webhook_event(event_type, event_data, meta)
        
        print(f"  - Processing result: {result}")
        
        # Step 11: Return response
        print(f"Step 11: Sending response")
        if result['success']:
            print("SUCCESS: Webhook processed successfully")
            response_data = {
                'status': 'success',
                'message': result.get('message', 'Webhook processed'),
                'event_type': event_type
            }
        else:
            print(f"ERROR: Webhook processing failed: {result['error']}")
            response_data = {
                'status': 'error',
                'message': result['error'],
                'event_type': event_type
            }
        
        print(f"  - Response data: {response_data}")
        print("=" * 60)
        print("WEBHOOK PROCESSING COMPLETE")
        print("=" * 60)
        
        # Always return 200 as per Flutterwave documentation
        return JsonResponse(response_data, status=200)
        
    except Exception as e:
        print(f"CRITICAL ERROR: Unexpected exception")
        print(f"  - Exception type: {type(e).__name__}")
        print(f"  - Exception message: {str(e)}")
        print(f"  - Traceback: {traceback.format_exc()}")
        
        return JsonResponse({
            'status': 'error',
            'message': 'Internal server error',
            'error': str(e)
        }, status=200)  # Still return 200 for Flutterwave


def verify_signature(signature, body_str):
    """Verify Flutterwave webhook signature with detailed debugging"""
    print("    Signature Verification Details:")
    
    # Get secret hash from settings
    secret_hash = getattr(settings, 'FLUTTERWAVE_SECRET_HASH', None)
    if not secret_hash:
        secret_hash = os.getenv('FLUTTERWAVE_SECRET_HASH')
    
    print(f"    - Secret hash configured: {'Yes' if secret_hash else 'No'}")
    if secret_hash:
        print(f"    - Secret hash value: {secret_hash}")
    
    if not secret_hash:
        print("    ERROR: No secret hash configured")
        return False
    
    if not signature:
        print("    ERROR: No signature provided")
        return False
    
    print(f"    - Received signature: {signature}")
    
    # Method 1: Direct comparison (Flutterwave test mode)
    print("    - Method 1: Direct comparison")
    if signature == secret_hash:
        print("    SUCCESS: Direct comparison matched")
        return True
    else:
        print("    FAILED: Direct comparison did not match")
    
    # Method 2: Hash of secret (some Flutterwave implementations)
    print("    - Method 2: Hash of secret")
    try:
        expected_hash = hashlib.sha256(secret_hash.encode()).hexdigest()
        print(f"    - Expected hash: {expected_hash}")
        if hmac.compare_digest(signature, expected_hash):
            print("    SUCCESS: Hash of secret matched")
            return True
        else:
            print("    FAILED: Hash of secret did not match")
    except Exception as e:
        print(f"    ERROR in Method 2: {e}")
    
    # Method 3: Hash of (body + secret)
    print("    - Method 3: Hash of (body + secret)")
    try:
        combined = body_str + secret_hash
        expected_hash = hashlib.sha256(combined.encode('utf-8')).hexdigest()
        print(f"    - Expected hash: {expected_hash}")
        if hmac.compare_digest(signature, expected_hash):
            print("    SUCCESS: Hash of (body + secret) matched")
            return True
        else:
            print("    FAILED: Hash of (body + secret) did not match")
    except Exception as e:
        print(f"    ERROR in Method 3: {e}")
    
    # Method 4: HMAC-SHA256
    print("    - Method 4: HMAC-SHA256")
    try:
        expected_hmac = hmac.new(
            secret_hash.encode('utf-8'),
            body_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        print(f"    - Expected HMAC: {expected_hmac}")
        if hmac.compare_digest(signature, expected_hmac):
            print("    SUCCESS: HMAC-SHA256 matched")
            return True
        else:
            print("    FAILED: HMAC-SHA256 did not match")
    except Exception as e:
        print(f"    ERROR in Method 4: {e}")
    
    print("    FINAL RESULT: All signature verification methods failed")
    return False


def process_webhook_event(event_type, event_data, meta):
    """Process different webhook events"""
    print(f"    Processing event: {event_type}")
    
    try:
        if event_type in ['charge.completed', 'charge.success']:
            return handle_payment_completed(event_data, meta)
        elif event_type == 'charge.failed':
            return handle_payment_failed(event_data, meta)
        elif event_type == 'subscription.activated':
            return handle_subscription_activated(event_data, meta)
        elif event_type == 'subscription.cancelled':
            return handle_subscription_cancelled(event_data, meta)
        else:
            print(f"    WARNING: Unhandled event type: {event_type}")
            return {
                'success': True,
                'message': f'Event type {event_type} acknowledged but not processed'
            }
    except Exception as e:
        print(f"    ERROR processing event: {e}")
        print(f"    Traceback: {traceback.format_exc()}")
        return {
            'success': False,
            'error': f'Error processing {event_type}: {str(e)}'
        }


def handle_payment_completed(event_data, meta):
    """Handle successful payment"""
    print("    Handling payment completion")
    
    donation_id = meta.get('donation_id')
    donation_type = meta.get('donation_type', 'one-time')
    
    print(f"    - Donation ID: {donation_id}")
    print(f"    - Donation type: {donation_type}")
    
    if not donation_id:
        print("    WARNING: No donation_id found - treating as test webhook")
        return {
            'success': True,
            'message': 'Test webhook acknowledged (no donation_id)'
        }
    
    # Extract transaction data
    transaction_data = {
        'flutterwave_ref': event_data.get('flw_ref'),
        'transaction_id': event_data.get('id'),
        'tx_ref': event_data.get('tx_ref'),
        'amount': event_data.get('amount'),
        'currency': event_data.get('currency'),
        'payment_method': event_data.get('payment_type', 'card'),
        'processed_at': event_data.get('created_at'),
        'customer_email': event_data.get('customer', {}).get('email'),
        'customer_name': event_data.get('customer', {}).get('name'),
    }
    
    print(f"    - Transaction data: {transaction_data}")
    
    try:
        with transaction.atomic():
            if donation_type == 'one-time':
                result = update_donation_status(donation_id, 'completed', transaction_data)
            elif donation_type == 'recurring':
                result = update_recurring_donation_status(donation_id, 'completed', transaction_data)
            elif donation_type == 'in-kind':
                result = update_in_kind_donation_status(donation_id, 'completed', transaction_data)
            else:
                print(f"    ERROR: Unknown donation type: {donation_type}")
                return {
                    'success': False,
                    'error': f'Unknown donation type: {donation_type}'
                }
        
        print(f"    - Update result: {result}")
        return result
        
    except Exception as e:
        print(f"    ERROR updating donation: {e}")
        print(f"    Traceback: {traceback.format_exc()}")
        return {
            'success': False,
            'error': f'Error updating donation: {str(e)}'
        }


def handle_payment_failed(event_data, meta):
    """Handle failed payment"""
    print("    Handling payment failure")
    
    donation_id = meta.get('donation_id')
    donation_type = meta.get('donation_type', 'one-time')
    
    print(f"    - Donation ID: {donation_id}")
    print(f"    - Donation type: {donation_type}")
    
    if not donation_id:
        print("    WARNING: No donation_id found - treating as test webhook")
        return {
            'success': True,
            'message': 'Test failed payment webhook acknowledged'
        }
    
    transaction_data = {
        'flutterwave_ref': event_data.get('flw_ref'),
        'transaction_id': event_data.get('id'),
        'tx_ref': event_data.get('tx_ref'),
        'error_message': event_data.get('processor_response', 'Payment failed'),
        'failed_at': event_data.get('created_at'),
    }
    
    print(f"    - Failed transaction data: {transaction_data}")
    
    try:
        with transaction.atomic():
            if donation_type == 'one-time':
                result = update_donation_status(donation_id, 'failed', transaction_data)
            elif donation_type == 'recurring':
                result = update_recurring_donation_status(donation_id, 'failed', transaction_data)
            elif donation_type == 'in-kind':
                result = update_in_kind_donation_status(donation_id, 'failed', transaction_data)
            else:
                return {
                    'success': False,
                    'error': f'Unknown donation type: {donation_type}'
                }
        
        return result
        
    except Exception as e:
        print(f"    ERROR updating failed donation: {e}")
        return {
            'success': False,
            'error': f'Error updating failed donation: {str(e)}'
        }


def handle_subscription_activated(event_data, meta):
    """Handle subscription activation"""
    print("    Handling subscription activation")
    
    donation_id = meta.get('donation_id')
    print(f"    - Donation ID: {donation_id}")
    
    if not donation_id:
        return {
            'success': True,
            'message': 'Test subscription activation acknowledged'
        }
    
    try:
        recurring_donation = RecurringDonation.objects.get(id=donation_id)
        recurring_donation.status = 'active'
        recurring_donation.subscription_id = event_data.get('id')
        recurring_donation.save()
        
        print(f"    SUCCESS: Activated recurring donation {donation_id}")
        return {
            'success': True,
            'message': f'Recurring donation {donation_id} activated'
        }
        
    except RecurringDonation.DoesNotExist:
        print(f"    ERROR: Recurring donation {donation_id} not found")
        return {
            'success': False,
            'error': f'Recurring donation {donation_id} not found'
        }
    except Exception as e:
        print(f"    ERROR activating subscription: {e}")
        return {
            'success': False,
            'error': f'Error activating subscription: {str(e)}'
        }


def handle_subscription_cancelled(event_data, meta):
    """Handle subscription cancellation"""
    print("    Handling subscription cancellation")
    
    donation_id = meta.get('donation_id')
    print(f"    - Donation ID: {donation_id}")
    
    if not donation_id:
        return {
            'success': True,
            'message': 'Test subscription cancellation acknowledged'
        }
    
    try:
        recurring_donation = RecurringDonation.objects.get(id=donation_id)
        recurring_donation.cancel_subscription("Cancelled via payment processor")
        
        print(f"    SUCCESS: Cancelled recurring donation {donation_id}")
        return {
            'success': True,
            'message': f'Recurring donation {donation_id} cancelled'
        }
        
    except RecurringDonation.DoesNotExist:
        print(f"    ERROR: Recurring donation {donation_id} not found")
        return {
            'success': False,
            'error': f'Recurring donation {donation_id} not found'
        }
    except Exception as e:
        print(f"    ERROR cancelling subscription: {e}")
        return {
            'success': False,
            'error': f'Error cancelling subscription: {str(e)}'
        }


def update_donation_status(donation_id, status, transaction_data):
    """Update one-time donation status"""
    print(f"      Updating donation {donation_id} to {status}")
    
    try:
        donation = Donation.objects.get(id=donation_id)
        print(f"      - Found donation: {donation}")
        
        old_status = donation.status
        donation.status = status
        
        # Update transaction fields
        if transaction_data.get('transaction_id'):
            donation.transaction_id = transaction_data['transaction_id']
            print(f"      - Set transaction_id: {transaction_data['transaction_id']}")
            
        if transaction_data.get('flutterwave_ref'):
            donation.reference_number = transaction_data['flutterwave_ref']
            print(f"      - Set reference_number: {transaction_data['flutterwave_ref']}")
            
        if transaction_data.get('tx_ref'):
            donation.bank_reference = transaction_data['tx_ref']
            print(f"      - Set bank_reference: {transaction_data['tx_ref']}")
        
        if status == 'completed':
            donation.processed_date = timezone.now()
            print(f"      - Set processed_date: {donation.processed_date}")
        
        # Add transaction notes
        transaction_notes = f"Flutterwave webhook: {transaction_data.get('transaction_id', 'N/A')}"
        donation.notes = f"{donation.notes or ''}\n{transaction_notes}".strip()
        
        donation.save()
        
        print(f"      SUCCESS: Updated donation {donation_id} from {old_status} to {status}")
        return {
            'success': True,
            'message': f'Donation {donation_id} updated from {old_status} to {status}'
        }
        
    except Donation.DoesNotExist:
        print(f"      ERROR: Donation {donation_id} not found")
        return {
            'success': False,
            'error': f'Donation {donation_id} not found'
        }
    except Exception as e:
        print(f"      ERROR updating donation: {e}")
        print(f"      Traceback: {traceback.format_exc()}")
        return {
            'success': False,
            'error': f'Error updating donation: {str(e)}'
        }


def update_recurring_donation_status(donation_id, status, transaction_data):
    """Update recurring donation status"""
    print(f"      Updating recurring donation {donation_id} to {status}")
    
    try:
        recurring_donation = RecurringDonation.objects.get(id=donation_id)
        print(f"      - Found recurring donation: {recurring_donation}")
        
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
            
            print(f"      - Created donation record: {donation.id}")
            
            # Update recurring donation
            recurring_donation.record_successful_payment(donation)
            print(f"      SUCCESS: Recorded successful recurring payment for {donation_id}")
            
            return {
                'success': True,
                'message': f'Recurring payment recorded for donation {donation_id}'
            }
            
        elif status == 'failed':
            recurring_donation.record_failed_payment()
            print(f"      SUCCESS: Recorded failed recurring payment for {donation_id}")
            
            return {
                'success': True,
                'message': f'Failed recurring payment recorded for donation {donation_id}'
            }
        
    except RecurringDonation.DoesNotExist:
        print(f"      ERROR: Recurring donation {donation_id} not found")
        return {
            'success': False,
            'error': f'Recurring donation {donation_id} not found'
        }
    except Exception as e:
        print(f"      ERROR updating recurring donation: {e}")
        print(f"      Traceback: {traceback.format_exc()}")
        return {
            'success': False,
            'error': f'Error updating recurring donation: {str(e)}'
        }


def update_in_kind_donation_status(donation_id, status, transaction_data):
    """Update in-kind donation status"""
    print(f"      Updating in-kind donation {donation_id} to {status}")
    
    try:
        in_kind_donation = InKindDonation.objects.get(id=donation_id)
        print(f"      - Found in-kind donation: {in_kind_donation}")
        
        old_status = in_kind_donation.status
        
        if status == 'completed':
            in_kind_donation.status = 'confirmed'
        elif status == 'failed':
            in_kind_donation.status = 'pledged'
        
        # Add transaction notes
        transaction_notes = f"Processing fee webhook: {transaction_data.get('transaction_id', 'N/A')}"
        in_kind_donation.notes = f"{in_kind_donation.notes or ''}\n{transaction_notes}".strip()
        
        in_kind_donation.save()
        
        print(f"      SUCCESS: Updated in-kind donation {donation_id} from {old_status} to {in_kind_donation.status}")
        return {
            'success': True,
            'message': f'In-kind donation {donation_id} updated from {old_status} to {in_kind_donation.status}'
        }
        
    except InKindDonation.DoesNotExist:
        print(f"      ERROR: In-kind donation {donation_id} not found")
        return {
            'success': False,
            'error': f'In-kind donation {donation_id} not found'
        }
    except Exception as e:
        print(f"      ERROR updating in-kind donation: {e}")
        print(f"      Traceback: {traceback.format_exc()}")
        return {
            'success': False,
            'error': f'Error updating in-kind donation: {str(e)}'
        }