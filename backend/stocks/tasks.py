from celery import shared_task
from datetime import datetime, timezone as datetime_timezone
import logging
from math import ceil

from django.utils import timezone

from .market import get_market_date, previous_business_day
from .models import HistoricalStockPrice, Stock, StockRefreshStatus
from .services import fetch_bvl_market_data, fetch_data_for_companies

logger = logging.getLogger(__name__)

COMPANIES = [
    {'symbol': 'AAPL', 'name': 'Apple Inc.'},
    {'symbol': 'MSFT', 'name': 'Microsoft Corp.'},
    {'symbol': 'GOOGL', 'name': 'Alphabet Inc.'},
    {'symbol': 'AMZN', 'name': 'Amazon.com Inc.'},
    {'symbol': 'META', 'name': 'Meta Platforms Inc.'},
    {'symbol': 'NVDA', 'name': 'NVIDIA Corp.'},
    {'symbol': 'IBM', 'name': 'IBM (International Business Machines Corp.)'},
    {'symbol': 'ADBE', 'name': 'Adobe Inc.'},
    {'symbol': 'CRM', 'name': 'Salesforce Inc.'},
    {'symbol': 'ORCL', 'name': 'Oracle Corp.'},
    {'symbol': 'NOW', 'name': 'ServiceNow Inc.'},
    {'symbol': 'PLTR', 'name': 'Palantir Technologies Inc.'},
    {'symbol': 'SAP', 'name': 'SAP SE'},
    {'symbol': 'CSCO', 'name': 'Cisco Systems Inc.'},
    {'symbol': 'TSLA', 'name': 'Tesla Inc.'},
    {'symbol': 'INTC', 'name': 'Intel Corp.'},
    {'symbol': 'AMD', 'name': 'Advanced Micro Devices Inc.'},
    {'symbol': 'QCOM', 'name': 'Qualcomm Inc.'},
    {'symbol': 'AVGO', 'name': 'Broadcom Inc.'},
    {'symbol': 'V', 'name': 'Visa Inc.'},

    {'symbol': 'MA', 'name': 'Mastercard Inc.'},
    {'symbol': 'PYPL', 'name': 'PayPal Holdings Inc.'},
    {'symbol': 'SQ', 'name': 'Block Inc.'},
    {'symbol': 'HOOD', 'name': 'Robinhood Markets Inc.'},
    {'symbol': 'NFLX', 'name': 'Netflix Inc.'},
    {'symbol': 'SPOT', 'name': 'Spotify Technology S.A.'},
    {'symbol': 'EA', 'name': 'Electronic Arts Inc.'},
    {'symbol': 'U', 'name': 'Unity Software Inc.'},
    {'symbol': 'TTWO', 'name': 'Take-Two Interactive Software Inc.'},
    {'symbol': 'NET', 'name': 'Cloudflare Inc.'},
    {'symbol': 'SNOW', 'name': 'Snowflake Inc.'},
    {'symbol': 'CRWD', 'name': 'CrowdStrike Holdings Inc.'},
    {'symbol': 'MDB', 'name': 'MongoDB Inc.'},
    {'symbol': 'RIVN', 'name': 'Rivian Automotive Inc.'},
    {'symbol': 'LCID', 'name': 'Lucid Group Inc.'},
    {'symbol': 'NKLA', 'name': 'Nikola Corp.'},
    {'symbol': 'UBER', 'name': 'Uber Technologies Inc.'},
    {'symbol': 'LYFT', 'name': 'Lyft Inc.'},
    {'symbol': 'SNAP', 'name': 'Snap Inc.'},
    {'symbol': 'PINS', 'name': 'Pinterest Inc.'},

    {'symbol': 'AI', 'name': 'C3.ai Inc.'},
    {'symbol': 'PATH', 'name': 'UiPath Inc.'},
    {'symbol': 'WMT', 'name': 'Walmart Inc.'},
    {'symbol': 'HD', 'name': 'The Home Depot Inc.'},
    {'symbol': 'COST', 'name': 'Costco Wholesale Corp.'},
    {'symbol': 'PEP', 'name': 'PepsiCo Inc.'},
    {'symbol': 'KO', 'name': 'Coca-Cola Co.'},
    {'symbol': 'NKE', 'name': 'Nike Inc.'},
    {'symbol': 'F', 'name': 'Ford Motor Co.'},
    {'symbol': 'GM', 'name': 'General Motors Co.'},
    {'symbol': 'TM', 'name': 'Toyota Motor Corp.'},
    {'symbol': 'BRK.B', 'name': 'Berkshire Hathaway Inc.'},
    {'symbol': 'GS', 'name': 'Goldman Sachs Group Inc.'},
    {'symbol': 'MS', 'name': 'Morgan Stanley'},
    {'symbol': 'C', 'name': 'Citigroup Inc.'},
    {'symbol': 'JPM', 'name': 'JPMorgan Chase & Co.'},
    {'symbol': 'JNJ', 'name': 'Johnson & Johnson'},
    {'symbol': 'PFE', 'name': 'Pfizer Inc.'},
    {'symbol': 'LLY', 'name': 'Eli Lilly and Co.'},
    {'symbol': 'ABBV', 'name': 'AbbVie Inc.'},

    {'symbol': 'MRK', 'name': 'Merck & Co. Inc.'},
    {'symbol': 'XOM', 'name': 'Exxon Mobil Corp.'},
    {'symbol': 'CVX', 'name': 'Chevron Corp.'},
    {'symbol': 'NEE', 'name': 'NextEra Energy Inc.'},
    {'symbol': 'DUK', 'name': 'Duke Energy Corp.'},
    {'symbol': 'FDX', 'name': 'FedEx Corp.'},
    {'symbol': 'UPS', 'name': 'United Parcel Service Inc.'},
    {'symbol': 'BA', 'name': 'Boeing Co.'},
    {'symbol': 'LMT', 'name': 'Lockheed Martin Corp.'},
    {'symbol': 'GE', 'name': 'General Electric Co.'},
    {'symbol': 'MMM', 'name': '3M Co.'},
    {'symbol': 'HON', 'name': 'Honeywell International Inc.'},
    {'symbol': 'T', 'name': 'AT&T Inc.'},
    {'symbol': 'VZ', 'name': 'Verizon Communications Inc.'},
    {'symbol': 'TMUS', 'name': 'T-Mobile US Inc.'},
    {'symbol': 'DIS', 'name': 'Walt Disney Co.'},
    {'symbol': 'CMCSA', 'name': 'Comcast Corp.'},
    {'symbol': 'ADP', 'name': 'Automatic Data Processing Inc.'},
    {'symbol': 'BK', 'name': 'Bank of New York Mellon Corp.'},
    {'symbol': 'SCHW', 'name': 'Charles Schwab Corp.'},
]

