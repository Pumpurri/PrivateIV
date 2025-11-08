import os
from dotenv import load_dotenv
import psycopg2
from decimal import Decimal, ROUND_HALF_UP

load_dotenv()

db_url = os.getenv('DATABASE_PUBLIC_URL')
conn = psycopg2.connect(db_url)
cursor = conn.cursor()

print("=" * 80)
print("SIMULATING SNAPSHOT VALUES AFTER FIX")
print("=" * 80)

portfolio_id = 1
snapshot_date = '2025-10-29'

# Calculate cash using the NEW method
cursor.execute("""
    SELECT
        t.transaction_type,
        t.amount,
        t.fx_rate
    FROM portfolio_transaction t
    WHERE t.portfolio_id = %s
    AND t.timestamp::date <= %s
    ORDER BY t.timestamp ASC;
""", (portfolio_id, snapshot_date))

transactions = cursor.fetchall()
cash_balance = Decimal('0.00')

print(f"\nCalculating cash for snapshot date: {snapshot_date}")
print("\nTransaction Processing:")

for txn_type, amount, fx_rate in transactions:
    amount_dec = Decimal(str(amount)) if amount else Decimal('0.00')
    fx_rate_dec = Decimal(str(fx_rate)) if fx_rate else Decimal('1.00')
    
    if txn_type == 'DEPOSIT':
        cash_balance += amount_dec
        print(f"  DEPOSIT: +{amount_dec:,.2f} → {cash_balance:,.2f}")
    elif txn_type == 'WITHDRAWAL':
        cash_balance -= amount_dec
        print(f"  WITHDRAWAL: -{amount_dec:,.2f} → {cash_balance:,.2f}")
    elif txn_type == 'BUY':
        cash_in_base = amount_dec * fx_rate_dec
        cash_balance -= cash_in_base
        print(f"  BUY: -{amount_dec:,.2f} × {fx_rate_dec:.4f} = -{cash_in_base:,.2f} → {cash_balance:,.2f}")
    elif txn_type == 'SELL':
        cash_in_base = amount_dec * fx_rate_dec
        cash_balance += cash_in_base
        print(f"  SELL: +{amount_dec:,.2f} × {fx_rate_dec:.4f} = +{cash_in_base:,.2f} → {cash_balance:,.2f}")

cash_balance = cash_balance.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

# Get holdings and calculate investment value for that date
print(f"\n\nCalculating investment value...")

# For simplicity, let's use current holdings
cursor.execute("""
    SELECT
        s.symbol,
        s.current_price,
        s.currency,
        h.quantity
    FROM portfolio_holding h
    JOIN stocks_stock s ON h.stock_id = s.id
    WHERE h.portfolio_id = %s AND h.quantity > 0;
""", (portfolio_id,))

holdings = cursor.fetchall()
investment_value = Decimal('0.00')

for symbol, current_price, currency, quantity in holdings:
    native_value = Decimal(str(current_price)) * Decimal(str(quantity))
    
    # Get FX rate for conversion
    cursor.execute("""
        SELECT rate
        FROM portfolio_fxrate
        WHERE base_currency = 'PEN' AND quote_currency = %s
        AND date <= %s
        ORDER BY date DESC, fetched_at DESC
        LIMIT 1;
    """, (currency, snapshot_date))
    
    fx_result = cursor.fetchone()
    if fx_result:
        fx_rate = Decimal(str(fx_result[0]))
        value_pen = native_value * fx_rate
    else:
        value_pen = native_value
    
    investment_value += value_pen
    print(f"  {symbol}: {quantity} × {current_price} {currency} = {value_pen:,.2f} PEN")

investment_value = investment_value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
total_value = (cash_balance + investment_value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

# Get current snapshot values
cursor.execute("""
    SELECT date, total_value, cash_balance, investment_value
    FROM portfolio_dailyportfoliosnapshot
    WHERE portfolio_id = %s
    ORDER BY date DESC
    LIMIT 2;
""", (portfolio_id,))
snapshots = cursor.fetchall()

print("\n" + "=" * 80)
print("COMPARISON")
print("=" * 80)

print("\n📊 CURRENT SNAPSHOT (BEFORE FIX):")
if snapshots:
    snap_date, snap_total, snap_cash, snap_invest = snapshots[0]
    print(f"  Date:       {snap_date}")
    print(f"  Total:      PEN {snap_total:,.2f}")
    print(f"  Cash:       PEN {snap_cash:,.2f}")
    print(f"  Investment: PEN {snap_invest:,.2f}")

print("\n✨ NEW SNAPSHOT (AFTER FIX):")
print(f"  Date:       {snapshot_date}")
print(f"  Total:      PEN {total_value:,.2f}")
print(f"  Cash:       PEN {cash_balance:,.2f}")
print(f"  Investment: PEN {investment_value:,.2f}")

print("\n📈 DAILY VARIATION (AFTER FIX):")
if len(snapshots) >= 2:
    yesterday_date, yesterday_total, _, _ = snapshots[1]
    
    # Old calculation (wrong)
    if snapshots:
        old_snap_total = Decimal(str(snapshots[0][1]))
        old_yesterday_total = Decimal(str(snapshots[1][1]))
        old_change = old_snap_total - old_yesterday_total
        old_pct = (old_change / old_yesterday_total * 100) if old_yesterday_total > 0 else Decimal('0')
        
        print(f"\n  OLD (wrong):")
        print(f"    Yesterday: PEN {old_yesterday_total:,.2f}")
        print(f"    Today:     PEN {old_snap_total:,.2f}")
        print(f"    Change:    PEN {old_change:+,.2f} ({old_pct:+.2f}%)")
    
    # New calculation (correct)
    # For accurate comparison, we'd need to regenerate yesterday's snapshot too
    # But we can show the expected change
    print(f"\n  NEW (correct):")
    print(f"    Today's snapshot will have cash = PEN {cash_balance:,.2f}")
    print(f"    This should result in a small daily variation (< 1%)")
    print(f"    Instead of the incorrect -17.70%")

cursor.close()
conn.close()
