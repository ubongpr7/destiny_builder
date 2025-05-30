import json
import hashlib
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
 
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