FMP_FREE_PLAN_SYMBOLS = [
    'AAPL', 'TSLA', 'AMZN', 'MSFT', 'NVDA', 'GOOGL', 'META', 'NFLX', 'JPM', 'V',
    'BAC', 'PYPL', 'DIS', 'T', 'PFE', 'COST', 'INTC', 'KO', 'TGT', 'NKE',
    'SPY', 'BA', 'BABA', 'XOM', 'WMT', 'GE', 'CSCO', 'VZ', 'JNJ', 'CVX',
    'PLTR', 'SQ', 'SHOP', 'SBUX', 'SOFI', 'HOOD', 'RBLX', 'SNAP', 'AMD', 'UBER',
    'FDX', 'ABBV', 'ETSY', 'MRNA', 'LMT', 'GM', 'F', 'LCID', 'CCL', 'DAL',
    'UAL', 'AAL', 'TSM', 'SONY', 'ET', 'MRO', 'COIN', 'RIVN', 'RIOT', 'CPRX',
    'VWO', 'SPYG', 'NOK', 'ROKU', 'VIAC', 'ATVI', 'BIDU', 'DOCU', 'ZM', 'PINS',
    'TLRY', 'WBA', 'MGM', 'NIO', 'C', 'GS', 'WFC', 'ADBE', 'PEP', 'UNH',
    'CARR', 'HCA', 'TWTR', 'BILI', 'SIRI', 'FUBO', 'RKT',
]

# Keep the full tracked universe above so enabling the paid tier is a one-line change.
USE_FMP_FREE_PLAN_SYMBOLS_ONLY = True

_COMPANY_BY_SYMBOL = {company['symbol']: company for company in COMPANIES}

ACTIVE_COMPANIES = (
    [
        _COMPANY_BY_SYMBOL.get(symbol, {'symbol': symbol, 'name': symbol})
        for symbol in FMP_FREE_PLAN_SYMBOLS
    ]
    if USE_FMP_FREE_PLAN_SYMBOLS_ONLY
    else COMPANIES
)

