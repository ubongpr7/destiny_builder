def get_default_currency():
        from mainapps.common.models import Currency
        return Currency.objects.get(code='USD').id