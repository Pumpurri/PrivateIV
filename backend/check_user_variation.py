#!/usr/bin/env python
"""
Diagnostic script to check daily variation for user sjjs0805@gmail.com
"""
import os
from dotenv import load_dotenv
import psycopg2
from decimal import Decimal

load_dotenv()

def analyze_daily_variation():
    """Analyze portfolio for user sjjs0805@gmail.com"""

    db_url = os.getenv('DATABASE_PUBLIC_URL')

    try:
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()

        # Get user info
        print("=" * 80)
        print("USER INFORMATION")
        print("=" * 80)
        cursor.execute("""
            SELECT id, email, full_name
            FROM users_customuser
            WHERE email = 'sjjs0805@gmail.com';
        """)
        user = cursor.fetchone()
        if not user:
            print("❌ User not found!")
            return

        user_id, email, full_name = user
        print(f"User ID: {user_id}")
        print(f"Email: {email}")
        print(f"Name: {full_name}")

        # Get portfolio info
        print("\n" + "=" * 80)
        print("PORTFOLIO INFORMATION")
        print("=" * 80)
        cursor.execute("""
            SELECT id, name, base_currency, cash_balance, created_at, updated_at
            FROM portfolio_portfolio
            WHERE user_id = %s;
        """, (user_id,))
        portfolio = cursor.fetchone()
        if not portfolio:
            print("❌ Portfolio not found!")
            return

        portfolio_id, name, base_currency, cash_balance, created_at, updated_at = portfolio
        print(f"Portfolio ID: {portfolio_id}")
        print(f"Name: {name}")
        print(f"Base Currency: {base_currency}")
        print(f"Cash Balance: {base_currency} {cash_balance:,.2f}")

        # Get holdings with current values
        print("\n" + "=" * 80)
        print("CURRENT HOLDINGS")
        print("=" * 80)
        cursor.execute("""
            SELECT
                h.id,
                s.symbol,
                s.name,
                s.current_price,
                s.currency,
                h.quantity,
                h.average_purchase_price,
                h.updated_at
            FROM portfolio_holding h
            JOIN stocks_stock s ON h.stock_id = s.id
            WHERE h.portfolio_id = %s AND h.quantity > 0
            ORDER BY s.symbol;
        """, (portfolio_id,))
        holdings = cursor.fetchall()

        total_investment_value_pen = Decimal('0')
        if holdings:
            for holding in holdings:
                h_id, symbol, stock_name, current_price, currency, quantity, avg_price, h_updated = holding
                market_value_native = Decimal(str(current_price)) * Decimal(str(quantity))
                cost_basis = Decimal(str(avg_price)) * Decimal(str(quantity))

                # Get latest FX rate if needed
                market_value_pen = market_value_native
                if currency != base_currency:
                    cursor.execute("""
                        SELECT rate
                        FROM portfolio_fxrate
                        WHERE base_currency = %s AND quote_currency = %s
                        ORDER BY date DESC, fetched_at DESC
                        LIMIT 1;
                    """, (base_currency, currency))
                    fx_result = cursor.fetchone()
                    if fx_result:
                        fx_rate = Decimal(str(fx_result[0]))
                        market_value_pen = market_value_native * fx_rate

                total_investment_value_pen += market_value_pen

                pnl = market_value_native - cost_basis
                pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0

                print(f"\n{symbol} - {stock_name}")
                print(f"  Currency: {currency}")
                print(f"  Quantity: {quantity}")
                print(f"  Current Price: {currency} {current_price:,.2f}")
                print(f"  Market Value ({currency}): {market_value_native:,.2f}")
                print(f"  Market Value ({base_currency}): {market_value_pen:,.2f}")
                print(f"  Avg Purchase Price: {currency} {avg_price:,.2f}")
                print(f"  Cost Basis: {currency} {cost_basis:,.2f}")
                print(f"  P&L: {currency} {pnl:,.2f} ({pnl_pct:.2f}%)")
        else:
            print("No holdings found")

        total_portfolio_value = total_investment_value_pen + Decimal(str(cash_balance))
        print(f"\n--- CURRENT PORTFOLIO SUMMARY ---")
        print(f"Cash Balance: {base_currency} {cash_balance:,.2f}")
        print(f"Investment Value: {base_currency} {total_investment_value_pen:,.2f}")
        print(f"Total Portfolio Value: {base_currency} {total_portfolio_value:,.2f}")

        # Get daily snapshots
        print("\n" + "=" * 80)
        print("DAILY PORTFOLIO SNAPSHOTS (Last 10)")
        print("=" * 80)
        cursor.execute("""
            SELECT
                date,
                total_value,
                cash_balance,
                investment_value
            FROM portfolio_dailyportfoliosnapshot
            WHERE portfolio_id = %s
            ORDER BY date DESC
            LIMIT 10;
        """, (portfolio_id,))
        snapshots = cursor.fetchall()

        if snapshots:
            print(f"{'Date':<12} {'Total Value':>15} {'Cash':>15} {'Investment':>15}")
            print("-" * 60)
            for snap in snapshots:
                snap_date, total_val, cash_bal, invest_val = snap
                print(f"{snap_date} {total_val:>15,.2f} {cash_bal:>15,.2f} {invest_val:>15,.2f}")

            # Calculate daily variation
            print("\n" + "=" * 80)
            print("DAILY VARIATION CALCULATION")
            print("=" * 80)

            today_snap = snapshots[0] if snapshots else None
            yesterday_snap = snapshots[1] if len(snapshots) > 1 else None

            if today_snap and yesterday_snap:
                today_total = Decimal(str(today_snap[1]))
                yesterday_total = Decimal(str(yesterday_snap[1]))

                daily_change = today_total - yesterday_total
                daily_change_pct = (daily_change / yesterday_total * Decimal('100')) if yesterday_total > 0 else Decimal('0')

                print(f"\nYesterday ({yesterday_snap[0]}): {base_currency} {yesterday_total:,.2f}")
                print(f"Today ({today_snap[0]}): {base_currency} {today_total:,.2f}")
                print(f"\nDaily Change: {base_currency} {daily_change:,.2f}")
                print(f"Daily Change %: {daily_change_pct:.2f}%")

                # Check if this matches the reported value
                print(f"\n--- ANALYSIS ---")
                print(f"Reported: {base_currency} 2,166.89 (-17.70%)")
                print(f"Calculated: {base_currency} {daily_change:,.2f} ({daily_change_pct:.2f}%)")

                if abs(daily_change_pct) > 20:
                    print(f"\n⚠️  WARNING: Daily variation exceeds 20%!")
                    print(f"   This is extremely unusual for a single day.")

                    # Check for transactions on these dates
                    cursor.execute("""
                        SELECT
                            transaction_type,
                            s.symbol,
                            quantity,
                            amount,
                            timestamp
                        FROM portfolio_transaction t
                        LEFT JOIN stocks_stock s ON t.stock_id = s.id
                        WHERE t.portfolio_id = %s
                        AND t.timestamp::date IN (%s, %s)
                        ORDER BY t.timestamp DESC;
                    """, (portfolio_id, today_snap[0], yesterday_snap[0]))
                    recent_txs = cursor.fetchall()

                    if recent_txs:
                        print(f"\n   Recent transactions:")
                        for tx in recent_txs:
                            tx_type, symbol, qty, amt, ts = tx
                            print(f"   - [{ts}] {tx_type}: {symbol or 'N/A'} - Amount: {amt:,.2f}")
                    else:
                        print(f"\n   No transactions found on these dates")

                    # Check stock price changes for each holding
                    print(f"\n   Stock price changes between snapshots:")
                    if holdings:
                        for holding in holdings:
                            h_id, symbol, stock_name, current_price, currency, quantity, avg_price, h_updated = holding

                            # Get prices on both dates
                            cursor.execute("""
                                SELECT date, close
                                FROM stocks_stockprice
                                WHERE stock_id = (SELECT id FROM stocks_stock WHERE symbol = %s)
                                AND date IN (%s, %s)
                                ORDER BY date DESC;
                            """, (symbol, today_snap[0], yesterday_snap[0]))
                            price_history = cursor.fetchall()

                            if len(price_history) >= 2:
                                today_price = Decimal(str(price_history[0][1]))
                                yesterday_price = Decimal(str(price_history[1][1]))
                                price_change = today_price - yesterday_price
                                price_change_pct = (price_change / yesterday_price * 100) if yesterday_price > 0 else 0
                                print(f"   - {symbol}: {yesterday_price:.2f} → {today_price:.2f} ({price_change_pct:+.2f}%)")
                            else:
                                print(f"   - {symbol}: Insufficient price data")
        else:
            print("No snapshots found")

        # Get portfolio performance metrics
        print("\n" + "=" * 80)
        print("PORTFOLIO PERFORMANCE TABLE")
        print("=" * 80)
        cursor.execute("""
            SELECT
                total_value,
                daily_change,
                daily_change_percentage,
                total_pnl,
                total_pnl_percentage,
                total_deposits,
                total_withdrawals,
                updated_at
            FROM portfolio_portfolioperformance
            WHERE portfolio_id = %s;
        """, (portfolio_id,))
        performance = cursor.fetchone()
        if performance:
            total_value, daily_change, daily_change_pct, total_pnl, total_pnl_pct, total_deposits, total_withdrawals, perf_updated = performance
            print(f"Total Value: {base_currency} {total_value:,.2f}")
            print(f"Daily Change: {base_currency} {daily_change:,.2f} ({daily_change_pct:.2f}%)")
            print(f"Total P&L: {base_currency} {total_pnl:,.2f} ({total_pnl_pct:.2f}%)")
            print(f"Total Deposits: {base_currency} {total_deposits:,.2f}")
            print(f"Total Withdrawals: {base_currency} {total_withdrawals:,.2f}")
            print(f"Last Updated: {perf_updated}")

            print(f"\n--- CHECKING PORTFOLIO PERFORMANCE TABLE ---")
            print(f"Performance table shows daily change: {base_currency} {daily_change:,.2f} ({daily_change_pct:.2f}%)")
            print(f"Does this match the reported value?")
        else:
            print("No performance metrics found")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    analyze_daily_variation()
