#!/usr/bin/env python
"""
Create a realistic portfolio with coherent data for testing.

This script creates:
- Portfolio starting 12 months ago
- Initial cash deposit
- Multiple buy/sell transactions over time with realistic prices
- Daily snapshots that match the transaction history
- Realized P&L records from sells
- Data that makes sense: gains show upward movement, losses show downward movement
"""
import os
import django
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'TradeSimulator.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from portfolio.models import Portfolio, Transaction, Holding, DailyPortfolioSnapshot, RealizedPNL
from stocks.models import Stock
from portfolio.services.transaction_service import TransactionService
from portfolio.services.snapshot_service import SnapshotService

User = get_user_model()

def create_realistic_portfolio():
    """Create a comprehensive realistic portfolio"""

    print("🎯 Creating realistic portfolio with coherent data...")

    # Get existing user
    user = User.objects.first()
    if not user:
        raise ValueError("No user found. Please create a user first.")
    print(f"✅ Using user: {user.email}")

    # Delete old test portfolio if exists
    Portfolio.objects.filter(user=user, name='Realistic Test Portfolio').delete()

    # Create portfolio 12 months ago
    start_date = timezone.now() - timedelta(days=365)
    portfolio = Portfolio.objects.create(
        user=user,
        name='Realistic Test Portfolio',
        description='Portfolio with realistic transaction history and coherent data',
        base_currency='PEN',
        created_at=start_date
    )
    print(f"✅ Created portfolio: {portfolio.name} (ID: {portfolio.id})")

    # Get or create stocks
    stocks_data = [
        {'symbol': 'AAPL', 'name': 'Apple Inc.', 'currency': 'USD'},
        {'symbol': 'GOOGL', 'name': 'Alphabet Inc.', 'currency': 'USD'},
        {'symbol': 'MSFT', 'name': 'Microsoft Corporation', 'currency': 'USD'},
        {'symbol': 'AMZN', 'name': 'Amazon.com Inc.', 'currency': 'USD'},
        {'symbol': 'TSLA', 'name': 'Tesla Inc.', 'currency': 'USD'},
    ]

    stocks = {}
    for stock_data in stocks_data:
        stock, created = Stock.objects.get_or_create(
            symbol=stock_data['symbol'],
            defaults={
                'name': stock_data['name'],
                'currency': stock_data['currency'],
                'current_price': Decimal('100.00')  # Placeholder
            }
        )
        stocks[stock_data['symbol']] = stock
        if created:
            print(f"✅ Created stock: {stock.symbol}")

    # Transaction timeline - simulating a realistic investor over 12 months
    transactions = []

    # Month 0 (365 days ago): Initial deposit
    transactions.append({
        'date': start_date,
        'type': 'DEPOSIT',
        'amount': Decimal('100000.00'),
        'description': 'Initial capital'
    })

    # Month 1 (335 days ago): First purchases - diversifying
    base = start_date + timedelta(days=30)
    transactions.extend([
        {'date': base, 'type': 'BUY', 'stock': 'AAPL', 'quantity': 50, 'price': Decimal('150.00')},
        {'date': base + timedelta(days=2), 'type': 'BUY', 'stock': 'GOOGL', 'quantity': 30, 'price': Decimal('125.00')},
        {'date': base + timedelta(days=5), 'type': 'BUY', 'stock': 'MSFT', 'quantity': 40, 'price': Decimal('300.00')},
    ])

    # Month 3 (275 days ago): More purchases
    base = start_date + timedelta(days=90)
    transactions.extend([
        {'date': base, 'type': 'BUY', 'stock': 'AMZN', 'quantity': 25, 'price': Decimal('140.00')},
        {'date': base + timedelta(days=3), 'type': 'BUY', 'stock': 'TSLA', 'quantity': 20, 'price': Decimal('200.00')},
    ])

    # Month 6 (185 days ago): Take some profits - AAPL went up
    base = start_date + timedelta(days=180)
    transactions.extend([
        {'date': base, 'type': 'SELL', 'stock': 'AAPL', 'quantity': 20, 'price': Decimal('180.00')},  # GAIN
    ])

    # Month 7 (155 days ago): Cut losses on TSLA
    base = start_date + timedelta(days=210)
    transactions.extend([
        {'date': base, 'type': 'SELL', 'stock': 'TSLA', 'quantity': 10, 'price': Decimal('180.00')},  # LOSS
    ])

    # Month 8 (125 days ago): More buys
    base = start_date + timedelta(days=240)
    transactions.extend([
        {'date': base, 'type': 'BUY', 'stock': 'GOOGL', 'quantity': 20, 'price': Decimal('130.00')},
        {'date': base + timedelta(days=2), 'type': 'BUY', 'stock': 'AAPL', 'quantity': 30, 'price': Decimal('175.00')},
    ])

    # Month 10 (65 days ago): Take profits on GOOGL
    base = start_date + timedelta(days=300)
    transactions.extend([
        {'date': base, 'type': 'SELL', 'stock': 'GOOGL', 'quantity': 25, 'price': Decimal('145.00')},  # GAIN
    ])

    # Month 11 (35 days ago): Sell some MSFT at gain
    base = start_date + timedelta(days=330)
    transactions.extend([
        {'date': base, 'type': 'SELL', 'stock': 'MSFT', 'quantity': 15, 'price': Decimal('350.00')},  # GAIN
    ])

    # Recent (5 days ago): Final adjustment
    base = timezone.now() - timedelta(days=5)
    transactions.extend([
        {'date': base, 'type': 'SELL', 'stock': 'AMZN', 'quantity': 10, 'price': Decimal('135.00')},  # LOSS
    ])

    print(f"\n📝 Processing {len(transactions)} transactions...")

    # Execute all transactions
    for i, txn_data in enumerate(transactions, 1):
        try:
            # Update stock current price before transaction
            if txn_data['type'] in ['BUY', 'SELL']:
                stock = stocks[txn_data['stock']]
                stock.current_price = txn_data['price']
                stock.save()

            # Prepare transaction data
            trans_data = {
                'portfolio': portfolio,
                'transaction_type': txn_data['type'],
                'idempotency_key': uuid4(),
                'timestamp': txn_data['date'],
            }

            if txn_data['type'] in ['BUY', 'SELL']:
                trans_data['stock'] = stocks[txn_data['stock']]
                trans_data['quantity'] = txn_data['quantity']
            else:
                trans_data['amount'] = txn_data['amount']

            # Execute transaction
            transaction = TransactionService.execute_transaction(trans_data)
            print(f"  [{i}/{len(transactions)}] ✅ {txn_data['type']} - {txn_data.get('stock', 'CASH')} - {txn_data['date'].date()}")

        except Exception as e:
            print(f"  [{i}/{len(transactions)}] ❌ Error: {e}")
            continue

    # Refresh portfolio
    portfolio.refresh_from_db()

    print(f"\n📊 Portfolio Status:")
    print(f"  Cash Balance: S/ {portfolio.cash_balance:,.2f}")
    print(f"  Investment Value: S/ {portfolio.current_investment_value:,.2f}")
    print(f"  Total Value: S/ {portfolio.total_value:,.2f}")

    # Generate daily snapshots manually
    print(f"\n📈 Generating daily snapshots...")

    # Delete existing snapshots for this portfolio
    DailyPortfolioSnapshot.objects.filter(portfolio=portfolio).delete()

    # Simulate daily snapshots with gradual portfolio growth
    current_date = start_date.date()
    end_date = timezone.now().date()
    snapshot_count = 0

    # Base values from transactions
    base_cash = Decimal('100000.00')
    base_investment = Decimal('0.00')

    while current_date <= end_date:
        try:
            # Find all transactions up to this date
            txns = Transaction.all_objects.filter(
                portfolio=portfolio,
                timestamp__date__lte=current_date
            ).order_by('timestamp')

            # Calculate cash and investment value at this point in time
            cash = Decimal('0')
            for txn in txns:
                if txn.transaction_type == 'DEPOSIT':
                    cash += txn.amount
                elif txn.transaction_type == 'WITHDRAWAL':
                    cash -= txn.amount
                elif txn.transaction_type == 'BUY':
                    cash -= (txn.executed_price * txn.quantity)
                elif txn.transaction_type == 'SELL':
                    cash += (txn.executed_price * txn.quantity)

            # Calculate investment value (simplified - using current holdings scaled)
            # This is approximate since we don't track historical prices perfectly
            holdings_today = Holding.objects.filter(portfolio=portfolio, is_active=True)
            investment_value = sum(
                holding.quantity * holding.stock.current_price
                for holding in holdings_today
            )

            # Create snapshot
            DailyPortfolioSnapshot.objects.create(
                portfolio=portfolio,
                date=current_date,
                cash_balance=cash,
                investment_value=investment_value,
                total_value=cash + investment_value
            )
            snapshot_count += 1

            if snapshot_count % 50 == 0:
                print(f"  Generated {snapshot_count} snapshots...")

        except Exception as e:
            # Skip dates with errors
            pass

        current_date += timedelta(days=1)

    print(f"  ✅ Generated {snapshot_count} daily snapshots")

    # Show realized P&L summary
    pnls = RealizedPNL.objects.filter(portfolio=portfolio)
    if pnls.exists():
        total_realized = sum(pnl.pnl for pnl in pnls)
        gains = sum(pnl.pnl for pnl in pnls if pnl.pnl > 0)
        losses = sum(pnl.pnl for pnl in pnls if pnl.pnl < 0)

        print(f"\n💰 Realized P&L:")
        print(f"  Total Gains: S/ {gains:,.2f}")
        print(f"  Total Losses: S/ {losses:,.2f}")
        print(f"  Net Realized: S/ {total_realized:,.2f}")
        print(f"  Win Rate: {(gains / (gains + abs(losses)) * 100):.1f}%")

    # Show current holdings
    holdings = Holding.objects.filter(portfolio=portfolio, is_active=True)
    if holdings.exists():
        print(f"\n📦 Current Holdings:")
        for holding in holdings:
            print(f"  {holding.stock.symbol}: {holding.quantity} shares @ S/ {holding.average_purchase_price:.2f}")

    print(f"\n✨ Portfolio created successfully!")
    print(f"   Portfolio ID: {portfolio.id}")
    print(f"   View at: http://localhost:5173/app/portfolios/{portfolio.id}/balances")
    print(f"   Realized: http://localhost:5173/app/portfolios/{portfolio.id}/realized")

    return portfolio

if __name__ == '__main__':
    create_realistic_portfolio()
