from celery import shared_task
from math import ceil

from django.utils import timezone

from .models import Stock, StockRefreshStatus
from .services import fetch_bvl_market_data, fetch_data_for_companies

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


def batch_companies(companies, batch_size=20):
    """
    Divide the list of companies into batches of a specified size.
    """
    num_batches = ceil(len(companies) / batch_size)
    return [companies[i*batch_size: (i+1)*batch_size] for i in range(num_batches)]


def update_local_stock_prices():
    """
    Fetch and upsert BVL local listings into the Stock table.
    """
    try:
        records = fetch_bvl_market_data()
    except RuntimeError as exc:
        print(f"[stocks] Failed to fetch BVL data: {exc}")
        return

    if not records:
        return

    for item in records:
        defaults = {
            'name': item.get('name') or item.get('symbol'),
            'current_price': item.get('current_price'),
            'previous_close': item.get('previous_close'),
            'currency': item.get('currency') or 'PEN',
            'company_code': item.get('company_code', ''),
            'is_local': True,
        }
        Stock.objects.update_or_create(symbol=item['symbol'], defaults=defaults)


def update_us_stock_prices(data):
    """
    Update stock prices in the database based on the fetched US market data.
    """
    if not data:
        return
    
    for stock_info in data:
        symbol = stock_info.get('symbol')
        current_price = stock_info.get('price', 0.0)
        name = stock_info.get('name', 'Unknown')

        Stock.objects.update_or_create(
            symbol=symbol,
            defaults={
                'name': name,
                'current_price': current_price,
                'company_code': '',
                'is_local': False,
            }
        )


@shared_task
def fetch_stock_prices():
    """
    Celery task to fetch and update stock prices for all companies
    """
    # TODO: split BVL ingestion into its own scheduled task so it can
    # continue refreshing after NYSE-specific schedules pause.
    update_local_stock_prices()

    batches = batch_companies(COMPANIES, batch_size=20)

    for batch in batches:
        symbols = ','.join([company['symbol'] for company in batch])
        data = fetch_data_for_companies(symbols)

        if data:
            update_us_stock_prices(data)
        
        print(f"Updated stock prices for batch: {symbols}")
    StockRefreshStatus.mark_refreshed(timezone.now())
        
