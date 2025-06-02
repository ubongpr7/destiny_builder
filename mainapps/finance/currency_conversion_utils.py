from decimal import Decimal
from django.utils import timezone
from .models import Currency, ExchangeRate
from django.contrib.auth import get_user_model
from django.db import models


try:
    from forex_python.converter import CurrencyRates, CurrencyConverter
    FOREX_AVAILABLE = True
except ImportError:
    FOREX_AVAILABLE = False

User = get_user_model()


def get_live_exchange_rate(from_currency_code, to_currency_code):
    """
    Get live exchange rate using forex-python
    """
    if not FOREX_AVAILABLE:
        raise Exception("forex-python library not available")
    
    try:
        c = CurrencyRates()
        rate = c.get_rate(from_currency_code, to_currency_code)
        return Decimal(str(rate))
    except Exception as e:
        raise Exception(f"Failed to get live exchange rate: {str(e)}")


def convert_amount(amount, from_currency, to_currency, conversion_date=None):
    """
    Convert amount from one currency to another
    """
    if from_currency == to_currency:
        return amount, Decimal('1.00000000')
    
    if not conversion_date:
        conversion_date = timezone.now()
    
    # Try to get existing exchange rate
    exchange_rate_record = ExchangeRate.objects.filter(
        from_currency=from_currency,
        to_currency=to_currency,
        effective_date__lte=conversion_date
    ).order_by('-effective_date').first()
    
    if exchange_rate_record:
        rate = exchange_rate_record.rate
        converted_amount = amount * rate
        return converted_amount, rate
    
    # Try to get live rate
    if FOREX_AVAILABLE:
        try:
            live_rate = get_live_exchange_rate(from_currency.code, to_currency.code)
            
            # Create exchange rate record
            system_user = get_system_user()
            ExchangeRate.objects.create(
                from_currency=from_currency,
                to_currency=to_currency,
                rate=live_rate,
                effective_date=conversion_date,
                source="forex-python API (auto-created)",
                created_by=system_user
            )
            
            converted_amount = amount * live_rate
            return converted_amount, live_rate
            
        except Exception as e:
            print(f"Failed to get live rate: {e}")
    
    # Fallback to 1:1 rate
    print(f"WARNING: Using 1:1 fallback rate for {from_currency.code} → {to_currency.code}")
    return amount, Decimal('1.00000000')


def get_system_user():
    """Get or create system user for automated operations"""
    try:
        system_user = User.objects.filter(username='system_webhook').first()
        if not system_user:
            system_user = User.objects.create_user(
                username='system_webhook',
                email='system@webhook.local',
                first_name='System',
                last_name='Webhook',
                is_active=True
            )
        return system_user
    except Exception:
        return User.objects.filter(is_superuser=True).first()


def update_donation_currency_conversion(donation):
    """
    Update currency conversion fields for a donation if needed
    """
    if not donation.campaign or not donation.currency or not donation.campaign.target_currency:
        return False
    
    if donation.currency == donation.campaign.target_currency:
        return False
    
    try:
        converted_amount, exchange_rate = convert_amount(
            donation.amount,
            donation.currency,
            donation.campaign.target_currency,
            donation.donation_date
        )
        
        donation.exchange_rate = exchange_rate
        donation.converted_amount = converted_amount
        donation.converted_currency = donation.campaign.target_currency
        
        return True
        
    except Exception as e:
        print(f"Error updating currency conversion for donation {donation.id}: {e}")
        return False


def bulk_update_currency_conversions():
    """
    Utility function to bulk update currency conversions for existing donations
    """
    from .models import Donation
    
    donations_needing_conversion = Donation.objects.filter(
        campaign__isnull=False,
        currency__isnull=False,
        campaign__target_currency__isnull=False,
        exchange_rate__isnull=True
    ).exclude(
        currency=models.F('campaign__target_currency')
    )
    
    updated_count = 0
    for donation in donations_needing_conversion:
        if update_donation_currency_conversion(donation):
            donation.save()
            updated_count += 1
    
    return updated_count
