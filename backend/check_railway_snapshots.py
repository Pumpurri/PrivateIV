"""
Script to check portfolio snapshots directly from Railway database
Run with: python check_railway_snapshots.py
Make sure you have the DATABASE_URL environment variable set
"""
import os
import psycopg2
from datetime import datetime

# Get database URL from environment
database_url = os.getenv('DATABASE_URL')
if not database_url:
    print("ERROR: DATABASE_URL environment variable not set")
    print("Set it with: export DATABASE_URL='your_railway_database_url'")
    exit(1)

print("Connecting to Railway database...")
try:
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()
    print("Connected successfully!\n")
except Exception as e:
    print(f"Connection error: {e}")
    exit(1)

# First, let's find the correct table names
print("Finding table names...")
cursor.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_name LIKE '%portfolio%' OR table_name LIKE '%snapshot%'
    ORDER BY table_name
""")
tables = cursor.fetchall()
print("Available tables:")
for table in tables:
    print(f"  - {table[0]}")
print()

# Check the columns of the snapshot table
print("Checking columns in portfolio_dailyportfoliosnapshot:")
cursor.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'portfolio_dailyportfoliosnapshot'
    ORDER BY ordinal_position
""")
columns = cursor.fetchall()
for col_name, col_type in columns:
    print(f"  - {col_name}: {col_type}")
print()

# Query all portfolios and their snapshots
print("=" * 100)
print("PORTFOLIO SNAPSHOTS ANALYSIS")
print("=" * 100)

# First, get all portfolios
cursor.execute("""
    SELECT id, name, user_id
    FROM portfolio_portfolio
    ORDER BY id
""")
portfolios = cursor.fetchall()

for portfolio_id, portfolio_name, user_id in portfolios:
    print(f"\n{'='*100}")
    print(f"PORTFOLIO {portfolio_id}: {portfolio_name} (User: {user_id})")
    print(f"{'='*100}\n")

    # Get snapshots for this portfolio
    cursor.execute("""
        SELECT
            date,
            total_value,
            cash_balance,
            investment_value
        FROM portfolio_dailyportfoliosnapshot
        WHERE portfolio_id = %s
        ORDER BY date
    """, (portfolio_id,))

    snapshots = cursor.fetchall()

    if not snapshots:
        print("No snapshots found for this portfolio\n")
        continue

    print(f"Total snapshots: {len(snapshots)}\n")
    print(f"{'Date':<12} | {'Total Value':>15} | {'Cash Balance':>15} | {'Invested':>15} | {'Change':>15} | {'% Change':>10}")
    print("-" * 110)

    prev_value = None
    for snap_date, total_value, cash_balance, invested in snapshots:
        change = ""
        pct_change = ""

        if prev_value is not None:
            diff = float(total_value) - float(prev_value)
            pct = (diff / float(prev_value) * 100) if prev_value != 0 else 0
            change = f"${diff:+,.2f}"
            pct_change = f"{pct:+.2f}%"

        print(f"{snap_date} | ${float(total_value):>14,.2f} | ${float(cash_balance):>14,.2f} | ${float(invested):>14,.2f} | {change:>15} | {pct_change:>10}")
        prev_value = total_value

    # Statistics
    values = [float(s[1]) for s in snapshots]
    if len(values) > 1:
        print(f"\n{'STATISTICS':^110}")
        print("-" * 110)
        print(f"Min Value: ${min(values):,.2f}")
        print(f"Max Value: ${max(values):,.2f}")
        print(f"Range: ${max(values) - min(values):,.2f}")
        print(f"First: ${values[0]:,.2f}")
        print(f"Last: ${values[-1]:,.2f}")
        print(f"Total Change: ${values[-1] - values[0]:+,.2f} ({((values[-1] - values[0]) / values[0] * 100):+.2f}%)")

        # Check for the October 29-30 drop
        oct_29_30_drop = False
        for i, (snap_date, total_value, _, _) in enumerate(snapshots):
            if snap_date.month == 10 and snap_date.day == 29:
                if i + 1 < len(snapshots):
                    next_date, next_value, _, _ = snapshots[i + 1]
                    if next_date.month == 10 and next_date.day == 30:
                        drop = float(total_value) - float(next_value)
                        drop_pct = (drop / float(total_value) * 100) if total_value != 0 else 0
                        print(f"\n⚠️  OCT 29-30 DROP DETECTED:")
                        print(f"   Oct 29: ${float(total_value):,.2f}")
                        print(f"   Oct 30: ${float(next_value):,.2f}")
                        print(f"   Drop: ${drop:,.2f} ({drop_pct:.2f}%)")
                        oct_29_30_drop = True

# Now check for transactions around Oct 29-30
print(f"\n\n{'='*100}")
print("TRANSACTIONS AROUND OCTOBER 29-30")
print(f"{'='*100}\n")

# First check transaction columns
cursor.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'portfolio_transaction'
    ORDER BY ordinal_position
""")
print("\nTransaction table columns:")
for col_name, col_type in cursor.fetchall():
    print(f"  - {col_name}: {col_type}")
print()

for portfolio_id, portfolio_name, user_id in portfolios:
    cursor.execute("""
        SELECT
            timestamp,
            transaction_type,
            quantity,
            amount,
            executed_price,
            fx_rate,
            stock_id
        FROM portfolio_transaction
        WHERE portfolio_id = %s
        AND timestamp::date BETWEEN '2024-10-28' AND '2024-10-31'
        ORDER BY timestamp
    """, (portfolio_id,))

    transactions = cursor.fetchall()

    if transactions:
        print(f"\nPortfolio {portfolio_id} ({portfolio_name}):")
        print(f"{'Timestamp':<20} | {'Type':<10} | {'Quantity':>10} | {'Price':>12} | {'Amount':>15} | {'FX Rate':>10} | {'Stock ID':>10}")
        print("-" * 110)

        for trans in transactions:
            timestamp, trans_type, quantity, amount, price, fx_rate, stock_id = trans
            fx_display = f"{float(fx_rate):.4f}" if fx_rate else 'N/A'
            print(f"{timestamp} | {trans_type:<10} | {quantity:>10} | ${float(price) if price else 0:>11,.2f} | ${float(amount):>14,.2f} | {fx_display:>10} | {stock_id if stock_id else 'N/A':>10}")

cursor.close()
conn.close()

print("\n" + "="*100)
print("Analysis complete!")
print("="*100)
