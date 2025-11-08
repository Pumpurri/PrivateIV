import os
from dotenv import load_dotenv
import psycopg2
from decimal import Decimal

load_dotenv()

db_url = os.getenv('DATABASE_PUBLIC_URL')
conn = psycopg2.connect(db_url)
cursor = conn.cursor()

print("=" * 80)
print("VERIFYING THE FIX LOGIC")
print("=" * 80)

portfolio_id = 1

# Get all transactions
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

print("\nTRANSACTIONS:")
print(f"{'ID':<6} {'Type':<12} {'Symbol':<8} {'Amount':<15} {'FX Rate':<10} {'Timestamp'}")
print("-" * 80)

cash_balance = Decimal('0.00')

for txn in transactions:
    txn_id, txn_type, symbol, quantity, exec_price, amount, fx_rate, fx_rate_type, timestamp = txn
    
    amount_dec = Decimal(str(amount)) if amount else Decimal('0.00')
    fx_rate_dec = Decimal(str(fx_rate)) if fx_rate else Decimal('1.00')
    
    print(f"{txn_id:<6} {txn_type:<12} {symbol or 'N/A':<8} {amount_dec:<15,.2f} {fx_rate_dec if fx_rate else 'N/A':<10} {timestamp}")
    
    # Apply the NEW logic from the fix
    cash_change = Decimal('0.00')
    
    if txn_type == 'DEPOSIT':
        cash_change = amount_dec
        print(f"       NEW LOGIC: DEPOSIT adds {amount_dec:,.2f} to cash")
        
    elif txn_type == 'WITHDRAWAL':
        cash_change = -amount_dec
        print(f"       NEW LOGIC: WITHDRAWAL removes {amount_dec:,.2f} from cash")
        
    elif txn_type == 'BUY':
        cash_in_base = amount_dec * fx_rate_dec
        cash_change = -cash_in_base
        print(f"       NEW LOGIC: BUY removes {amount_dec:,.2f} × {fx_rate_dec:.4f} = {cash_in_base:,.2f} from cash")
        
    elif txn_type == 'SELL':
        cash_in_base = amount_dec * fx_rate_dec
        cash_change = cash_in_base
        print(f"       NEW LOGIC: SELL adds {amount_dec:,.2f} × {fx_rate_dec:.4f} = {cash_in_base:,.2f} to cash")
    
    cash_balance += cash_change
    print(f"       Running Balance: {cash_balance:,.2f} PEN")
    print()

# Get actual portfolio cash
cursor.execute("""
    SELECT cash_balance, base_currency
    FROM portfolio_portfolio
    WHERE id = %s;
""", (portfolio_id,))
actual_cash, base_currency = cursor.fetchone()

print("=" * 80)
print("VERIFICATION RESULTS")
print("=" * 80)
print(f"\nCalculated Cash (using NEW fix): {base_currency} {cash_balance:,.2f}")
print(f"Actual Portfolio Cash (from DB): {base_currency} {actual_cash:,.2f}")
print(f"Difference:                       {base_currency} {abs(cash_balance - Decimal(str(actual_cash))):,.2f}")

if abs(cash_balance - Decimal(str(actual_cash))) < Decimal('0.01'):
    print("\n✅ PERFECT MATCH! The fix logic is CORRECT!")
else:
    print(f"\n❌ MISMATCH! There's still an issue.")
    print(f"\nLet me check if the issue is with how transactions store data...")
    
    # Let's look at the transaction_service.py to see how it stores amounts
    print("\nChecking transaction details more carefully...")
    for txn in transactions:
        txn_id, txn_type, symbol, quantity, exec_price, amount, fx_rate, fx_rate_type, timestamp = txn
        if txn_type in ['BUY', 'SELL'] and symbol:
            print(f"\n{txn_type} {quantity} {symbol}:")
            print(f"  executed_price: {exec_price}")
            print(f"  amount (stored): {amount}")
            print(f"  fx_rate: {fx_rate} ({fx_rate_type})")
            print(f"  Expected native amount: {quantity} × {exec_price} = {quantity * exec_price if exec_price and quantity else 'N/A'}")

cursor.close()
conn.close()
