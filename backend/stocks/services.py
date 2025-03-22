import requests
from .models import Stock
import os
from dotenv import load_dotenv

load_dotenv()

def fetch_data_for_companies(symbols): 
    """
    Fetch stock data for multiple companies from the FMP API.
    """
    api_key = os.getenv('API_KEY')
    url = f'https://financialmodelingprep.com/api/v3/quote/{symbols}/?apikey={api_key}'

    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching current price for {symbols}: {e}")
        return None