# Backward-compatible aliases used by older tests/imports.
companies = COMPANIES
active_companies = ACTIVE_COMPANIES


def batch_companies(companies, batch_size=20):
    """
    Divide the list of companies into batches of a specified size.
    """
    num_batches = ceil(len(companies) / batch_size)
    return [companies[i*batch_size: (i+1)*batch_size] for i in range(num_batches)]


def _coerce_quote_timestamp(value):
    if value in (None, ''):
        return None

    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=datetime_timezone.utc)

    if isinstance(value, str):
        stripped = value.strip()
        try:
            return datetime.fromtimestamp(float(stripped), tz=datetime_timezone.utc)
        except ValueError:
            try:
                parsed = datetime.fromisoformat(stripped.replace('Z', '+00:00'))
                if timezone.is_naive(parsed):
                    parsed = timezone.make_aware(parsed, timezone.get_default_timezone())
                return parsed
            except ValueError:
                return None

    return None


def _resolve_quote_market_date(*, is_local, currency, market_timestamp=None, raw_timestamp=None):
    quote_timestamp = market_timestamp or _coerce_quote_timestamp(raw_timestamp)
    if quote_timestamp is not None:
        return get_market_date(is_local=is_local, currency=currency, now=quote_timestamp)
    return get_market_date(is_local=is_local, currency=currency)


def _resolve_previous_close_date(symbol, market_date):
    existing_stock = Stock.objects.filter(symbol=symbol).only('id').first()
    if existing_stock is not None:
        historical_date = HistoricalStockPrice.objects.filter(
            stock=existing_stock,
            date__lt=market_date,
        ).order_by('-date').values_list('date', flat=True).first()
        if historical_date is not None:
            return historical_date
    return previous_business_day(market_date)


def update_local_stock_prices():
    """
    Fetch and upsert BVL local listings into the Stock table.
    """
    try:
        records = fetch_bvl_market_data()
    except RuntimeError:
        logger.exception(
            "Failed to fetch BVL stock data",
            extra={"provider": "bvl"},
        )
        return False

    if not records:
        logger.info(
            "Fetched BVL stock data with no records",
            extra={"provider": "bvl", "records": 0},
        )
        return True

    for item in records:
        market_date = _resolve_quote_market_date(
            is_local=True,
            currency=item.get('currency') or 'PEN',
            market_timestamp=item.get('market_timestamp'),
        )
        defaults = {
            'name': item.get('name') or item.get('symbol'),
            'current_price': item.get('current_price'),
            'previous_close': item.get('previous_close'),
            'previous_close_date': _resolve_previous_close_date(item['symbol'], market_date),
            'currency': item.get('currency') or 'PEN',
            'company_code': item.get('company_code', ''),
            'is_local': True,
        }
        Stock.objects.update_or_create(symbol=item['symbol'], defaults=defaults)

    logger.info(
        "Updated BVL stock prices",
        extra={"provider": "bvl", "records": len(records)},
    )
    return True


def update_us_stock_prices(data):
    """
    Update stock prices in the database based on the fetched US market data.
    """
    if not data:
        return

    for stock_info in data:
        symbol = stock_info.get('symbol')
        current_price = stock_info.get('price', 0.0)
        previous_close = stock_info.get('previousClose')
        name = stock_info.get('name', 'Unknown')
        market_date = _resolve_quote_market_date(
            is_local=False,
            currency=stock_info.get('currency') or 'USD',
            raw_timestamp=stock_info.get('timestamp'),
        )

        Stock.objects.update_or_create(
            symbol=symbol,
            defaults={
                'name': name,
                'current_price': current_price,
                'previous_close': previous_close,
                'previous_close_date': _resolve_previous_close_date(symbol, market_date),
                'company_code': '',
                'is_local': False,
            }
        )


