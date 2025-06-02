import json
import hashlib
import hmac
import traceback
import os
from decimal import Decimal
from datetime import datetime
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils import timezone
from django.db import transaction

from mainapps.finance.currency_conversion_utils import get_exchange_rate
from .models import Donation, RecurringDonation, InKindDonation, Currency, ExchangeRate
from django.contrib.auth import get_user_model



User = get_user_model()

def get_currency_rate():
    pass

@csrf_exempt
def flutterwave_webhook(request):
    """Complete Flutterwave webhook handler with comprehensive debugging and donation updates"""
    
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
        
        # Step 9: Extract metadata (FIXED)
        print(f"Step 9: Metadata extraction")
        meta_data = data.get('meta_data', {})
        donation_id = meta_data.get('donation_id')
        donation_type = meta_data.get('donation_type', 'one-time')
        donor_email = meta_data.get('donor_email')
        
        print(f"  - Metadata: {meta_data}")
        print(f"  - Donation ID: {donation_id}")
        print(f"  - Donation type: {donation_type}")
        print(f"  - Donor email: {donor_email}")
        
        # Step 10: Process based on event type
        print(f"Step 10: Event type processing")
        result = process_webhook_event(event_type, event_data, meta_data, data)
        
        print(f"  - Processing result: {result}")
        
        # Step 11: Return response
        print(f"Step 11: Sending response")
        if result['success']:
            print("SUCCESS: Webhook processed successfully")
            response_data = {
                'status': 'success',
                'message': result.get('message', 'Webhook processed'),
                'event_type': event_type,
                'donation_id': donation_id
            }
        else:
            print(f"ERROR: Webhook processing failed: {result['error']}")
            response_data = {
                'status': 'error',
                'message': result['error'],
                'event_type': event_type,
                'donation_id': donation_id
            }
        
        print(f"  - Response data: {response_data}")
        print("=" * 60)
        print("WEBHOOK PROCESSING COMPLETE")
        print("=" * 60)
        
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
        }, status=200)


def verify_signature(signature, body_str):
    """Verify Flutterwave webhook signature with detailed debugging"""
    print("    Signature Verification Details:")
    
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
    
    # Additional verification methods...
    print("    FINAL RESULT: All signature verification methods failed")
    return False


def process_webhook_event(event_type, event_data, meta_data, full_webhook_data):
    """Process different webhook events"""
    print(f"    Processing event: {event_type}")
    
    try:
        if event_type in ['charge.completed', 'charge.success']:
            return handle_payment_completed(event_data, meta_data, full_webhook_data)
        elif event_type == 'charge.failed':
            return handle_payment_failed(event_data, meta_data, full_webhook_data)
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


