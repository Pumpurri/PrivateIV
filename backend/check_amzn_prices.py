"""
Check AMZN price movements vs portfolio variance
"""
import os
import psycopg2

database_url = os.getenv('DATABASE_URL')
if not database_url:
    print("ERROR: DATABASE_URL not set")
    exit(1)

conn = psycopg2.connect(database_url)
cursor = conn.cursor()

# Get AMZN stock info
cursor.execute("""
    SELECT id, symbol, name, currency
    FROM stocks_stock
    WHERE symbol = 'AMZN'
""")
stock = cursor.fetchone()

if not stock:
    print("AMZN not found!")
    exit(1)

stock_id, symbol, name, currency = stock
print(f"Stock: {symbol} - {name}")
print(f"Currency: {currency}")
print(f"Stock ID: {stock_id}\n")

# Get historical prices
cursor.execute("""
    SELECT date, price
    FROM portfolio_historicalstockprice
    WHERE stock_id = %s
    AND date BETWEEN '2025-10-24' AND '2025-11-07'
    ORDER BY date
""", (stock_id,))

prices = cursor.fetchall()

print("="*80)
print("AMZN HISTORICAL PRICES (USD)")
print("="*80)
print(f"{'Date':<12} | {'Price':>12} | {'Change':>12} | {'% Change':>10}")
print("-"*80)

prev_price = None
for date, price in prices:
    change_str = ""
    pct_str = ""

    if prev_price:
        change = float(price) - float(prev_price)
        pct = (change / float(prev_price)) * 100
        change_str = f"${change:+.2f}"
        pct_str = f"{pct:+.2f}%"

    print(f"{date} | ${float(price):>11.2f} | {change_str:>12} | {pct_str:>10}")
    prev_price = price

# Get portfolio 1 snapshots
print("\n" + "="*80)
print("PORTFOLIO 1 SNAPSHOTS")
print("="*80)

cursor.execute("""
    SELECT
        date,
        total_value,
        cash_balance,
        investment_value
    FROM portfolio_dailyportfoliosnapshot
    WHERE portfolio_id = 1
    AND date BETWEEN '2025-10-24' AND '2025-11-07'
    ORDER BY date
""")

snapshots = cursor.fetchall()

print(f"{'Date':<12} | {'Total Value':>15} | {'Cash':>15} | {'Investment':>15} | {'Total Change':>15} | {'Inv Change':>15}")
print("-"*110)

prev_total = None
prev_inv = None

for date, total, cash, inv in snapshots:
    total_change = ""
    inv_change = ""

    if prev_total:
        t_diff = float(total) - float(prev_total)
        total_change = f"S/. {t_diff:+.2f}"

    if prev_inv:
        i_diff = float(inv) - float(prev_inv)
        inv_change = f"S/. {i_diff:+.2f}"

    print(f"{date} | S/. {float(total):>12.2f} | S/. {float(cash):>12.2f} | S/. {float(inv):>12.2f} | {total_change:>15} | {inv_change:>15}")

    prev_total = total
    prev_inv = inv

# Get transactions for portfolio 1
print("\n" + "="*80)
print("PORTFOLIO 1 TRANSACTIONS (AMZN)")
print("="*80)

cursor.execute("""
    SELECT
        timestamp,
        transaction_type,
        quantity,
        executed_price,
        amount,
        fx_rate
    FROM portfolio_transaction
    WHERE portfolio_id = 1
    AND stock_id = %s
    ORDER BY timestamp
""", (stock_id,))

txns = cursor.fetchall()

total_shares = 0
print(f"{'Date':<20} | {'Type':<10} | {'Quantity':>10} | {'Price (USD)':>12} | {'FX Rate':>10}")
print("-"*80)

for timestamp, txn_type, qty, price, amount, fx in txns:
    print(f"{timestamp} | {txn_type:<10} | {qty:>10} | ${float(price):>11.2f} | {float(fx):>10.4f}")
    if txn_type == 'BUY':
        total_shares += qty
    elif txn_type == 'SELL':
        total_shares -= qty

print(f"\nTotal AMZN shares owned: {total_shares}")

# Calculate expected variance
print("\n" + "="*80)
print("EXPECTED PORTFOLIO VARIANCE CALCULATION")
print("="*80)
print(f"Shares owned: {total_shares}")
print(f"Cash balance: S/. 7,739.58 (constant)")
print()

# Get FX rates for the period
print("Getting FX rates...")
cursor.execute("""
    SELECT date, rate
    FROM portfolio_fxrate
    WHERE base_currency = 'USD'
    AND quote_currency = 'PEN'
    AND session = 'cierre'
    AND date BETWEEN '2025-10-24' AND '2025-11-07'
    ORDER BY date
""")

fx_rates = {date: rate for date, rate in cursor.fetchall()}

print(f"\n{'Date':<12} | {'AMZN (USD)':>12} | {'FX Rate':>10} | {'Market Val (PEN)':>18} | {'Expected Total':>18} | {'Actual Total':>18} | {'Difference':>15}")
print("-"*130)

price_dict = {date: price for date, price in prices}
snapshot_dict = {date: total for date, total, cash, inv in snapshots}

for date in sorted(price_dict.keys()):
    amzn_price = float(price_dict[date])
    fx_rate = float(fx_rates.get(date, 3.408))  # fallback to purchase rate

    market_value_usd = amzn_price * total_shares
    market_value_pen = market_value_usd * fx_rate

    cash = 7739.58
    expected_total = cash + market_value_pen

    actual_total = float(snapshot_dict.get(date, 0))
    difference = actual_total - expected_total if actual_total else 0

    print(f"{date} | ${amzn_price:>11.2f} | {fx_rate:>10.4f} | S/. {market_value_pen:>15.2f} | S/. {expected_total:>15.2f} | S/. {actual_total:>15.2f} | S/. {difference:>12.2f}")

cursor.close()
conn.close()
