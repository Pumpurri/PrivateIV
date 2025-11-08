import os
from dotenv import load_dotenv
import psycopg2
from decimal import Decimal

load_dotenv()

db_url = os.getenv('DATABASE_PUBLIC_URL')
conn = psycopg2.connect(db_url)
cursor = conn.cursor()

print("=" * 80)
print("CASH BALANCE DISCREPANCY ANALYSIS")
print("=" * 80)

# Get portfolio info
portfolio_id = 1

cursor.execute("""
    SELECT id, name, base_currency, cash_balance
    FROM portfolio_portfolio
    WHERE id = %s;
""", (portfolio_id,))
portfolio = cursor.fetchone()
portfolio_id, name, base_currency, cash_balance = portfolio

print(f"\nPortfolio: {name}")
print(f"Current Cash Balance (from portfolio table): {base_currency} {cash_balance:,.2f}")

# Get all transactions
print(f"\n{'='*80}")
print("ALL TRANSACTIONS (chronological order)")
print(f"{'='*80}")

cursor.execute("""
    SELECT
        t.id,
        t.transaction_type,
        s.symbol,
        t.quantity,
        t.executed_price,
        t.amount,
        t.fx_rate,
        t.fx_rate_type,
        t.timestamp
    FROM portfolio_transaction t
    LEFT JOIN stocks_stock s ON t.stock_id = s.id
    WHERE t.portfolio_id = %s
    ORDER BY t.timestamp ASC;
""", (portfolio_id,))
transactions = cursor.fetchall()

print(f"\n{'ID':<6} {'Type':<12} {'Symbol':<8} {'Qty':<6} {'Price':<12} {'Amount':<15} {'FX Rate':<10} {'Date':<20}")
print("-" * 110)

running_cash = Decimal('0.00')
for txn in transactions:
    txn_id, txn_type, symbol, quantity, exec_price, amount, fx_rate, fx_rate_type, timestamp = txn
    
    # Calculate cash impact
    cash_impact = Decimal('0.00')
    if txn_type == 'DEPOSIT':
        cash_impact = Decimal(str(amount))
    elif txn_type == 'WITHDRAWAL':
        cash_impact = -Decimal(str(amount))
    elif txn_type == 'BUY':
        # BUY reduces cash - amount should be positive, so we negate it
        if fx_rate:
            # If FX involved, amount is in native currency, need to convert
            cash_impact = -Decimal(str(amount)) * Decimal(str(fx_rate))
        else:
            cash_impact = -Decimal(str(amount))
    elif txn_type == 'SELL':
        # SELL increases cash
        if fx_rate:
            cash_impact = Decimal(str(amount)) * Decimal(str(fx_rate))
        else:
            cash_impact = Decimal(str(amount))
    
    running_cash += cash_impact
    
    fx_str = f"{fx_rate:.4f}" if fx_rate else "N/A"
    print(f"{txn_id:<6} {txn_type:<12} {symbol or 'N/A':<8} {quantity or 0:<6} {exec_price or 0:<12.2f} {amount:<15,.2f} {fx_str:<10} {timestamp}")
    print(f"       Cash Impact: {cash_impact:+,.2f} | Running Balance: {running_cash:,.2f}")

print(f"\n{'='*80}")
print(f"FINAL CALCULATED CASH BALANCE: {base_currency} {running_cash:,.2f}")
print(f"ACTUAL CASH BALANCE (DB):      {base_currency} {cash_balance:,.2f}")
print(f"DIFFERENCE:                     {base_currency} {(cash_balance - running_cash):,.2f}")

# Check what the snapshot service would calculate
print(f"\n{'='*80}")
print("SNAPSHOT SERVICE CALCULATION (using the query from snapshot_service.py)")
print(f"{'='*80}")

# This mimics _get_historical_cash from snapshot_service.py
# BUT the original code has a bug - it doesn't properly handle the sign of amounts
cursor.execute("""
    SELECT
        transaction_type,
        amount,
        fx_rate,
        timestamp
    FROM portfolio_transaction
    WHERE portfolio_id = %s
    ORDER BY timestamp ASC;
""", (portfolio_id,))

all_txns = cursor.fetchall()
snapshot_cash = Decimal('0.00')

print("\nSnapshot Service Logic:")
print(f"{'Type':<12} {'Amount':<15} {'FX Rate':<10} {'Contribution':<15} {'Running Total':<15}")
print("-" * 75)

for txn_type, amount, fx_rate, timestamp in all_txns:
    contribution = Decimal('0.00')
    
    # The snapshot service uses this aggregation:
    # Sum amount where:
    # - transaction_type IN ['DEPOSIT', 'WITHDRAWAL']
    # - OR transaction_type='BUY' AND amount < 0
    # - OR transaction_type='SELL' AND amount > 0
    
    if txn_type in ['DEPOSIT', 'WITHDRAWAL']:
        contribution = Decimal(str(amount))
    elif txn_type == 'BUY' and Decimal(str(amount)) < 0:
        contribution = Decimal(str(amount))
    elif txn_type == 'SELL' and Decimal(str(amount)) > 0:
        contribution = Decimal(str(amount))
    
    snapshot_cash += contribution
    fx_str = f"{fx_rate:.4f}" if fx_rate else "N/A"
    print(f"{txn_type:<12} {amount:<15,.2f} {fx_str:<10} {contribution:+15,.2f} {snapshot_cash:15,.2f}")

print(f"\n{'='*80}")
print(f"SNAPSHOT SERVICE CALCULATED: {base_currency} {snapshot_cash:,.2f}")
print(f"ACTUAL CASH BALANCE (DB):    {base_currency} {cash_balance:,.2f}")
print(f"DIFFERENCE:                   {base_currency} {(cash_balance - snapshot_cash):,.2f}")

# Check latest snapshot
print(f"\n{'='*80}")
print("LATEST SNAPSHOT VALUES")
print(f"{'='*80}")

cursor.execute("""
    SELECT date, total_value, cash_balance, investment_value
    FROM portfolio_dailyportfoliosnapshot
    WHERE portfolio_id = %s
    ORDER BY date DESC
    LIMIT 1;
""", (portfolio_id,))
snapshot = cursor.fetchone()

if snapshot:
    snap_date, total_val, snap_cash, invest_val = snapshot
    print(f"\nSnapshot Date: {snap_date}")
    print(f"Total Value:   {base_currency} {total_val:,.2f}")
    print(f"Cash Balance:  {base_currency} {snap_cash:,.2f}")
    print(f"Investment:    {base_currency} {invest_val:,.2f}")
    print(f"\nThis cash balance ({snap_cash:,.2f}) is what's being used in snapshots!")

cursor.close()
conn.close()
