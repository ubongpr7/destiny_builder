# import requests
# from django.conf import settings
# def get_exchange_rate(from_currency: str, to_currency: str, ) -> float:
#     """
#     Fetches the exchange rate from 'from_currency' to 'to_currency' using ExchangeRate-API.

#     Parameters:
#     - from_currency (str): The base currency code (e.g., 'USD').
#     - to_currency (str): The target currency code (e.g., 'EUR').
#     - api_key (str): Your ExchangeRate-API key.

#     Returns:
#     - float: The exchange rate.

#     Raises:
#     - Exception: If the API request fails or returns an error.

#     """
#     api_key = settings.EXCHANGERATE_API_KEY
#     url = f"https://v6.exchangerate-api.com/v6/{api_key}/pair/{from_currency}/{to_currency}"
    
#     try:
#         response = requests.get(url)
#         response.raise_for_status()  # Raise an exception for HTTP errors
#         data = response.json()
        
#         if data['result'] == 'success':
#             return data['conversion_rate']
#         else:
#             raise Exception(f"API error: {data.get('error-type', 'Unknown error')}")
    
#     except requests.exceptions.RequestException as e:
#         raise Exception(f"Request error: {e}")
from freecurrencyapi import Client

def get_exchange_rate(from_currency: str, to_currency: str, api_key: str) -> float:
    """
    Get the exchange rate from 'from_currency' to 'to_currency' using freecurrencyapi.

    Parameters:
    - from_currency (str): Currency code to convert from (e.g., "USD")
    - to_currency (str): Currency code to convert to (e.g., "NGN")
    - api_key (str): Your freecurrencyapi API key

    Returns:
    - float: The current exchange rate

    Raises:
    - Exception: If an error occurs while fetching the rate
    """
    try:
        client = Client(api_key)
        response = client.latest(
            base_currency=from_currency,
            currencies=[to_currency]
        )
        rate = response["data"].get(to_currency)
        if rate is None:
            raise Exception(f"Rate not found for {to_currency}")
        return rate
    except Exception as e:
        raise Exception(f"Error getting exchange rate: {e}")