@shared_task
def fetch_stock_prices():
    """
    Celery task to fetch and update stock prices for all companies.
    This updates Stock.current_price only (for intraday updates).
    For end-of-day historical prices, use fetch_eod_prices() instead.
    """
    successful_upstream_calls = 0

    # TODO: split BVL ingestion into its own scheduled task so it can
    # continue refreshing after NYSE-specific schedules pause.
    if update_local_stock_prices():
        successful_upstream_calls += 1

    for company in ACTIVE_COMPANIES:
        symbol = company['symbol']
        try:
            data = fetch_data_for_companies(symbol)
        except RuntimeError:
            logger.exception(
                "Failed to fetch US stock data",
                extra={"provider": "fmp", "symbols": symbol},
            )
            continue

        if data is None:
            logger.error(
                "FMP stock data returned no response",
                extra={"provider": "fmp", "symbols": symbol},
            )
            continue

        successful_upstream_calls += 1

        if data:
            update_us_stock_prices(data)

        logger.info(
            "Processed US stock price",
            extra={
                "provider": "fmp",
                "symbols": symbol,
                "records": len(data) if isinstance(data, list) else None,
            },
        )

    if successful_upstream_calls == 0:
        logger.error(
            "Stock refresh failed because all upstream calls failed",
            extra={"task": "fetch_stock_prices"},
        )
        raise RuntimeError("Stock refresh failed because all upstream calls failed")

    StockRefreshStatus.mark_refreshed(timezone.now())


@shared_task
def fetch_eod_prices():
    """
    Celery task to fetch end-of-day prices and save them to HistoricalStockPrice.
    This should run once per day after market close (4:00 PM EST).

    Saves both current_price (Stock table) and historical_price (HistoricalStockPrice table).
    """
    today = timezone.now().date()
    successful_upstream_calls = 0

    # Fetch BVL stocks and save historical
    try:
        records = fetch_bvl_market_data()
        successful_upstream_calls += 1
        if records:
            for item in records:
                market_date = _resolve_quote_market_date(
                    is_local=True,
                    currency=item.get('currency') or 'PEN',
                    market_timestamp=item.get('market_timestamp'),
                )
                defaults = {
                    'name': item.get('name') or item.get('symbol'),
                    'current_price': item.get('current_price'),
                    'previous_close': item.get('previous_close'),
                    'previous_close_date': _resolve_previous_close_date(item['symbol'], market_date),
                    'currency': item.get('currency') or 'PEN',
                    'company_code': item.get('company_code', ''),
                    'is_local': True,
                }
                stock, created = Stock.objects.update_or_create(
                    symbol=item['symbol'],
                    defaults=defaults
                )

                # Save EOD historical price
                current_price = item.get('current_price')
                if current_price and current_price > 0:
                    HistoricalStockPrice.objects.update_or_create(
                        stock=stock,
                        date=market_date,
                        defaults={'price': current_price}
                    )
    except RuntimeError:
        logger.exception(
            "Failed to fetch BVL EOD stock data",
            extra={"provider": "bvl"},
        )

    # Fetch US stocks and save historical
    for company in ACTIVE_COMPANIES:
        symbol = company['symbol']
        try:
            data = fetch_data_for_companies(symbol)
        except RuntimeError:
            logger.exception(
                "Failed to fetch US EOD stock data",
                extra={"provider": "fmp", "symbols": symbol},
            )
            continue

        if data is None:
            logger.error(
                "FMP EOD stock data returned no response",
                extra={"provider": "fmp", "symbols": symbol},
            )
            continue

        successful_upstream_calls += 1

        if data:
            for stock_info in data:
                symbol = stock_info.get('symbol')
                current_price = stock_info.get('price', 0.0)
                previous_close = stock_info.get('previousClose')
                name = stock_info.get('name', 'Unknown')
                market_date = _resolve_quote_market_date(
                    is_local=False,
                    currency=stock_info.get('currency') or 'USD',
                    raw_timestamp=stock_info.get('timestamp'),
                )

                stock, created = Stock.objects.update_or_create(
                    symbol=symbol,
                    defaults={
                        'name': name,
                        'current_price': current_price,
                        'previous_close': previous_close,
                        'previous_close_date': _resolve_previous_close_date(symbol, market_date),
                        'company_code': '',
                        'is_local': False,
                    }
                )

                # Save EOD historical price
                if current_price and current_price > 0:
                    HistoricalStockPrice.objects.update_or_create(
                        stock=stock,
                        date=market_date,
                        defaults={'price': current_price}
                    )

        logger.info(
            "Processed US EOD stock price",
            extra={
                "provider": "fmp",
                "symbols": symbol,
                "records": len(data) if isinstance(data, list) else None,
            },
        )

    if successful_upstream_calls == 0:
        logger.error(
            "EOD stock refresh failed because all upstream calls failed",
            extra={"task": "fetch_eod_prices", "date": str(today)},
        )
        raise RuntimeError("EOD stock refresh failed because all upstream calls failed")

    StockRefreshStatus.mark_refreshed(timezone.now())
    logger.info(
        "EOD prices saved",
        extra={"task": "fetch_eod_prices", "date": str(today)},
    )
