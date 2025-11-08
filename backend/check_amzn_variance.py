"""
Check if the portfolio variance matches AMZN stock price movements
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'TradeSimulator.settings')
django.setup()

from portfolio.models.historical_price import HistoricalStockPrice
from stocks.models import Stock
from decimal import Decimal

# Get AMZN stock
try:
    amzn = Stock.objects.get(symbol='AMZN')
    print(f"Found AMZN: {amzn.name} (ID: {amzn.id})")
    print(f"Currency: {amzn.currency}")
    print()
except Stock.DoesNotExist:
    print("AMZN stock not found!")
    exit(1)

# Get historical prices from Oct 24 to Nov 7
prices = HistoricalStockPrice.objects.filter(
    stock=amzn,
    date__gte='2024-10-24',
    date__lte='2024-11-07'
).order_by('date')

print("AMZN Historical Prices:")
print(f"{'Date':<12} | {'Price (USD)':>12} | {'Change USD':>12} | {'Change %':>10}")
print("-" * 60)

prev_price = None
for price_record in prices:
    change_usd = ""
    change_pct = ""

    if prev_price:
        diff = float(price_record.price) - float(prev_price)
        pct = (diff / float(prev_price)) * 100
        change_usd = f"${diff:+.2f}"
        change_pct = f"{pct:+.2f}%"

    print(f"{price_record.date} | ${float(price_record.price):>11.2f} | {change_usd:>12} | {change_pct:>10}")
    prev_price = price_record.price

print("\n" + "="*60)
print("PORTFOLIO VALUE CALCULATION (3 shares of AMZN)")
print("="*60)

# Portfolio has 3 shares of AMZN bought at $221.09
shares = 3
purchase_price = Decimal('221.09')
fx_rate = Decimal('3.408')  # USD to PEN rate at purchase

print(f"\nShares owned: {shares}")
print(f"Purchase price: ${purchase_price} per share")
print(f"FX Rate (USD->PEN) at purchase: {fx_rate}")
print(f"Cash balance: S/. 7,739.58 (constant)")
print()

print(f"{'Date':<12} | {'AMZN Price':>12} | {'Market Value (USD)':>18} | {'Market Value (PEN)':>18} | {'Total Portfolio':>18} | {'Daily Change':>15}")
print("-" * 120)

prev_total = None
for price_record in prices:
    current_price = price_record.price

    # Calculate market value in USD
    market_value_usd = current_price * shares

    # Need to get FX rate for this date to convert to PEN
    # For now, let's assume we need to check what FX rate the system is using
    from portfolio.services.fx_service import get_fx_rate
    from datetime import datetime

    try:
        # Get FX rate for this date (USD to PEN)
        date_obj = price_record.date if isinstance(price_record.date, datetime) else datetime.strptime(str(price_record.date), '%Y-%m-%d').date()
        fx_rate_date = get_fx_rate(
            date_obj,
            from_currency='PEN',
            to_currency='USD',
            rate_type='mid',
            session='cierre'
        )
        # This returns PEN/USD, so market value in PEN = market_value_usd * fx_rate
        market_value_pen = market_value_usd * fx_rate_date
    except Exception as e:
        print(f"Error getting FX rate for {price_record.date}: {e}")
        # Fallback to purchase FX rate
        market_value_pen = market_value_usd * fx_rate

    cash_balance = Decimal('7739.58')
    total_portfolio = cash_balance + market_value_pen

    change = ""
    if prev_total:
        diff = float(total_portfolio - prev_total)
        change = f"S/. {diff:+.2f}"

    print(f"{price_record.date} | ${float(current_price):>11.2f} | ${float(market_value_usd):>17.2f} | S/. {float(market_value_pen):>15.2f} | S/. {float(total_portfolio):>15.2f} | {change:>15}")
    prev_total = total_portfolio

print("\n" + "="*60)
print("EXPECTED vs ACTUAL SNAPSHOTS")
print("="*60)

# Now compare with actual snapshots
from portfolio.models.daily_snapshot import DailyPortfolioSnapshot

snapshots = DailyPortfolioSnapshot.objects.filter(
    portfolio_id=1,
    date__gte='2024-10-24',
    date__lte='2024-11-07'
).order_by('date')

print(f"\n{'Date':<12} | {'Snapshot Total':>18} | {'Snapshot Investment':>20} | {'Snapshot Cash':>18}")
print("-" * 80)

for snap in snapshots:
    print(f"{snap.date} | S/. {float(snap.total_value):>15.2f} | S/. {float(snap.investment_value):>17.2f} | S/. {float(snap.cash_balance):>15.2f}")
