#!/usr/bin/env python
"""
Create a realistic portfolio with COHERENT data where everything makes sense.

Key principles:
1. Graph goes UP -> portfolio has GAINS
2. Graph goes DOWN -> portfolio has LOSSES
3. Sells at higher price than buy = GAINS
4. Sells at lower price than buy = LOSSES
5. Total value = cash + current holdings value
6. Snapshots accurately reflect transaction history
"""
import os
import django
import sys
from datetime import datetime, timedelta, date
from decimal import Decimal
from uuid import uuid4

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

def create_good_portfolio():
    """Create portfolio with realistic, coherent data"""

    print("🎯 Creating portfolio with GOOD, realistic data...\n")

    # Get user
    user = User.objects.filter(email='sjjs0805@gmail.com').first()
    if not user:
        print("❌ User sjjs0805@gmail.com not found!")
        return

    print(f"✅ Using user: {user.email}")

    # Delete old portfolio if exists
    Portfolio.objects.filter(user=user, name='Premium Growth Portfolio').delete()

    # Create portfolio 1 year ago
    start_date = timezone.now() - timedelta(days=365)
    portfolio = Portfolio.objects.create(
        user=user,
        name='Premium Growth Portfolio',
        description='Diversified portfolio with realistic gains and losses over 12 months',
        base_currency='PEN',
        created_at=start_date
    )
    print(f"✅ Created portfolio: {portfolio.name} (ID: {portfolio.id})\n")

    # Ensure stocks exist with reasonable prices
    stocks_data = {
        'AAPL': {'name': 'Apple Inc.', 'price': Decimal('175.00')},
        'GOOGL': {'name': 'Alphabet Inc.', 'price': Decimal('140.00')},
        'MSFT': {'name': 'Microsoft Corporation', 'price': Decimal('380.00')},
        'NVDA': {'name': 'NVIDIA Corporation', 'price': Decimal('500.00')},
        'TSLA': {'name': 'Tesla Inc.', 'price': Decimal('250.00')},
    }

    stocks = {}
    for symbol, data in stocks_data.items():
        stock, created = Stock.objects.get_or_create(
            symbol=symbol,
            defaults={'name': data['name'], 'currency': 'USD', 'current_price': data['price']}
        )
        stock.current_price = data['price']
        stock.save()
        stocks[symbol] = stock

    print("📝 Executing transaction timeline...\n")

    # MONTH 0: Initial deposit (more capital to account for FX rates)
    execute_txn(portfolio, {
        'date': start_date,
        'type': 'DEPOSIT',
        'amount': Decimal('500000.00')
    })
    print(f"  ✅ DEPOSIT S/ 500,000 (starting capital)\n")

    # MONTH 1 (30 days ago from start): First buys
    month1 = start_date + timedelta(days=30)

    # Buy AAPL at 150
    update_stock_price(stocks['AAPL'], Decimal('150.00'))
    execute_txn(portfolio, {
        'date': month1,
        'type': 'BUY',
        'stock': stocks['AAPL'],
        'quantity': 100
    })
    print(f"  ✅ BUY 100 AAPL @ S/ 150.00 = S/ 15,000")

    # Buy GOOGL at 120
    update_stock_price(stocks['GOOGL'], Decimal('120.00'))
    execute_txn(portfolio, {
        'date': month1 + timedelta(days=2),
        'type': 'BUY',
        'stock': stocks['GOOGL'],
        'quantity': 80
    })
    print(f"  ✅ BUY 80 GOOGL @ S/ 120.00 = S/ 9,600")

    # Buy MSFT at 350
    update_stock_price(stocks['MSFT'], Decimal('350.00'))
    execute_txn(portfolio, {
        'date': month1 + timedelta(days=5),
        'type': 'BUY',
        'stock': stocks['MSFT'],
        'quantity': 50
    })
    print(f"  ✅ BUY 50 MSFT @ S/ 350.00 = S/ 17,500\n")

    # MONTH 3 (150 days from start): More investments
    month3 = start_date + timedelta(days=90)

    # Buy NVDA at 450
    update_stock_price(stocks['NVDA'], Decimal('450.00'))
    execute_txn(portfolio, {
        'date': month3,
        'type': 'BUY',
        'stock': stocks['NVDA'],
        'quantity': 40
    })
    print(f"  ✅ BUY 40 NVDA @ S/ 450.00 = S/ 18,000")

    # Buy TSLA at 200
    update_stock_price(stocks['TSLA'], Decimal('200.00'))
    execute_txn(portfolio, {
        'date': month3 + timedelta(days=5),
        'type': 'BUY',
        'stock': stocks['TSLA'],
        'quantity': 60
    })
    print(f"  ✅ BUY 60 TSLA @ S/ 200.00 = S/ 12,000\n")

    # MONTH 6 (180 days): AAPL went UP - take profits (GAIN)
    month6 = start_date + timedelta(days=180)
    update_stock_price(stocks['AAPL'], Decimal('175.00'))  # Up from 150
    execute_txn(portfolio, {
        'date': month6,
        'type': 'SELL',
        'stock': stocks['AAPL'],
        'quantity': 50  # Sell half
    })
    print(f"  ✅ SELL 50 AAPL @ S/ 175.00 (bought @ 150) = GAIN S/ 1,250")

    # MONTH 7 (210 days): TSLA went DOWN - cut losses (LOSS)
    month7 = start_date + timedelta(days=210)
    update_stock_price(stocks['TSLA'], Decimal('180.00'))  # Down from 200
    execute_txn(portfolio, {
        'date': month7,
        'type': 'SELL',
        'stock': stocks['TSLA'],
        'quantity': 30  # Sell half
    })
    print(f"  ✅ SELL 30 TSLA @ S/ 180.00 (bought @ 200) = LOSS S/ -600\n")

    # MONTH 9 (270 days): GOOGL went UP - take profits (GAIN)
    month9 = start_date + timedelta(days=270)
    update_stock_price(stocks['GOOGL'], Decimal('140.00'))  # Up from 120
    execute_txn(portfolio, {
        'date': month9,
        'type': 'SELL',
        'stock': stocks['GOOGL'],
        'quantity': 40
    })
    print(f"  ✅ SELL 40 GOOGL @ S/ 140.00 (bought @ 120) = GAIN S/ 800")

    # MONTH 10 (300 days): NVDA went UP big - take profits (BIG GAIN)
    month10 = start_date + timedelta(days=300)
    update_stock_price(stocks['NVDA'], Decimal('500.00'))  # Way up from 450
    execute_txn(portfolio, {
        'date': month10,
        'type': 'SELL',
        'stock': stocks['NVDA'],
        'quantity': 20
    })
    print(f"  ✅ SELL 20 NVDA @ S/ 500.00 (bought @ 450) = GAIN S/ 1,000")

    # MONTH 11 (330 days): MSFT went UP - take profits (GAIN)
    month11 = start_date + timedelta(days=330)
    update_stock_price(stocks['MSFT'], Decimal('380.00'))  # Up from 350
    execute_txn(portfolio, {
        'date': month11,
        'type': 'SELL',
        'stock': stocks['MSFT'],
        'quantity': 25
    })
    print(f"  ✅ SELL 25 MSFT @ S/ 380.00 (bought @ 350) = GAIN S/ 750\n")

    # Update current prices for remaining holdings
    update_stock_price(stocks['AAPL'], Decimal('175.00'))
    update_stock_price(stocks['GOOGL'], Decimal('140.00'))
    update_stock_price(stocks['MSFT'], Decimal('380.00'))
    update_stock_price(stocks['NVDA'], Decimal('500.00'))
    update_stock_price(stocks['TSLA'], Decimal('250.00'))  # Recovered!

    portfolio.refresh_from_db()

    print("="*60)
    print("📊 PORTFOLIO SUMMARY")
    print("="*60)
    print(f"Cash Balance:      S/ {portfolio.cash_balance:>12,.2f}")
    print(f"Investment Value:  S/ {portfolio.current_investment_value:>12,.2f}")
    print(f"Total Value:       S/ {portfolio.total_value:>12,.2f}")
    print(f"Initial Deposit:   S/ {Decimal('100000.00'):>12,.2f}")
    print(f"Total Return:      S/ {portfolio.total_value - Decimal('100000.00'):>12,.2f}")
    print(f"Return %:          {((portfolio.total_value - Decimal('100000.00')) / Decimal('100000.00') * 100):>12.2f}%")
    print("="*60 + "\n")

    # Show realized P&L
    pnls = RealizedPNL.objects.filter(portfolio=portfolio)
    if pnls.exists():
        gains = sum(pnl.pnl for pnl in pnls if pnl.pnl > 0)
        losses = sum(pnl.pnl for pnl in pnls if pnl.pnl < 0)
        total_realized = sum(pnl.pnl for pnl in pnls)
        win_count = sum(1 for pnl in pnls if pnl.pnl > 0)
        loss_count = sum(1 for pnl in pnls if pnl.pnl < 0)

        print("💰 REALIZED P&L")
        print("="*60)
        print(f"Total Gains:       S/ {gains:>12,.2f} ({win_count} trades)")
        print(f"Total Losses:      S/ {losses:>12,.2f} ({loss_count} trades)")
        print(f"Net Realized:      S/ {total_realized:>12,.2f}")
        if gains + abs(losses) > 0:
            win_rate = gains / (gains + abs(losses)) * 100
            print(f"Win Rate:          {win_rate:>12.1f}%")
        print("="*60 + "\n")

    # Show holdings
    holdings = Holding.objects.filter(portfolio=portfolio, is_active=True)
    if holdings.exists():
        print("📦 CURRENT HOLDINGS")
        print("="*60)
        for holding in holdings:
            current_value = holding.quantity * holding.stock.current_price
            cost_basis = holding.quantity * holding.average_purchase_price
            unrealized = current_value - cost_basis
            unrealized_pct = (unrealized / cost_basis * 100) if cost_basis > 0 else 0

            print(f"{holding.stock.symbol:6} | {holding.quantity:3} shares @ S/ {holding.stock.current_price:7.2f}")
            print(f"       | Cost: S/ {holding.average_purchase_price:7.2f} | Value: S/ {current_value:10,.2f}")
            print(f"       | Unrealized: S/ {unrealized:10,.2f} ({unrealized_pct:+.1f}%)")
        print("="*60 + "\n")

    # Generate daily snapshots
    print("📈 Generating daily snapshots...")
    DailyPortfolioSnapshot.objects.filter(portfolio=portfolio).delete()

    current_date = start_date.date()
    end_date = timezone.now().date()
    count = 0

    while current_date <= end_date:
        try:
            SnapshotService.create_daily_snapshot(portfolio, current_date)
            count += 1
            if count % 50 == 0:
                print(f"  Generated {count} snapshots...")
        except:
            pass
        current_date += timedelta(days=1)

    print(f"✅ Generated {count} daily snapshots\n")

    # Show snapshot trend
    snaps = DailyPortfolioSnapshot.objects.filter(portfolio=portfolio).order_by('date')
    if snaps.count() > 2:
        first = snaps.first()
        middle = snaps[len(snaps)//2]
        last = snaps.last()

        print("📈 BALANCE HISTORY")
        print("="*60)
        print(f"Start  ({first.date}):  S/ {first.total_value:>12,.2f}")
        print(f"Middle ({middle.date}):  S/ {middle.total_value:>12,.2f}")
        print(f"Latest ({last.date}):  S/ {last.total_value:>12,.2f}")
        print(f"Growth: S/ {last.total_value - first.total_value:>12,.2f}")
        print("="*60 + "\n")

    print("✨ Portfolio created successfully!")
    print(f"   Portfolio ID: {portfolio.id}")
    print(f"   📊 Balances: http://localhost:5173/app/portfolios/{portfolio.id}/balances")
    print(f"   💰 Realized: http://localhost:5173/app/portfolios/{portfolio.id}/realized\n")

    return portfolio

def execute_txn(portfolio, data):
    """Execute a transaction"""
    trans_data = {
        'portfolio': portfolio,
        'transaction_type': data['type'],
        'idempotency_key': uuid4(),
        'timestamp': data['date']
    }

    if data['type'] in ['BUY', 'SELL']:
        trans_data['stock'] = data['stock']
        trans_data['quantity'] = data['quantity']
    else:
        trans_data['amount'] = data['amount']

    return TransactionService.execute_transaction(trans_data)

def update_stock_price(stock, price):
    """Update stock price"""
    stock.current_price = price
    stock.save()

if __name__ == '__main__':
    create_good_portfolio()