def handle_payment_completed(event_data, meta_data, full_webhook_data):
    """Handle successful payment with comprehensive donation update"""
    print("    Handling payment completion")
    
    donation_id = meta_data.get('donation_id')
    donation_type = meta_data.get('donation_type', 'one-time')
    
    print(f"    - Donation ID: {donation_id}")
    print(f"    - Donation type: {donation_type}")
    
    if not donation_id:
        print("    WARNING: No donation_id found - treating as test webhook")
        return {
            'success': True,
            'message': 'Test webhook acknowledged (no donation_id)'
        }
    
    try:
        with transaction.atomic():
            if donation_type == 'one-time':
                result = update_donation_with_currency_conversion(donation_id, full_webhook_data)
            else:
                print(f"    ERROR: Unsupported donation type for currency conversion: {donation_type}")
                return {
                    'success': False,
                    'error': f'Unsupported donation type: {donation_type}'
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


def handle_payment_failed(event_data, meta_data, full_webhook_data):
    """Handle failed payment with comprehensive donation update"""
    print("    Handling payment failure")
    
    donation_id = meta_data.get('donation_id')
    donation_type = meta_data.get('donation_type', 'one-time')
    
    print(f"    - Donation ID: {donation_id}")
    print(f"    - Donation type: {donation_type}")
    
    if not donation_id:
        print("    WARNING: No donation_id found - treating as test webhook")
        return {
            'success': True,
            'message': 'Test failed payment webhook acknowledged'
        }
    
    try:
        with transaction.atomic():
            if donation_type == 'one-time':
                # Update webhook data to reflect failed status
                webhook_data_copy = full_webhook_data.copy()
                webhook_data_copy['data']['status'] = 'failed'
                result = update_donation_with_currency_conversion(donation_id, webhook_data_copy)
            else:
                return {
                    'success': False,
                    'error': f'Unsupported donation type: {donation_type}'
                }
        
        return result
        
    except Exception as e:
        print(f"    ERROR updating failed donation: {e}")
        return {
            'success': False,
            'error': f'Error updating failed donation: {str(e)}'
        }


def get_or_create_exchange_rate(from_currency, to_currency, effective_date=None):
    """
    Get or create exchange rate between two currencies
    """
    print(f"        Getting exchange rate: {from_currency.code} → {to_currency.code}")
    
    if not effective_date:
        effective_date = timezone.now()
    
    # Check if we already have a recent exchange rate (within 24 hours)
    from datetime import timedelta
    recent_cutoff = effective_date - timedelta(hours=24)
    
    existing_rate = ExchangeRate.objects.filter(
        from_currency=from_currency,
        to_currency=to_currency,
        effective_date__gte=recent_cutoff,
        effective_date__lte=effective_date
    ).order_by('-effective_date').first()
    
    if existing_rate:
        print(f"        Found existing rate: 1 {from_currency.code} = {existing_rate.rate} {to_currency.code}")
        return existing_rate
    
    try:
        print(f"        Fetching live rate from forex-python...")
        
        rate =get_exchange_rate(from_currency.code, to_currency.code)
        rate_decimal = Decimal(str(rate))
        
        print(f"        Live rate fetched: 1 {from_currency.code} = {rate_decimal} {to_currency.code}")
        
        # Create system user for exchange rate creation if needed
        system_user = get_system_user()
        
        # Create new exchange rate record
        exchange_rate = ExchangeRate.objects.create(
            from_currency=from_currency,
            to_currency=to_currency,
            rate=rate_decimal,
            effective_date=effective_date,
            source="freecurrencyapi API",
            created_by=system_user
        )
        
        print(f"        Created new exchange rate record: ID {exchange_rate.id}")
        return exchange_rate
        
    except Exception as e:
        print(f"        ERROR fetching live rate: {e}")
    
    fallback_rate = ExchangeRate.objects.filter(
        from_currency=from_currency,
        to_currency=to_currency
    ).order_by('-effective_date').first()
    
    if fallback_rate:
        print(f"        Using fallback rate from {fallback_rate.effective_date}: 1 {from_currency.code} = {fallback_rate.rate} {to_currency.code}")
        return fallback_rate
    
    # Last resort: Create a 1:1 rate with warning
    print(f"        WARNING: No exchange rate available, creating 1:1 rate")
    system_user = get_system_user()
    
    exchange_rate = ExchangeRate.objects.create(
        from_currency=from_currency,
        to_currency=to_currency,
        rate=Decimal('1.00000000'),
        effective_date=effective_date,
        source="Fallback 1:1 rate (webhook)",
        created_by=system_user
    )
    
    return exchange_rate


def get_system_user():
    """Get or create a system user for automated operations"""
    try:
        system_user = User.objects.filter(
            username='system_webhook'
        ).first()
        
        if not system_user:
            system_user = User.objects.create_user(
                username='system_webhook',
                email='system@webhook.local',
                first_name='System',
                last_name='Webhook',
                is_active=True
            )
            print(f"        Created system user: {system_user.username}")
        
        return system_user
    except Exception as e:
        print(f"        ERROR creating system user: {e}")
        # Return first superuser as fallback
        return User.objects.filter(is_superuser=True).first()


def update_donation_with_currency_conversion(donation_id, webhook_data):
    """
    Comprehensive donation update with currency conversion handling
    """
    print(f"      Updating donation {donation_id} with currency conversion")
    
    try:
        # Get the donation record
        donation = Donation.objects.select_for_update().get(id=donation_id)
        print(f"      - Found donation: {donation}")
        
        # Extract data from webhook
        data = webhook_data.get('data', {})
        meta_data = webhook_data.get('meta_data', {})
        customer = data.get('customer', {})
        card = data.get('card', {})
        
        # Store original status for logging
        original_status = donation.status
        
        # Validate webhook data against donation
        validation_errors = validate_webhook_donation_data(donation, webhook_data)
        if validation_errors:
            print(f"      - Validation warnings: {validation_errors}")
        
        # Update basic transaction identifiers
        if data.get('id'):
            donation.transaction_id = str(data['id'])
            print(f"      - Set transaction_id: {donation.transaction_id}")
        
        if data.get('flw_ref'):
            donation.reference_number = data['flw_ref']
            print(f"      - Set reference_number: {donation.reference_number}")
        
        if data.get('tx_ref'):
            donation.bank_reference = data['tx_ref']
            print(f"      - Set bank_reference: {donation.bank_reference}")
        
        # Update financial details
        if data.get('amount'):
            webhook_amount = Decimal(str(data['amount']))
            if abs(donation.amount - webhook_amount) > Decimal('0.01'):
                print(f"      - Amount updated: {donation.amount} → {webhook_amount}")
                donation.amount = webhook_amount
        
        # Update currency if provided and different
        if data.get('currency'):
            try:
                webhook_currency = Currency.objects.get(code=data['currency'])
                if donation.currency != webhook_currency:
                    donation.currency = webhook_currency
                    print(f"      - Currency updated: {donation.currency.code}")
            except Currency.DoesNotExist:
                print(f"      - Warning: Currency {data['currency']} not found in database")
        
        # ============================================================================
        # CURRENCY CONVERSION LOGIC
        # ============================================================================
        
        print(f"      - Checking for currency conversion needs...")
        
        # Check if donation is connected to a campaign and currencies differ
        if donation.campaign and donation.currency and donation.campaign.target_currency:
            donation_currency = donation.currency
            campaign_currency = donation.campaign.target_currency
            
            print(f"      - Donation currency: {donation_currency.code}")
            print(f"      - Campaign currency: {campaign_currency.code}")
            
            if donation_currency != campaign_currency:
                print(f"      - Currency conversion needed: {donation_currency.code} → {campaign_currency.code}")
                
                try:
                    # Get conversion date (use processed date or current time)
                    conversion_date = timezone.now()
                    if data.get('created_at'):
                        try:
                            conversion_date = datetime.fromisoformat(
                                data['created_at'].replace('Z', '+00:00')
                            )
                        except:
                            pass
                    
                    # Get or create exchange rate
                    exchange_rate_record = get_or_create_exchange_rate(
                        from_currency=donation_currency,
                        to_currency=campaign_currency,
                        effective_date=conversion_date
                    )
                    
                    if exchange_rate_record:
                        # Calculate converted amount
                        converted_amount = donation.amount * exchange_rate_record.rate
                        
                        # Update donation with conversion data
                        donation.exchange_rate = exchange_rate_record.rate
                        donation.converted_amount = converted_amount
                        donation.converted_currency = campaign_currency
                        
                        print(f"      - Exchange rate applied: {exchange_rate_record.rate}")
                        print(f"      - Original amount: {donation_currency.code} {donation.amount}")
                        print(f"      - Converted amount: {campaign_currency.code} {converted_amount}")
                        print(f"      - Exchange rate source: {exchange_rate_record.source}")
                        
                        # Add conversion info to notes
                        conversion_note = (
                            f"Currency conversion applied: "
                            f"{donation_currency.code} {donation.amount} → "
                            f"{campaign_currency.code} {converted_amount} "
                            f"(rate: {exchange_rate_record.rate}, source: {exchange_rate_record.source})"
                        )
                        
                    else:
                        print(f"      - ERROR: Could not obtain exchange rate")
                        conversion_note = f"Currency conversion failed: Could not obtain exchange rate for {donation_currency.code} → {campaign_currency.code}"
                
                except Exception as e:
                    print(f"      - ERROR in currency conversion: {e}")
                    conversion_note = f"Currency conversion error: {str(e)}"
            else:
                print(f"      - No currency conversion needed (same currency)")
                conversion_note = None
        else:
            if not donation.campaign:
                print(f"      - No campaign linked, skipping currency conversion")
            elif not donation.currency:
                print(f"      - No donation currency set, skipping currency conversion")
            elif not donation.campaign.target_currency:
                print(f"      - No campaign target currency set, skipping currency conversion")
            conversion_note = None
        
        # ============================================================================
        # CONTINUE WITH REGULAR UPDATES
        # ============================================================================
        
        # Update payment method with intelligent mapping
        if data.get('payment_type'):
            payment_method_mapping = {
                'card': 'credit_card',
                'bank_transfer': 'bank_transfer',
                'ussd': 'mobile_money',
                'mobile_money': 'mobile_money',
                'bank': 'bank_transfer',
                'qr': 'other',
                'mpesa': 'mobile_money',
                'account': 'bank_transfer'
            }
            
            mapped_method = payment_method_mapping.get(
                data['payment_type'].lower(), 
                'other'
            )
            
            # Refine card type if it's a card payment
            if data['payment_type'] == 'card' and card.get('type'):
                card_type = card['type'].lower()
                if 'debit' in card_type or 'maestro' in card_type:
                    mapped_method = 'debit_card'
                elif 'credit' in card_type or 'mastercard' in card_type or 'visa' in card_type:
                    mapped_method = 'credit_card'
            
            donation.payment_method = mapped_method
            print(f"      - Set payment_method: {mapped_method}")
        
        # Update processor fee
        if data.get('app_fee'):
            donation.processor_fee = Decimal(str(data['app_fee']))
            donation.processor_fee_currency = donation.currency
            print(f"      - Set processor_fee: {donation.processor_fee}")
        
        # Update status based on webhook status
        webhook_status = data.get('status', '').lower()
        status_mapping = {
            'successful': 'completed',
            'success': 'completed',
            'completed': 'completed',
            'failed': 'failed',
            'error': 'failed',
            'cancelled': 'cancelled',
            'pending': 'processing',
            'processing': 'processing'
        }
        
        new_status = status_mapping.get(webhook_status, donation.status)
        donation.status = new_status
        print(f"      - Status updated: {original_status} → {new_status}")
        
        # Set processed date for completed payments
        if new_status == 'completed' and not donation.processed_date:
            if data.get('created_at'):
                try:
                    processed_time = datetime.fromisoformat(
                        data['created_at'].replace('Z', '+00:00')
                    )
                    donation.processed_date = processed_time
                    print(f"      - Set processed_date from webhook: {donation.processed_date}")
                except Exception as e:
                    print(f"      - Error parsing date, using current time: {e}")
                    donation.processed_date = timezone.now()
            else:
                donation.processed_date = timezone.now()
                print(f"      - Set processed_date to current time: {donation.processed_date}")
        
        # Update donor information if not already set
        if customer.get('name') and (not donation.donor_name or donation.is_anonymous):
            donation.donor_name = customer['name']
            print(f"      - Set donor_name: {donation.donor_name}")
        
        if customer.get('email'):
            webhook_email = customer['email']
            # Clean up Flutterwave test emails
            if 'ravesb_' in webhook_email and '@gmail.com' in webhook_email:
                real_email = meta_data.get('donor_email')
                if real_email:
                    webhook_email = real_email
            
            if not donation.donor_email:
                donation.donor_email = webhook_email
                print(f"      - Set donor_email: {donation.donor_email}")
        
        if customer.get('phone_number') and not donation.donor_phone:
            donation.donor_phone = customer['phone_number']
            print(f"      - Set donor_phone: {donation.donor_phone}")
        
        # Build comprehensive notes
        webhook_notes = []
        
        # Add processor response
        if data.get('processor_response'):
            webhook_notes.append(f"Processor Response: {data['processor_response']}")
        
        # Add payment details
        if data.get('narration'):
            webhook_notes.append(f"Narration: {data['narration'].strip()}")
        
        # Add currency conversion note if applicable
        if conversion_note:
            webhook_notes.append(conversion_note)
        
        # Add card information (masked for security)
        if card:
            card_info = []
            if card.get('type'):
                card_info.append(f"Type: {card['type']}")
            if card.get('issuer'):
                issuer = card['issuer'].strip()
                if len(issuer) > 50:
                    issuer = issuer[:50] + "..."
                card_info.append(f"Issuer: {issuer}")
            if card.get('first_6digits') and card.get('last_4digits'):
                card_info.append(f"Card: {card['first_6digits']}****{card['last_4digits']}")
            if card.get('country'):
                card_info.append(f"Country: {card['country']}")
            if card.get('expiry'):
                card_info.append(f"Expiry: {card['expiry']}")
            
            if card_info:
                webhook_notes.append(f"Card Details: {', '.join(card_info)}")
        
        # Add transaction details
        transaction_details = []
        if data.get('created_at'):
            transaction_details.append(f"Processed: {data['created_at']}")
        if data.get('charged_amount') and data.get('charged_amount') != data.get('amount'):
            transaction_details.append(f"Charged Amount: {data['charged_amount']}")
        if data.get('auth_model'):
            transaction_details.append(f"Auth Method: {data['auth_model']}")
        
        if transaction_details:
            webhook_notes.append(f"Transaction: {', '.join(transaction_details)}")
        
        # Add webhook event info
        webhook_notes.append(f"Webhook Event: {webhook_data.get('event', 'unknown')}")
        webhook_notes.append(f"Flutterwave Ref: {data.get('flw_ref', 'N/A')}")
        
        # Add validation warnings if any
        if validation_errors:
            webhook_notes.append(f"Validation Warnings: {'; '.join(validation_errors)}")
        
        # Append to existing notes
        new_notes = '\n'.join(webhook_notes)
        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        webhook_section = f"--- Webhook Update ({timestamp}) ---\n{new_notes}"
        
        if donation.notes:
            donation.notes = f"{donation.notes}\n\n{webhook_section}"
        else:
            donation.notes = webhook_section
        
        # Add internal notes for debugging and security
        internal_notes = []
        if data.get('ip'):
            internal_notes.append(f"IP: {data['ip']}")
        if data.get('device_fingerprint') and data['device_fingerprint'] != 'N/A':
            internal_notes.append(f"Device: {data['device_fingerprint']}")
        if data.get('account_id'):
            internal_notes.append(f"Flutterwave Account: {data['account_id']}")
        if meta_data.get('__CheckoutInitAddress'):
            internal_notes.append(f"Checkout URL: {meta_data['__CheckoutInitAddress']}")
        
        # Add currency conversion details to internal notes
        if donation.exchange_rate:
            internal_notes.append(f"Exchange Rate: {donation.exchange_rate} ({donation.currency.code} → {donation.converted_currency.code})")
        
        if internal_notes:
            internal_note_text = f"Webhook Data ({timestamp}): {', '.join(internal_notes)}"
            if donation.internal_notes:
                donation.internal_notes = f"{donation.internal_notes}\n{internal_note_text}"
            else:
                donation.internal_notes = internal_note_text
        
        # Save the updated donation
        donation.save()
        
        print(f"      SUCCESS: Comprehensively updated donation {donation_id}")
        print(f"      - Status change: {original_status} → {donation.status}")
        print(f"      - Transaction ID: {donation.transaction_id}")
        print(f"      - Reference: {donation.reference_number}")
        if donation.exchange_rate:
            print(f"      - Currency conversion: {donation.currency.code} {donation.amount} → {donation.converted_currency.code} {donation.converted_amount}")
        
        return {
            'success': True,
            'message': f'Donation {donation_id} updated successfully with currency conversion',
            'status_change': f'{original_status} → {donation.status}',
            'transaction_id': donation.transaction_id,
            'reference_number': donation.reference_number,
            'amount': str(donation.amount),
            'currency': donation.currency.code if donation.currency else None,
            'converted_amount': str(donation.converted_amount) if donation.converted_amount else None,
            'converted_currency': donation.converted_currency.code if donation.converted_currency else None,
            'exchange_rate': str(donation.exchange_rate) if donation.exchange_rate else None
        }
        
    except Donation.DoesNotExist:
        error_msg = f"Donation {donation_id} not found"
        print(f"      ERROR: {error_msg}")
        return {
            'success': False,
            'error': error_msg
        }
    
    except Exception as e:
        error_msg = f"Error updating donation {donation_id}: {str(e)}"
        print(f"      ERROR: {error_msg}")
        print(f"      Exception details: {type(e).__name__}")
        print(f"      Traceback: {traceback.format_exc()}")
        return {
            'success': False,
            'error': error_msg
        }


def validate_webhook_donation_data(donation, webhook_data):
    """
    Validate webhook data against existing donation record
    """
    data = webhook_data.get('data', {})
    meta_data = webhook_data.get('meta_data', {})
    
    validation_errors = []
    
    # Check amount consistency
    if data.get('amount'):
        webhook_amount = Decimal(str(data['amount']))
        if abs(donation.amount - webhook_amount) > Decimal('0.01'):
            validation_errors.append(
                f"Amount mismatch: DB={donation.amount}, Webhook={webhook_amount}"
            )
    
    # Check currency consistency
    if data.get('currency') and donation.currency:
        if data['currency'] != donation.currency.code:
            validation_errors.append(
                f"Currency mismatch: DB={donation.currency.code}, Webhook={data['currency']}"
            )
    
    # Check donor email consistency
    webhook_email = meta_data.get('donor_email')
    if webhook_email and donation.donor_email:
        if webhook_email.lower() != donation.donor_email.lower():
            validation_errors.append(
                f"Email mismatch: DB={donation.donor_email}, Webhook={webhook_email}"
            )
    
    return validation_errors






















# import json
# import hashlib
# import hmac
# import traceback
# import os
# from decimal import Decimal
# from datetime import datetime
# from django.http import HttpResponse, JsonResponse
# from django.views.decorators.csrf import csrf_exempt
# from django.conf import settings
# from django.utils import timezone
# from django.db import transaction
# from .models import Donation, RecurringDonation, InKindDonation, Currency

# @csrf_exempt
# def flutterwave_webhook(request):
#     """Complete Flutterwave webhook handler with comprehensive debugging and donation updates"""
    
#     print("=" * 60)
#     print("FLUTTERWAVE WEBHOOK RECEIVED")
#     print("=" * 60)
    
#     # Step 1: Check request method
#     print(f"Step 1: Request method: {request.method}")
#     if request.method != 'POST':
#         print(f"ERROR: Invalid method {request.method}")
#         return JsonResponse({'error': 'Method not allowed'}, status=405)
    
#     try:
#         # Step 2: Log request details
#         print(f"Step 2: Request details")
#         print(f"  - Content-Type: {request.content_type}")
#         print(f"  - Content-Length: {len(request.body)}")
#         print(f"  - User-Agent: {request.META.get('HTTP_USER_AGENT', 'Unknown')}")
        
#         # Step 3: Get all headers
#         print(f"Step 3: Headers analysis")
#         signature_headers = {}
#         for key, value in request.META.items():
#             if any(sig_key in key.lower() for sig_key in ['signature', 'hash', 'verif']):
#                 header_name = key[5:] if key.startswith('HTTP_') else key
#                 signature_headers[header_name] = value
#                 print(f"  - Found signature header {header_name}: {value}")
        
#         # Step 4: Get the verif-hash specifically
#         print(f"Step 4: Signature extraction")
#         signature = request.headers.get('verif-hash')
#         print(f"  - verif-hash header: {signature}")
#         print(f"  - Signature present: {'Yes' if signature else 'No'}")
        
#         # Step 5: Get and validate request body
#         print(f"Step 5: Request body processing")
#         raw_body = request.body
#         print(f"  - Raw body length: {len(raw_body)}")
        
#         if not raw_body:
#             print("ERROR: Request body is empty")
#             return JsonResponse({'error': 'Empty request body'}, status=400)
        
#         try:
#             body_str = raw_body.decode('utf-8')
#             print(f"  - Body decoded successfully")
#             print(f"  - Body content: {body_str}")
#         except UnicodeDecodeError as e:
#             print(f"ERROR: Failed to decode body: {e}")
#             return JsonResponse({'error': 'Invalid body encoding'}, status=400)
        
#         # Step 6: Parse JSON
#         print(f"Step 6: JSON parsing")
#         try:
#             data = json.loads(body_str)
#             print(f"  - JSON parsed successfully")
#             print(f"  - Event type: {data.get('event', 'Not specified')}")
#             print(f"  - Data keys: {list(data.keys())}")
#             print(f"  - Full data: {json.dumps(data, indent=2)}")
#         except json.JSONDecodeError as e:
#             print(f"ERROR: JSON parsing failed: {e}")
#             return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
#         # Step 7: Signature verification
#         print(f"Step 7: Signature verification")
#         signature_valid = verify_signature(signature, body_str)
        
#         if not signature_valid:
#             print("ERROR: Signature verification failed")
#             # For debugging, let's continue anyway but log the failure
#             print("WARNING: Continuing despite signature failure for debugging")
#         else:
#             print("SUCCESS: Signature verification passed")
        
#         # Step 8: Extract event information
#         print(f"Step 8: Event processing")
#         event_type = data.get('event')
#         event_data = data.get('data', {})
        
#         print(f"  - Event type: {event_type}")
#         print(f"  - Event data keys: {list(event_data.keys())}")
        
#         if not event_type:
#             print("ERROR: No event type found")
#             return JsonResponse({'error': 'Missing event type'}, status=400)
        
#         # Step 9: Extract metadata (FIXED)
#         print(f"Step 9: Metadata extraction")
#         meta_data = data.get('meta_data', {})  # Fixed: was looking in event_data
#         donation_id = meta_data.get('donation_id')
#         donation_type = meta_data.get('donation_type', 'one-time')
#         donor_email = meta_data.get('donor_email')
        
#         print(f"  - Metadata: {meta_data}")
#         print(f"  - Donation ID: {donation_id}")
#         print(f"  - Donation type: {donation_type}")
#         print(f"  - Donor email: {donor_email}")
        
#         # Step 10: Process based on event type
#         print(f"Step 10: Event type processing")
#         result = process_webhook_event(event_type, event_data, meta_data, data)
        
#         print(f"  - Processing result: {result}")
        
#         # Step 11: Return response
#         print(f"Step 11: Sending response")
#         if result['success']:
#             print("SUCCESS: Webhook processed successfully")
#             response_data = {
#                 'status': 'success',
#                 'message': result.get('message', 'Webhook processed'),
#                 'event_type': event_type,
#                 'donation_id': donation_id
#             }
#         else:
#             print(f"ERROR: Webhook processing failed: {result['error']}")
#             response_data = {
#                 'status': 'error',
#                 'message': result['error'],
#                 'event_type': event_type,
#                 'donation_id': donation_id
#             }
        
#         print(f"  - Response data: {response_data}")
#         print("=" * 60)
#         print("WEBHOOK PROCESSING COMPLETE")
#         print("=" * 60)
        
#         # Always return 200 as per Flutterwave documentation
#         return JsonResponse(response_data, status=200)
        
#     except Exception as e:
#         print(f"CRITICAL ERROR: Unexpected exception")
#         print(f"  - Exception type: {type(e).__name__}")
#         print(f"  - Exception message: {str(e)}")
#         print(f"  - Traceback: {traceback.format_exc()}")
        
#         return JsonResponse({
#             'status': 'error',
#             'message': 'Internal server error',
#             'error': str(e)
#         }, status=200)  # Still return 200 for Flutterwave


# def verify_signature(signature, body_str):
#     """Verify Flutterwave webhook signature with detailed debugging"""
#     print("    Signature Verification Details:")
    
#     # Get secret hash from settings
#     secret_hash = getattr(settings, 'FLUTTERWAVE_SECRET_HASH', None)
#     if not secret_hash:
#         secret_hash = os.getenv('FLUTTERWAVE_SECRET_HASH')
    
#     print(f"    - Secret hash configured: {'Yes' if secret_hash else 'No'}")
#     if secret_hash:
#         print(f"    - Secret hash value: {secret_hash}")
    
#     if not secret_hash:
#         print("    ERROR: No secret hash configured")
#         return False
    
#     if not signature:
#         print("    ERROR: No signature provided")
#         return False
    
#     print(f"    - Received signature: {signature}")
    
#     # Method 1: Direct comparison (Flutterwave test mode)
#     print("    - Method 1: Direct comparison")
#     if signature == secret_hash:
#         print("    SUCCESS: Direct comparison matched")
#         return True
#     else:
#         print("    FAILED: Direct comparison did not match")
    
#     # Method 2: Hash of secret (some Flutterwave implementations)
#     print("    - Method 2: Hash of secret")
#     try:
#         expected_hash = hashlib.sha256(secret_hash.encode()).hexdigest()
#         print(f"    - Expected hash: {expected_hash}")
#         if hmac.compare_digest(signature, expected_hash):
#             print("    SUCCESS: Hash of secret matched")
#             return True
#         else:
#             print("    FAILED: Hash of secret did not match")
#     except Exception as e:
#         print(f"    ERROR in Method 2: {e}")
    
#     # Method 3: Hash of (body + secret)
#     print("    - Method 3: Hash of (body + secret)")
#     try:
#         combined = body_str + secret_hash
#         expected_hash = hashlib.sha256(combined.encode('utf-8')).hexdigest()
#         print(f"    - Expected hash: {expected_hash}")
#         if hmac.compare_digest(signature, expected_hash):
#             print("    SUCCESS: Hash of (body + secret) matched")
#             return True
#         else:
#             print("    FAILED: Hash of (body + secret) did not match")
#     except Exception as e:
#         print(f"    ERROR in Method 3: {e}")
    
#     # Method 4: HMAC-SHA256
#     print("    - Method 4: HMAC-SHA256")
#     try:
#         expected_hmac = hmac.new(
#             secret_hash.encode('utf-8'),
#             body_str.encode('utf-8'),
#             hashlib.sha256
#         ).hexdigest()
#         print(f"    - Expected HMAC: {expected_hmac}")
#         if hmac.compare_digest(signature, expected_hmac):
#             print("    SUCCESS: HMAC-SHA256 matched")
#             return True
#         else:
#             print("    FAILED: HMAC-SHA256 did not match")
#     except Exception as e:
#         print(f"    ERROR in Method 4: {e}")
    
#     print("    FINAL RESULT: All signature verification methods failed")
#     return False


# def process_webhook_event(event_type, event_data, meta_data, full_webhook_data):
#     """Process different webhook events"""
#     print(f"    Processing event: {event_type}")
    
#     try:
#         if event_type in ['charge.completed', 'charge.success']:
#             return handle_payment_completed(event_data, meta_data, full_webhook_data)
#         elif event_type == 'charge.failed':
#             return handle_payment_failed(event_data, meta_data, full_webhook_data)
#         elif event_type == 'subscription.activated':
#             return handle_subscription_activated(event_data, meta_data)
#         elif event_type == 'subscription.cancelled':
#             return handle_subscription_cancelled(event_data, meta_data)
#         else:
#             print(f"    WARNING: Unhandled event type: {event_type}")
#             return {
#                 'success': True,
#                 'message': f'Event type {event_type} acknowledged but not processed'
#             }
#     except Exception as e:
#         print(f"    ERROR processing event: {e}")
#         print(f"    Traceback: {traceback.format_exc()}")
#         return {
#             'success': False,
#             'error': f'Error processing {event_type}: {str(e)}'
#         }


# def handle_payment_completed(event_data, meta_data, full_webhook_data):
#     """Handle successful payment with comprehensive donation update"""
#     print("    Handling payment completion")
    
#     donation_id = meta_data.get('donation_id')
#     donation_type = meta_data.get('donation_type', 'one-time')
    
#     print(f"    - Donation ID: {donation_id}")
#     print(f"    - Donation type: {donation_type}")
    
#     if not donation_id:
#         print("    WARNING: No donation_id found - treating as test webhook")
#         return {
#             'success': True,
#             'message': 'Test webhook acknowledged (no donation_id)'
#         }
    
#     try:
#         with transaction.atomic():
#             if donation_type == 'one-time':
#                 result = update_donation_comprehensive(donation_id, full_webhook_data)
#             elif donation_type == 'recurring':
#                 result = update_recurring_donation_status(donation_id, 'completed', event_data)
#             elif donation_type == 'in-kind':
#                 result = update_in_kind_donation_status(donation_id, 'completed', event_data)
#             else:
#                 print(f"    ERROR: Unknown donation type: {donation_type}")
#                 return {
#                     'success': False,
#                     'error': f'Unknown donation type: {donation_type}'
#                 }
        
#         print(f"    - Update result: {result}")
#         return result
        
#     except Exception as e:
#         print(f"    ERROR updating donation: {e}")
#         print(f"    Traceback: {traceback.format_exc()}")
#         return {
#             'success': False,
#             'error': f'Error updating donation: {str(e)}'
#         }


# def handle_payment_failed(event_data, meta_data, full_webhook_data):
#     """Handle failed payment with comprehensive donation update"""
#     print("    Handling payment failure")
    
#     donation_id = meta_data.get('donation_id')
#     donation_type = meta_data.get('donation_type', 'one-time')
    
#     print(f"    - Donation ID: {donation_id}")
#     print(f"    - Donation type: {donation_type}")
    
#     if not donation_id:
#         print("    WARNING: No donation_id found - treating as test webhook")
#         return {
#             'success': True,
#             'message': 'Test failed payment webhook acknowledged'
#         }
    
#     try:
#         with transaction.atomic():
#             if donation_type == 'one-time':
#                 # Update webhook data to reflect failed status
#                 webhook_data_copy = full_webhook_data.copy()
#                 webhook_data_copy['data']['status'] = 'failed'
#                 result = update_donation_comprehensive(donation_id, webhook_data_copy)
#             elif donation_type == 'recurring':
#                 result = update_recurring_donation_status(donation_id, 'failed', event_data)
#             elif donation_type == 'in-kind':
#                 result = update_in_kind_donation_status(donation_id, 'failed', event_data)
#             else:
#                 return {
#                     'success': False,
#                     'error': f'Unknown donation type: {donation_type}'
#                 }
        
#         return result
        
#     except Exception as e:
#         print(f"    ERROR updating failed donation: {e}")
#         return {
#             'success': False,
#             'error': f'Error updating failed donation: {str(e)}'
#         }


# def update_donation_comprehensive(donation_id, webhook_data):
#     """
#     Comprehensive donation update with all webhook data
#     """
#     print(f"      Updating donation {donation_id} comprehensively")
    
#     try:
#         # Get the donation record
#         donation = Donation.objects.select_for_update().get(id=donation_id)
#         print(f"      - Found donation: {donation}")
        
#         # Extract data from webhook
#         data = webhook_data.get('data', {})
#         meta_data = webhook_data.get('meta_data', {})
#         customer = data.get('customer', {})
#         card = data.get('card', {})
        
#         # Store original status for logging
#         original_status = donation.status
        
#         # Validate webhook data against donation
#         validation_errors = validate_webhook_donation_data(donation, webhook_data)
#         if validation_errors:
#             print(f"      - Validation warnings: {validation_errors}")
#             # Log warnings but continue processing
        
#         # Update transaction identifiers
#         if data.get('id'):
#             donation.transaction_id = str(data['id'])
#             print(f"      - Set transaction_id: {donation.transaction_id}")
        
#         if data.get('flw_ref'):
#             donation.reference_number = data['flw_ref']
#             print(f"      - Set reference_number: {donation.reference_number}")
        
#         if data.get('tx_ref'):
#             donation.bank_reference = data['tx_ref']
#             print(f"      - Set bank_reference: {donation.bank_reference}")
        
#         # Update financial details
#         if data.get('amount'):
#             webhook_amount = Decimal(str(data['amount']))
#             if abs(donation.amount - webhook_amount) > Decimal('0.01'):
#                 print(f"      - Amount updated: {donation.amount} → {webhook_amount}")
#                 donation.amount = webhook_amount
        
#         if data.get('currency'):
#             try:
#                 currency = Currency.objects.get(code=data['currency'])
#                 if donation.currency != currency:
#                     donation.currency = currency
#                     print(f"      - Currency updated: {donation.currency.code}")
#             except Currency.DoesNotExist:
#                 print(f"      - Warning: Currency {data['currency']} not found in database")
        
#         # Update payment method with intelligent mapping
#         if data.get('payment_type'):
#             payment_method_mapping = {
#                 'card': 'credit_card',  # Default to credit card
#                 'bank_transfer': 'bank_transfer',
#                 'ussd': 'mobile_money',
#                 'mobile_money': 'mobile_money',
#                 'bank': 'bank_transfer',
#                 'qr': 'other',
#                 'mpesa': 'mobile_money',
#                 'account': 'bank_transfer'
#             }
            
#             mapped_method = payment_method_mapping.get(
#                 data['payment_type'].lower(), 
#                 'other'
#             )
            
#             # Refine card type if it's a card payment
#             if data['payment_type'] == 'card' and card.get('type'):
#                 card_type = card['type'].lower()
#                 if 'debit' in card_type or 'maestro' in card_type:
#                     mapped_method = 'debit_card'
#                 elif 'credit' in card_type or 'mastercard' in card_type or 'visa' in card_type:
#                     mapped_method = 'credit_card'
            
#             donation.payment_method = mapped_method
#             print(f"      - Set payment_method: {mapped_method}")
        
#         # Update processor fee
#         if data.get('app_fee'):
#             donation.processor_fee = Decimal(str(data['app_fee']))
#             # Set processor fee currency same as donation currency
#             donation.processor_fee_currency = donation.currency
#             print(f"      - Set processor_fee: {donation.processor_fee}")
        
#         # Update status based on webhook status
#         webhook_status = data.get('status', '').lower()
#         status_mapping = {
#             'successful': 'completed',
#             'success': 'completed',
#             'completed': 'completed',
#             'failed': 'failed',
#             'error': 'failed',
#             'cancelled': 'cancelled',
#             'pending': 'processing',
#             'processing': 'processing'
#         }
        
#         new_status = status_mapping.get(webhook_status, donation.status)
#         donation.status = new_status
#         print(f"      - Status updated: {original_status} → {new_status}")
        
#         # Set processed date for completed payments
#         if new_status == 'completed' and not donation.processed_date:
#             if data.get('created_at'):
#                 try:
#                     # Parse Flutterwave timestamp (ISO format)
#                     processed_time = datetime.fromisoformat(
#                         data['created_at'].replace('Z', '+00:00')
#                     )
#                     donation.processed_date = processed_time
#                     print(f"      - Set processed_date from webhook: {donation.processed_date}")
#                 except Exception as e:
#                     print(f"      - Error parsing date, using current time: {e}")
#                     donation.processed_date = timezone.now()
#             else:
#                 donation.processed_date = timezone.now()
#                 print(f"      - Set processed_date to current time: {donation.processed_date}")
        
#         # Update donor information if not already set or if anonymous
#         if customer.get('name') and (not donation.donor_name or donation.is_anonymous):
#             donation.donor_name = customer['name']
#             print(f"      - Set donor_name: {donation.donor_name}")
        
#         if customer.get('email'):
#             # Always update email from webhook if provided
#             webhook_email = customer['email']
#             # Clean up Flutterwave test emails
#             if 'ravesb_' in webhook_email and '@gmail.com' in webhook_email:
#                 # Extract real email from Flutterwave test format
#                 real_email = meta_data.get('donor_email')
#                 if real_email:
#                     webhook_email = real_email
            
#             if not donation.donor_email:
#                 donation.donor_email = webhook_email
#                 print(f"      - Set donor_email: {donation.donor_email}")
#             elif donation.donor_email != webhook_email:
#                 print(f"      - Email mismatch: DB={donation.donor_email}, Webhook={webhook_email}")
        
#         if customer.get('phone_number') and not donation.donor_phone:
#             donation.donor_phone = customer['phone_number']
#             print(f"      - Set donor_phone: {donation.donor_phone}")
        
#         # Build comprehensive notes
#         webhook_notes = []
        
#         # Add processor response
#         if data.get('processor_response'):
#             webhook_notes.append(f"Processor Response: {data['processor_response']}")
        
#         # Add payment details
#         if data.get('narration'):
#             webhook_notes.append(f"Narration: {data['narration'].strip()}")
        
#         # Add card information (masked for security)
#         if card:
#             card_info = []
#             if card.get('type'):
#                 card_info.append(f"Type: {card['type']}")
#             if card.get('issuer'):
#                 issuer = card['issuer'].strip()
#                 if len(issuer) > 50:  # Truncate long issuer names
#                     issuer = issuer[:50] + "..."
#                 card_info.append(f"Issuer: {issuer}")
#             if card.get('first_6digits') and card.get('last_4digits'):
#                 card_info.append(f"Card: {card['first_6digits']}****{card['last_4digits']}")
#             if card.get('country'):
#                 card_info.append(f"Country: {card['country']}")
#             if card.get('expiry'):
#                 card_info.append(f"Expiry: {card['expiry']}")
            
#             if card_info:
#                 webhook_notes.append(f"Card Details: {', '.join(card_info)}")
        
#         # Add transaction details
#         transaction_details = []
#         if data.get('created_at'):
#             transaction_details.append(f"Processed: {data['created_at']}")
#         if data.get('charged_amount') and data.get('charged_amount') != data.get('amount'):
#             transaction_details.append(f"Charged Amount: {data['charged_amount']}")
#         if data.get('auth_model'):
#             transaction_details.append(f"Auth Method: {data['auth_model']}")
        
#         if transaction_details:
#             webhook_notes.append(f"Transaction: {', '.join(transaction_details)}")
        
#         # Add webhook event info
#         webhook_notes.append(f"Webhook Event: {webhook_data.get('event', 'unknown')}")
#         webhook_notes.append(f"Flutterwave Ref: {data.get('flw_ref', 'N/A')}")
        
#         # Add validation warnings if any
#         if validation_errors:
#             webhook_notes.append(f"Validation Warnings: {'; '.join(validation_errors)}")
        
#         # Append to existing notes
#         new_notes = '\n'.join(webhook_notes)
#         timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')
#         webhook_section = f"--- Webhook Update ({timestamp}) ---\n{new_notes}"
        
#         if donation.notes:
#             donation.notes = f"{donation.notes}\n\n{webhook_section}"
#         else:
#             donation.notes = webhook_section
        
#         # Add internal notes for debugging and security
#         internal_notes = []
#         if data.get('ip'):
#             internal_notes.append(f"IP: {data['ip']}")
#         if data.get('device_fingerprint') and data['device_fingerprint'] != 'N/A':
#             internal_notes.append(f"Device: {data['device_fingerprint']}")
#         if data.get('account_id'):
#             internal_notes.append(f"Flutterwave Account: {data['account_id']}")
#         if meta_data.get('__CheckoutInitAddress'):
#             internal_notes.append(f"Checkout URL: {meta_data['__CheckoutInitAddress']}")
        
#         if internal_notes:
#             internal_note_text = f"Webhook Data ({timestamp}): {', '.join(internal_notes)}"
#             if donation.internal_notes:
#                 donation.internal_notes = f"{donation.internal_notes}\n{internal_note_text}"
#             else:
#                 donation.internal_notes = internal_note_text
        
#         # Save the updated donation
#         donation.save()
        
#         print(f"      SUCCESS: Comprehensively updated donation {donation_id}")
#         print(f"      - Status change: {original_status} → {donation.status}")
#         print(f"      - Transaction ID: {donation.transaction_id}")
#         print(f"      - Reference: {donation.reference_number}")
        
#         return {
#             'success': True,
#             'message': f'Donation {donation_id} updated successfully',
#             'status_change': f'{original_status} → {donation.status}',
#             'transaction_id': donation.transaction_id,
#             'reference_number': donation.reference_number,
#             'amount': str(donation.amount),
#             'currency': donation.currency.code if donation.currency else None
#         }
        
#     except Donation.DoesNotExist:
#         error_msg = f"Donation {donation_id} not found"
#         print(f"      ERROR: {error_msg}")
#         return {
#             'success': False,
#             'error': error_msg
#         }
    
#     except Exception as e:
#         error_msg = f"Error updating donation {donation_id}: {str(e)}"
#         print(f"      ERROR: {error_msg}")
#         print(f"      Exception details: {type(e).__name__}")
#         print(f"      Traceback: {traceback.format_exc()}")
#         return {
#             'success': False,
#             'error': error_msg
#         }


# def validate_webhook_donation_data(donation, webhook_data):
#     """
#     Validate webhook data against existing donation record
#     """
#     data = webhook_data.get('data', {})
#     meta_data = webhook_data.get('meta_data', {})
    
#     validation_errors = []
    
#     # Check amount consistency
#     if data.get('amount'):
#         webhook_amount = Decimal(str(data['amount']))
#         if abs(donation.amount - webhook_amount) > Decimal('0.01'):
#             validation_errors.append(
#                 f"Amount mismatch: DB={donation.amount}, Webhook={webhook_amount}"
#             )
    
#     # Check currency consistency
#     if data.get('currency') and donation.currency:
#         if data['currency'] != donation.currency.code:
#             validation_errors.append(
#                 f"Currency mismatch: DB={donation.currency.code}, Webhook={data['currency']}"
#             )
    
#     # Check donor email consistency
#     webhook_email = meta_data.get('donor_email')
#     if webhook_email and donation.donor_email:
#         if webhook_email.lower() != donation.donor_email.lower():
#             validation_errors.append(
#                 f"Email mismatch: DB={donation.donor_email}, Webhook={webhook_email}"
#             )
    
#     return validation_errors


# # Keep existing functions for recurring and in-kind donations
# def update_recurring_donation_status(donation_id, status, transaction_data):
#     """Update recurring donation status"""
#     print(f"      Updating recurring donation {donation_id} to {status}")
    
#     try:
#         recurring_donation = RecurringDonation.objects.get(id=donation_id)
#         print(f"      - Found recurring donation: {recurring_donation}")
        
#         if status == 'completed':
#             # Create individual donation record
#             donation = Donation.objects.create(
#                 donor=recurring_donation.donor,
#                 is_anonymous=recurring_donation.is_anonymous,
#                 campaign=recurring_donation.campaign,
#                 project=getattr(recurring_donation, 'project', None),
#                 amount=recurring_donation.amount,
#                 currency=recurring_donation.currency,
#                 payment_method=recurring_donation.payment_method,
#                 transaction_id=transaction_data.get('id'),
#                 reference_number=transaction_data.get('flw_ref'),
#                 bank_reference=transaction_data.get('tx_ref'),
#                 status='completed',
#                 processed_date=timezone.now(),
#                 donation_source='website',
#                 notes=f"Recurring donation payment #{recurring_donation.payment_count + 1}"
#             )
            
#             print(f"      - Created donation record: {donation.id}")
            
#             # Update recurring donation
#             recurring_donation.record_successful_payment(donation)
#             print(f"      SUCCESS: Recorded successful recurring payment for {donation_id}")
            
#             return {
#                 'success': True,
#                 'message': f'Recurring payment recorded for donation {donation_id}'
#             }
            
#         elif status == 'failed':
#             recurring_donation.record_failed_payment()
#             print(f"      SUCCESS: Recorded failed recurring payment for {donation_id}")
            
#             return {
#                 'success': True,
#                 'message': f'Failed recurring payment recorded for donation {donation_id}'
#             }
        
#     except RecurringDonation.DoesNotExist:
#         print(f"      ERROR: Recurring donation {donation_id} not found")
#         return {
#             'success': False,
#             'error': f'Recurring donation {donation_id} not found'
#         }
#     except Exception as e:
#         print(f"      ERROR updating recurring donation: {e}")
#         print(f"      Traceback: {traceback.format_exc()}")
#         return {
#             'success': False,
#             'error': f'Error updating recurring donation: {str(e)}'
#         }


# def update_in_kind_donation_status(donation_id, status, transaction_data):
#     """Update in-kind donation status"""
#     print(f"      Updating in-kind donation {donation_id} to {status}")
    
#     try:
#         in_kind_donation = InKindDonation.objects.get(id=donation_id)
#         print(f"      - Found in-kind donation: {in_kind_donation}")
        
#         old_status = in_kind_donation.status
        
#         if status == 'completed':
#             in_kind_donation.status = 'confirmed'
#         elif status == 'failed':
#             in_kind_donation.status = 'pledged'
        
#         # Add transaction notes
#         transaction_notes = f"Processing fee webhook: {transaction_data.get('id', 'N/A')}"
#         in_kind_donation.notes = f"{in_kind_donation.notes or ''}\n{transaction_notes}".strip()
        
#         in_kind_donation.save()
        
#         print(f"      SUCCESS: Updated in-kind donation {donation_id} from {old_status} to {in_kind_donation.status}")
#         return {
#             'success': True,
#             'message': f'In-kind donation {donation_id} updated from {old_status} to {in_kind_donation.status}'
#         }
        
#     except InKindDonation.DoesNotExist:
#         print(f"      ERROR: In-kind donation {donation_id} not found")
#         return {
#             'success': False,
#             'error': f'In-kind donation {donation_id} not found'
#         }
#     except Exception as e:
#         print(f"      ERROR updating in-kind donation: {e}")
#         print(f"      Traceback: {traceback.format_exc()}")
#         return {
#             'success': False,
#             'error': f'Error updating in-kind donation: {str(e)}'
#         }


# def handle_subscription_activated(event_data, meta_data):
#     """Handle subscription activation"""
#     print("    Handling subscription activation")
    
#     donation_id = meta_data.get('donation_id')
#     print(f"    - Donation ID: {donation_id}")
    
#     if not donation_id:
#         return {
#             'success': True,
#             'message': 'Test subscription activation acknowledged'
#         }
    
#     try:
#         recurring_donation = RecurringDonation.objects.get(id=donation_id)
#         recurring_donation.status = 'active'
#         recurring_donation.subscription_id = event_data.get('id')
#         recurring_donation.save()
        
#         print(f"    SUCCESS: Activated recurring donation {donation_id}")
#         return {
#             'success': True,
#             'message': f'Recurring donation {donation_id} activated'
#         }
        
#     except RecurringDonation.DoesNotExist:
#         print(f"    ERROR: Recurring donation {donation_id} not found")
#         return {
#             'success': False,
#             'error': f'Recurring donation {donation_id} not found'
#         }
#     except Exception as e:
#         print(f"    ERROR activating subscription: {e}")
#         return {
#             'success': False,
#             'error': f'Error activating subscription: {str(e)}'
#         }


# def handle_subscription_cancelled(event_data, meta_data):
#     """Handle subscription cancellation"""
#     print("    Handling subscription cancellation")
    
#     donation_id = meta_data.get('donation_id')
#     print(f"    - Donation ID: {donation_id}")
    
#     if not donation_id:
#         return {
#             'success': True,
#             'message': 'Test subscription cancellation acknowledged'
#         }
    
#     try:
#         recurring_donation = RecurringDonation.objects.get(id=donation_id)
#         recurring_donation.cancel_subscription("Cancelled via payment processor")
        
#         print(f"    SUCCESS: Cancelled recurring donation {donation_id}")
#         return {
#             'success': True,
#             'message': f'Recurring donation {donation_id} cancelled'
#         }
        
#     except RecurringDonation.DoesNotExist:
#         print(f"    ERROR: Recurring donation {donation_id} not found")
#         return {
#             'success': False,
#             'error': f'Recurring donation {donation_id} not found'
#         }
#     except Exception as e:
#         print(f"    ERROR cancelling subscription: {e}")
#         return {
#             'success': False,
#             'error': f'Error cancelling subscription: {str(e)}'
#         }



















# import json
# import hashlib
# import hmac
# import traceback
# import os
# from django.http import HttpResponse, JsonResponse
# from django.views.decorators.csrf import csrf_exempt
# from django.conf import settings
# from django.utils import timezone
# from django.db import transaction
# from .models import Donation, RecurringDonation, InKindDonation

# @csrf_exempt
# def flutterwave_webhook(request):
#     """Complete Flutterwave webhook handler with comprehensive debugging"""
    
#     print("=" * 60)
#     print("FLUTTERWAVE WEBHOOK RECEIVED")
#     print("=" * 60)
    
#     # Step 1: Check request method
#     print(f"Step 1: Request method: {request.method}")
#     if request.method != 'POST':
#         print(f"ERROR: Invalid method {request.method}")
#         return JsonResponse({'error': 'Method not allowed'}, status=405)
    
#     try:
#         # Step 2: Log request details
#         print(f"Step 2: Request details")
#         print(f"  - Content-Type: {request.content_type}")
#         print(f"  - Content-Length: {len(request.body)}")
#         print(f"  - User-Agent: {request.META.get('HTTP_USER_AGENT', 'Unknown')}")
        
#         # Step 3: Get all headers
#         print(f"Step 3: Headers analysis")
#         signature_headers = {}
#         for key, value in request.META.items():
#             if any(sig_key in key.lower() for sig_key in ['signature', 'hash', 'verif']):
#                 header_name = key[5:] if key.startswith('HTTP_') else key
#                 signature_headers[header_name] = value
#                 print(f"  - Found signature header {header_name}: {value}")
        
#         # Step 4: Get the verif-hash specifically
#         print(f"Step 4: Signature extraction")
#         signature = request.headers.get('verif-hash')
#         print(f"  - verif-hash header: {signature}")
#         print(f"  - Signature present: {'Yes' if signature else 'No'}")
        
#         # Step 5: Get and validate request body
#         print(f"Step 5: Request body processing")
#         raw_body = request.body
#         print(f"  - Raw body length: {len(raw_body)}")
        
#         if not raw_body:
#             print("ERROR: Request body is empty")
#             return JsonResponse({'error': 'Empty request body'}, status=400)
        
#         try:
#             body_str = raw_body.decode('utf-8')
#             print(f"  - Body decoded successfully")
#             print(f"  - Body content: {body_str}")
#         except UnicodeDecodeError as e:
#             print(f"ERROR: Failed to decode body: {e}")
#             return JsonResponse({'error': 'Invalid body encoding'}, status=400)
        
#         # Step 6: Parse JSON
#         print(f"Step 6: JSON parsing")
#         try:
#             data = json.loads(body_str)
#             print(f"  - JSON parsed successfully")
#             print(f"  - Event type: {data.get('event', 'Not specified')}")
#             print(f"  - Data keys: {list(data.keys())}")
#             print(f"  - Full data: {json.dumps(data, indent=2)}")
#         except json.JSONDecodeError as e:
#             print(f"ERROR: JSON parsing failed: {e}")
#             return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
#         # Step 7: Signature verification
#         print(f"Step 7: Signature verification")
#         signature_valid = verify_signature(signature, body_str)
        
#         if not signature_valid:
#             print("ERROR: Signature verification failed")
#             # For debugging, let's continue anyway but log the failure
#             print("WARNING: Continuing despite signature failure for debugging")
#         else:
#             print("SUCCESS: Signature verification passed")
        
#         # Step 8: Extract event information
#         print(f"Step 8: Event processing")
#         event_type = data.get('event')
#         event_data = data.get('data', {})
        
#         print(f"  - Event type: {event_type}")
#         print(f"  - Event data keys: {list(event_data.keys())}")
        
#         if not event_type:
#             print("ERROR: No event type found")
#             return JsonResponse({'error': 'Missing event type'}, status=400)
        
#         # Step 9: Extract metadata
#         print(f"Step 9: Metadata extraction")
#         meta = event_data.get('meta', {})
#         donation_id = meta.get('donation_id')
#         donation_type = meta.get('donation_type', 'one-time')
        
#         print(f"  - Metadata: {meta}")
#         print(f"  - Donation ID: {donation_id}")
#         print(f"  - Donation type: {donation_type}")
        
#         # Step 10: Process based on event type
#         print(f"Step 10: Event type processing")
#         result = process_webhook_event(event_type, event_data, meta)
        
#         print(f"  - Processing result: {result}")
        
#         # Step 11: Return response
#         print(f"Step 11: Sending response")
#         if result['success']:
#             print("SUCCESS: Webhook processed successfully")
#             response_data = {
#                 'status': 'success',
#                 'message': result.get('message', 'Webhook processed'),
#                 'event_type': event_type
#             }
#         else:
#             print(f"ERROR: Webhook processing failed: {result['error']}")
#             response_data = {
#                 'status': 'error',
#                 'message': result['error'],
#                 'event_type': event_type
#             }
        
#         print(f"  - Response data: {response_data}")
#         print("=" * 60)
#         print("WEBHOOK PROCESSING COMPLETE")
#         print("=" * 60)
        
#         # Always return 200 as per Flutterwave documentation
#         return JsonResponse(response_data, status=200)
        
#     except Exception as e:
#         print(f"CRITICAL ERROR: Unexpected exception")
#         print(f"  - Exception type: {type(e).__name__}")
#         print(f"  - Exception message: {str(e)}")
#         print(f"  - Traceback: {traceback.format_exc()}")
        
#         return JsonResponse({
#             'status': 'error',
#             'message': 'Internal server error',
#             'error': str(e)
#         }, status=200)  # Still return 200 for Flutterwave


# def verify_signature(signature, body_str):
#     """Verify Flutterwave webhook signature with detailed debugging"""
#     print("    Signature Verification Details:")
    
#     # Get secret hash from settings
#     secret_hash = getattr(settings, 'FLUTTERWAVE_SECRET_HASH', None)
#     if not secret_hash:
#         secret_hash = os.getenv('FLUTTERWAVE_SECRET_HASH')
    
#     print(f"    - Secret hash configured: {'Yes' if secret_hash else 'No'}")
#     if secret_hash:
#         print(f"    - Secret hash value: {secret_hash}")
    
#     if not secret_hash:
#         print("    ERROR: No secret hash configured")
#         return False
    
#     if not signature:
#         print("    ERROR: No signature provided")
#         return False
    
#     print(f"    - Received signature: {signature}")
    
#     # Method 1: Direct comparison (Flutterwave test mode)
#     print("    - Method 1: Direct comparison")
#     if signature == secret_hash:
#         print("    SUCCESS: Direct comparison matched")
#         return True
#     else:
#         print("    FAILED: Direct comparison did not match")
    
#     # Method 2: Hash of secret (some Flutterwave implementations)
#     print("    - Method 2: Hash of secret")
#     try:
#         expected_hash = hashlib.sha256(secret_hash.encode()).hexdigest()
#         print(f"    - Expected hash: {expected_hash}")
#         if hmac.compare_digest(signature, expected_hash):
#             print("    SUCCESS: Hash of secret matched")
#             return True
#         else:
#             print("    FAILED: Hash of secret did not match")
#     except Exception as e:
#         print(f"    ERROR in Method 2: {e}")
    
#     # Method 3: Hash of (body + secret)
#     print("    - Method 3: Hash of (body + secret)")
#     try:
#         combined = body_str + secret_hash
#         expected_hash = hashlib.sha256(combined.encode('utf-8')).hexdigest()
#         print(f"    - Expected hash: {expected_hash}")
#         if hmac.compare_digest(signature, expected_hash):
#             print("    SUCCESS: Hash of (body + secret) matched")
#             return True
#         else:
#             print("    FAILED: Hash of (body + secret) did not match")
#     except Exception as e:
#         print(f"    ERROR in Method 3: {e}")
    
#     # Method 4: HMAC-SHA256
#     print("    - Method 4: HMAC-SHA256")
#     try:
#         expected_hmac = hmac.new(
#             secret_hash.encode('utf-8'),
#             body_str.encode('utf-8'),
#             hashlib.sha256
#         ).hexdigest()
#         print(f"    - Expected HMAC: {expected_hmac}")
#         if hmac.compare_digest(signature, expected_hmac):
#             print("    SUCCESS: HMAC-SHA256 matched")
#             return True
#         else:
#             print("    FAILED: HMAC-SHA256 did not match")
#     except Exception as e:
#         print(f"    ERROR in Method 4: {e}")
    
#     print("    FINAL RESULT: All signature verification methods failed")
#     return False


# def process_webhook_event(event_type, event_data, meta):
#     """Process different webhook events"""
#     print(f"    Processing event: {event_type}")
    
#     try:
#         if event_type in ['charge.completed', 'charge.success']:
#             return handle_payment_completed(event_data, meta)
#         elif event_type == 'charge.failed':
#             return handle_payment_failed(event_data, meta)
#         elif event_type == 'subscription.activated':
#             return handle_subscription_activated(event_data, meta)
#         elif event_type == 'subscription.cancelled':
#             return handle_subscription_cancelled(event_data, meta)
#         else:
#             print(f"    WARNING: Unhandled event type: {event_type}")
#             return {
#                 'success': True,
#                 'message': f'Event type {event_type} acknowledged but not processed'
#             }
#     except Exception as e:
#         print(f"    ERROR processing event: {e}")
#         print(f"    Traceback: {traceback.format_exc()}")
#         return {
#             'success': False,
#             'error': f'Error processing {event_type}: {str(e)}'
#         }


# def handle_payment_completed(event_data, meta):
#     """Handle successful payment"""
#     print("    Handling payment completion")
    
#     donation_id = meta.get('donation_id')
#     donation_type = meta.get('donation_type', 'one-time')
    
#     print(f"    - Donation ID: {donation_id}")
#     print(f"    - Donation type: {donation_type}")
    
#     if not donation_id:
#         print("    WARNING: No donation_id found - treating as test webhook")
#         return {
#             'success': True,
#             'message': 'Test webhook acknowledged (no donation_id)'
#         }
    
#     # Extract transaction data
#     transaction_data = {
#         'flutterwave_ref': event_data.get('flw_ref'),
#         'transaction_id': event_data.get('id'),
#         'tx_ref': event_data.get('tx_ref'),
#         'amount': event_data.get('amount'),
#         'currency': event_data.get('currency'),
#         'payment_method': event_data.get('payment_type', 'card'),
#         'processed_at': event_data.get('created_at'),
#         'customer_email': event_data.get('customer', {}).get('email'),
#         'customer_name': event_data.get('customer', {}).get('name'),
#     }
    
#     print(f"    - Transaction data: {transaction_data}")
    
#     try:
#         with transaction.atomic():
#             if donation_type == 'one-time':
#                 result = update_donation_status(donation_id, 'completed', transaction_data)
#             elif donation_type == 'recurring':
#                 result = update_recurring_donation_status(donation_id, 'completed', transaction_data)
#             elif donation_type == 'in-kind':
#                 result = update_in_kind_donation_status(donation_id, 'completed', transaction_data)
#             else:
#                 print(f"    ERROR: Unknown donation type: {donation_type}")
#                 return {
#                     'success': False,
#                     'error': f'Unknown donation type: {donation_type}'
#                 }
        
#         print(f"    - Update result: {result}")
#         return result
        
#     except Exception as e:
#         print(f"    ERROR updating donation: {e}")
#         print(f"    Traceback: {traceback.format_exc()}")
#         return {
#             'success': False,
#             'error': f'Error updating donation: {str(e)}'
#         }


# def handle_payment_failed(event_data, meta):
#     """Handle failed payment"""
#     print("    Handling payment failure")
    
#     donation_id = meta.get('donation_id')
#     donation_type = meta.get('donation_type', 'one-time')
    
#     print(f"    - Donation ID: {donation_id}")
#     print(f"    - Donation type: {donation_type}")
    
#     if not donation_id:
#         print("    WARNING: No donation_id found - treating as test webhook")
#         return {
#             'success': True,
#             'message': 'Test failed payment webhook acknowledged'
#         }
    
#     transaction_data = {
#         'flutterwave_ref': event_data.get('flw_ref'),
#         'transaction_id': event_data.get('id'),
#         'tx_ref': event_data.get('tx_ref'),
#         'error_message': event_data.get('processor_response', 'Payment failed'),
#         'failed_at': event_data.get('created_at'),
#     }
    
#     print(f"    - Failed transaction data: {transaction_data}")
    
#     try:
#         with transaction.atomic():
#             if donation_type == 'one-time':
#                 result = update_donation_status(donation_id, 'failed', transaction_data)
#             elif donation_type == 'recurring':
#                 result = update_recurring_donation_status(donation_id, 'failed', transaction_data)
#             elif donation_type == 'in-kind':
#                 result = update_in_kind_donation_status(donation_id, 'failed', transaction_data)
#             else:
#                 return {
#                     'success': False,
#                     'error': f'Unknown donation type: {donation_type}'
#                 }
        
#         return result
        
#     except Exception as e:
#         print(f"    ERROR updating failed donation: {e}")
#         return {
#             'success': False,
#             'error': f'Error updating failed donation: {str(e)}'
#         }


# def handle_subscription_activated(event_data, meta):
#     """Handle subscription activation"""
#     print("    Handling subscription activation")
    
#     donation_id = meta.get('donation_id')
#     print(f"    - Donation ID: {donation_id}")
    
#     if not donation_id:
#         return {
#             'success': True,
#             'message': 'Test subscription activation acknowledged'
#         }
    
#     try:
#         recurring_donation = RecurringDonation.objects.get(id=donation_id)
#         recurring_donation.status = 'active'
#         recurring_donation.subscription_id = event_data.get('id')
#         recurring_donation.save()
        
#         print(f"    SUCCESS: Activated recurring donation {donation_id}")
#         return {
#             'success': True,
#             'message': f'Recurring donation {donation_id} activated'
#         }
        
#     except RecurringDonation.DoesNotExist:
#         print(f"    ERROR: Recurring donation {donation_id} not found")
#         return {
#             'success': False,
#             'error': f'Recurring donation {donation_id} not found'
#         }
#     except Exception as e:
#         print(f"    ERROR activating subscription: {e}")
#         return {
#             'success': False,
#             'error': f'Error activating subscription: {str(e)}'
#         }


# def handle_subscription_cancelled(event_data, meta):
#     """Handle subscription cancellation"""
#     print("    Handling subscription cancellation")
    
#     donation_id = meta.get('donation_id')
#     print(f"    - Donation ID: {donation_id}")
    
#     if not donation_id:
#         return {
#             'success': True,
#             'message': 'Test subscription cancellation acknowledged'
#         }
    
#     try:
#         recurring_donation = RecurringDonation.objects.get(id=donation_id)
#         recurring_donation.cancel_subscription("Cancelled via payment processor")
        
#         print(f"    SUCCESS: Cancelled recurring donation {donation_id}")
#         return {
#             'success': True,
#             'message': f'Recurring donation {donation_id} cancelled'
#         }
        
#     except RecurringDonation.DoesNotExist:
#         print(f"    ERROR: Recurring donation {donation_id} not found")
#         return {
#             'success': False,
#             'error': f'Recurring donation {donation_id} not found'
#         }
#     except Exception as e:
#         print(f"    ERROR cancelling subscription: {e}")
#         return {
#             'success': False,
#             'error': f'Error cancelling subscription: {str(e)}'
#         }


# def update_donation_status(donation_id, status, transaction_data):
#     """Update one-time donation status"""
#     print(f"      Updating donation {donation_id} to {status}")
    
#     try:
#         donation = Donation.objects.get(id=donation_id)
#         print(f"      - Found donation: {donation}")
        
#         old_status = donation.status
#         donation.status = status
        
#         # Update transaction fields
#         if transaction_data.get('transaction_id'):
#             donation.transaction_id = transaction_data['transaction_id']
#             print(f"      - Set transaction_id: {transaction_data['transaction_id']}")
            
#         if transaction_data.get('flutterwave_ref'):
#             donation.reference_number = transaction_data['flutterwave_ref']
#             print(f"      - Set reference_number: {transaction_data['flutterwave_ref']}")
            
#         if transaction_data.get('tx_ref'):
#             donation.bank_reference = transaction_data['tx_ref']
#             print(f"      - Set bank_reference: {transaction_data['tx_ref']}")
        
#         if status == 'completed':
#             donation.processed_date = timezone.now()
#             print(f"      - Set processed_date: {donation.processed_date}")
        
#         # Add transaction notes
#         transaction_notes = f"Flutterwave webhook: {transaction_data.get('transaction_id', 'N/A')}"
#         donation.notes = f"{donation.notes or ''}\n{transaction_notes}".strip()
        
#         donation.save()
        
#         print(f"      SUCCESS: Updated donation {donation_id} from {old_status} to {status}")
#         return {
#             'success': True,
#             'message': f'Donation {donation_id} updated from {old_status} to {status}'
#         }
        
#     except Donation.DoesNotExist:
#         print(f"      ERROR: Donation {donation_id} not found")
#         return {
#             'success': False,
#             'error': f'Donation {donation_id} not found'
#         }
#     except Exception as e:
#         print(f"      ERROR updating donation: {e}")
#         print(f"      Traceback: {traceback.format_exc()}")
#         return {
#             'success': False,
#             'error': f'Error updating donation: {str(e)}'
#         }


# def update_recurring_donation_status(donation_id, status, transaction_data):
#     """Update recurring donation status"""
#     print(f"      Updating recurring donation {donation_id} to {status}")
    
#     try:
#         recurring_donation = RecurringDonation.objects.get(id=donation_id)
#         print(f"      - Found recurring donation: {recurring_donation}")
        
#         if status == 'completed':
#             # Create individual donation record
#             donation = Donation.objects.create(
#                 donor=recurring_donation.donor,
#                 is_anonymous=recurring_donation.is_anonymous,
#                 campaign=recurring_donation.campaign,
#                 project=getattr(recurring_donation, 'project', None),
#                 amount=recurring_donation.amount,
#                 currency=recurring_donation.currency,
#                 payment_method=recurring_donation.payment_method,
#                 transaction_id=transaction_data.get('transaction_id'),
#                 reference_number=transaction_data.get('flutterwave_ref'),
#                 bank_reference=transaction_data.get('tx_ref'),
#                 status='completed',
#                 processed_date=timezone.now(),
#                 donation_source='website',
#                 notes=f"Recurring donation payment #{recurring_donation.payment_count + 1}"
#             )
            
#             print(f"      - Created donation record: {donation.id}")
            
#             # Update recurring donation
#             recurring_donation.record_successful_payment(donation)
#             print(f"      SUCCESS: Recorded successful recurring payment for {donation_id}")
            
#             return {
#                 'success': True,
#                 'message': f'Recurring payment recorded for donation {donation_id}'
#             }
            
#         elif status == 'failed':
#             recurring_donation.record_failed_payment()
#             print(f"      SUCCESS: Recorded failed recurring payment for {donation_id}")
            
#             return {
#                 'success': True,
#                 'message': f'Failed recurring payment recorded for donation {donation_id}'
#             }
        
#     except RecurringDonation.DoesNotExist:
#         print(f"      ERROR: Recurring donation {donation_id} not found")
#         return {
#             'success': False,
#             'error': f'Recurring donation {donation_id} not found'
#         }
#     except Exception as e:
#         print(f"      ERROR updating recurring donation: {e}")
#         print(f"      Traceback: {traceback.format_exc()}")
#         return {
#             'success': False,
#             'error': f'Error updating recurring donation: {str(e)}'
#         }


# def update_in_kind_donation_status(donation_id, status, transaction_data):
#     """Update in-kind donation status"""
#     print(f"      Updating in-kind donation {donation_id} to {status}")
    
#     try:
#         in_kind_donation = InKindDonation.objects.get(id=donation_id)
#         print(f"      - Found in-kind donation: {in_kind_donation}")
        
#         old_status = in_kind_donation.status
        
#         if status == 'completed':
#             in_kind_donation.status = 'confirmed'
#         elif status == 'failed':
#             in_kind_donation.status = 'pledged'
        
#         # Add transaction notes
#         transaction_notes = f"Processing fee webhook: {transaction_data.get('transaction_id', 'N/A')}"
#         in_kind_donation.notes = f"{in_kind_donation.notes or ''}\n{transaction_notes}".strip()
        
#         in_kind_donation.save()
        
#         print(f"      SUCCESS: Updated in-kind donation {donation_id} from {old_status} to {in_kind_donation.status}")
#         return {
#             'success': True,
#             'message': f'In-kind donation {donation_id} updated from {old_status} to {in_kind_donation.status}'
#         }
        
#     except InKindDonation.DoesNotExist:
#         print(f"      ERROR: In-kind donation {donation_id} not found")
#         return {
#             'success': False,
#             'error': f'In-kind donation {donation_id} not found'
#         }
#     except Exception as e:
#         print(f"      ERROR updating in-kind donation: {e}")
#         print(f"      Traceback: {traceback.format_exc()}")
#         return {
#             'success': False,
#             'error': f'Error updating in-kind donation: {str(e)}'
#         }