"""
Management command to create a test portfolio with extensive historical data.
Usage: python manage.py create_test_portfolio --username=<email>
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from datetime import timedelta
import random
import uuid

from users.models import CustomUser
from portfolio.models import Portfolio, Transaction
from portfolio.services.transaction_service import TransactionService
from portfolio.services.snapshot_service import SnapshotService
from stocks.models import Stock


class Command(BaseCommand):
    help = 'Create a test portfolio with extensive historical transaction data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            required=True,
            help='Email of the user to create portfolio for'
        )
        parser.add_argument(
            '--portfolio-name',
            type=str,
            default='Test Portfolio - Rich Data',
            help='Name for the test portfolio'
        )

    def handle(self, *args, **options):
        username = options['username']
        portfolio_name = options['portfolio_name']

        try:
            user = CustomUser.objects.get(email=username)
        except CustomUser.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User with email {username} not found'))
            return

        self.stdout.write(self.style.SUCCESS(f'Creating test portfolio for user: {user.email}'))

        # Create portfolio
        portfolio = Portfolio.objects.create(
            user=user,
            name=portfolio_name,
            description='Auto-generated test portfolio with extensive historical data',
            cash_balance=Decimal('0.00'),
            base_currency='PEN'
        )
        self.stdout.write(self.style.SUCCESS(f'Created portfolio: {portfolio.name} (ID: {portfolio.id})'))

        # Get or create test stocks
        stocks_data = [
            {'symbol': 'AAPL', 'name': 'Apple Inc.', 'price': Decimal('175.50'), 'currency': 'USD'},
            {'symbol': 'GOOGL', 'name': 'Alphabet Inc.', 'price': Decimal('140.25'), 'currency': 'USD'},
            {'symbol': 'MSFT', 'name': 'Microsoft Corp.', 'price': Decimal('380.00'), 'currency': 'USD'},
            {'symbol': 'TSLA', 'name': 'Tesla Inc.', 'price': Decimal('245.80'), 'currency': 'USD'},
            {'symbol': 'AMZN', 'name': 'Amazon.com Inc.', 'price': Decimal('155.30'), 'currency': 'USD'},
        ]

        stocks = []
        for data in stocks_data:
            stock, created = Stock.objects.get_or_create(
                symbol=data['symbol'],
                defaults={
                    'name': data['name'],
                    'current_price': data['price'],
                    'previous_close': data['price'] * Decimal('0.98'),
                    'currency': data['currency'],
                    'is_active': True
                }
            )
            if not created:
                # Update price if stock already exists
                stock.current_price = data['price']
                stock.previous_close = data['price'] * Decimal('0.98')
                stock.currency = data['currency']
                stock.is_active = True
                stock.save()
            stocks.append(stock)
            status = 'Created' if created else 'Updated'
            self.stdout.write(f'  {status} stock: {stock.symbol} @ ${stock.current_price}')

        # Generate historical transactions over the past 18 months
        self.stdout.write(self.style.SUCCESS('\nGenerating historical transactions...'))

        start_date = timezone.now() - timedelta(days=540)  # ~18 months
        current_date = start_date

        transaction_count = 0

        # Initial deposit
        self._create_transaction(
            portfolio=portfolio,
            transaction_type='DEPOSIT',
            amount=Decimal('50000.00'),
            timestamp=current_date
        )
        transaction_count += 1
        self.stdout.write(f'  Initial deposit: PEN 50,000.00')

        # Generate transactions over time
        while current_date < timezone.now():
            # Random interval between transactions (3-15 days)
            days_gap = random.randint(3, 15)
            current_date += timedelta(days=days_gap)

            if current_date > timezone.now():
                break

            # Decide transaction type
            action = random.choices(
                ['buy', 'sell', 'deposit', 'withdrawal'],
                weights=[50, 20, 15, 10],
                k=1
            )[0]

            try:
                if action == 'buy':
                    stock = random.choice(stocks)
                    quantity = random.randint(5, 50)
                    self._create_transaction(
                        portfolio=portfolio,
                        transaction_type='BUY',
                        stock=stock,
                        quantity=quantity,
                        timestamp=current_date
                    )
                    transaction_count += 1
                    self.stdout.write(f'  [{current_date.date()}] BUY {quantity} shares of {stock.symbol}')

                elif action == 'sell':
                    # Check if we have holdings to sell
                    holdings = portfolio.holdings.filter(is_active=True, quantity__gt=0)
                    if holdings.exists():
                        holding = random.choice(holdings)
                        # Sell between 25% and 75% of holding
                        max_sell = holding.quantity
                        quantity = random.randint(max(1, max_sell // 4), max(1, (max_sell * 3) // 4))
                        quantity = min(quantity, max_sell)  # Don't sell more than we have

                        self._create_transaction(
                            portfolio=portfolio,
                            transaction_type='SELL',
                            stock=holding.stock,
                            quantity=quantity,
                            timestamp=current_date
                        )
                        transaction_count += 1
                        self.stdout.write(f'  [{current_date.date()}] SELL {quantity} shares of {holding.stock.symbol}')

                elif action == 'deposit':
                    amount = Decimal(random.randint(1000, 20000))
                    self._create_transaction(
                        portfolio=portfolio,
                        transaction_type='DEPOSIT',
                        amount=amount,
                        timestamp=current_date
                    )
                    transaction_count += 1
                    self.stdout.write(f'  [{current_date.date()}] DEPOSIT PEN {amount:,.2f}')

                elif action == 'withdrawal':
                    # Only withdraw if we have sufficient cash
                    portfolio.refresh_from_db()
                    if portfolio.cash_balance > Decimal('5000.00'):
                        max_withdrawal = portfolio.cash_balance - Decimal('1000.00')
                        amount = Decimal(random.randint(500, min(10000, int(max_withdrawal))))
                        self._create_transaction(
                            portfolio=portfolio,
                            transaction_type='WITHDRAWAL',
                            amount=amount,
                            timestamp=current_date
                        )
                        transaction_count += 1
                        self.stdout.write(f'  [{current_date.date()}] WITHDRAWAL PEN {amount:,.2f}')

            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  Skipped transaction: {str(e)}'))
                continue

        # Generate historical snapshots
        self.stdout.write(self.style.SUCCESS('\nGenerating daily portfolio snapshots...'))
        snapshot_count = 0
        snapshot_date = start_date.date()
        end_date = timezone.now().date()

        while snapshot_date <= end_date:
            try:
                SnapshotService.create_daily_snapshot(portfolio, snapshot_date)
                snapshot_count += 1
                if snapshot_count % 30 == 0:  # Progress update every 30 snapshots
                    self.stdout.write(f'  Created {snapshot_count} snapshots...')
                snapshot_date += timedelta(days=1)
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  Failed to create snapshot for {snapshot_date}: {str(e)}'))
                snapshot_date += timedelta(days=1)
                continue

        self.stdout.write(self.style.SUCCESS(f'Created {snapshot_count} daily snapshots'))

        # Final summary
        portfolio.refresh_from_db()
        self.stdout.write(self.style.SUCCESS(f'\n{"="*60}'))
        self.stdout.write(self.style.SUCCESS(f'Portfolio Created Successfully!'))
        self.stdout.write(self.style.SUCCESS(f'{"="*60}'))
        self.stdout.write(f'Portfolio Name: {portfolio.name}')
        self.stdout.write(f'Portfolio ID: {portfolio.id}')
        self.stdout.write(f'Total Transactions: {transaction_count}')
        self.stdout.write(f'Total Snapshots: {snapshot_count}')
        self.stdout.write(f'Current Cash Balance: PEN {portfolio.cash_balance:,.2f}')
        self.stdout.write(f'Investment Value: PEN {portfolio.current_investment_value:,.2f}')
        self.stdout.write(f'Total Value: PEN {portfolio.total_value:,.2f}')
        self.stdout.write(f'\nActive Holdings:')
        for holding in portfolio.holdings.filter(is_active=True):
            self.stdout.write(f'  - {holding.stock.symbol}: {holding.quantity} shares @ PEN {holding.average_purchase_price:,.2f}')

        # Show realized P&L summary
        realized_pnls = portfolio.realized_pnls.all()
        if realized_pnls.exists():
            total_realized = sum(pnl.pnl for pnl in realized_pnls)
            self.stdout.write(f'\nRealized P&L:')
            self.stdout.write(f'  Total Realized Gains/Losses: PEN {total_realized:,.2f}')
            self.stdout.write(f'  Number of Realized Transactions: {realized_pnls.count()}')

    def _create_transaction(self, portfolio, transaction_type, amount=None, stock=None, quantity=None, timestamp=None):
        """Helper method to create a transaction using TransactionService"""
        transaction_data = {
            'portfolio': portfolio,
            'transaction_type': transaction_type,
            'idempotency_key': uuid.uuid4(),
        }

        if amount is not None:
            transaction_data['amount'] = amount

        if stock is not None:
            transaction_data['stock'] = stock

        if quantity is not None:
            transaction_data['quantity'] = quantity

        # Create the transaction
        txn = TransactionService.execute_transaction(transaction_data)

        # Update timestamp if specified (for historical data)
        if timestamp is not None:
            Transaction.all_objects.filter(pk=txn.pk).update(timestamp=timestamp)

        return txn
