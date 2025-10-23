import os
from datetime import datetime

import requests
from dotenv import load_dotenv

from django.conf import settings
from django.utils import timezone

from .models import Stock

load_dotenv()

BVL_API_BASE = os.getenv('BVL_API_BASE', 'https://dataondemand.bvl.com.pe')
BVL_API_KEY = os.getenv('BVL_API_KEY', '')
BVL_CURRENCY_MAP = {
    'US$': 'USD',
    'S/': 'PEN',
}


def _normalize_currency(code: str) -> str:
    if not code:
        return ''
    code = code.strip()
    return BVL_CURRENCY_MAP.get(code, code[:3].upper())


def _parse_bvl_datetime(value: str):
    if not value:
        return None
    for fmt in ('%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S'):
        try:
            dt = datetime.strptime(value, fmt)
            if getattr(settings, 'USE_TZ', False) and timezone.is_naive(dt):
                tzinfo = timezone.get_current_timezone()
                return timezone.make_aware(dt, tzinfo)
            return dt
        except (ValueError, TypeError):
            continue
    return None


def fetch_bvl_market_data(
    sector: str = '',
    today: bool = True,
    company_code: str = '',
    input_company: str = ''
):
    """
    Fetch and normalize market data from BVL. Returns only local listings
    (companyCode != 'XXX') with canonical currency codes.
    """
    url = f"{BVL_API_BASE.rstrip('/')}/v1/stock-quote/market"
    payload = {
        "sector": sector,
        "today": today,
        "companyCode": company_code,
        "inputCompany": input_company,
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if BVL_API_KEY:
        headers["X-Api-Key"] = BVL_API_KEY

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Error fetching BVL market data: {exc}") from exc

    data = response.json() or {}
    records = data.get('content', [])

    locals_only = []
    for item in records:
        if not isinstance(item, dict):
            continue

        raw_code = (item.get('companyCode') or '').strip()
        if not raw_code or raw_code == 'XXX':
            continue

        symbol = (item.get('nemonico') or '').strip()
        if not symbol:
            continue

        # Calculate current_price as average of buy and sell
        buy = item.get('buy')
        sell = item.get('sell')
        last = item.get('last')
        previous = item.get('previous')

        current_price = None

        # Priority 1: Average of buy and sell (if both available)
        if buy is not None and sell is not None and buy > 0 and sell > 0:
            current_price = (buy + sell) / 2
        # Priority 2: Use last price if available
        elif last is not None and last > 0:
            current_price = last
        # Priority 3: Use buy or sell if one is available
        elif buy is not None and buy > 0:
            current_price = buy
        elif sell is not None and sell > 0:
            current_price = sell

        # Skip stocks without any valid pricing data
        if current_price is None:
            continue

        # For previous_close, use it if available, otherwise use 0 or current_price
        # to avoid excluding stocks
        previous_close = previous if previous is not None else current_price

        currency = _normalize_currency(item.get('currency', ''))
        market_ts = _parse_bvl_datetime(item.get('lastDate'))

        locals_only.append({
            "company_code": raw_code,
            "symbol": symbol,
            "name": (item.get('companyName') or item.get('shortName') or '').strip(),
            "current_price": current_price,
            "previous_close": previous_close,
            "currency": currency,
            "segment": item.get('segment'),
            "percentage_change": item.get('percentageChange'),
            "market_timestamp": market_ts,
            "raw": item,
        })

    return locals_only


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
