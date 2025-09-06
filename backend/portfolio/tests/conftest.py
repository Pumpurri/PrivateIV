import pytest
from decimal import Decimal
from django.db import transaction
from portfolio.tests.factories import PortfolioFactory, HoldingFactory, TransactionFactory
from users.tests.factories import UserFactory
from stocks.models import Stock
from portfolio.models import Portfolio, Holding, Transaction
from stocks.tests.factories import StockFactory
from django.utils import timezone
from datetime import timezone as datetime_timezone
import logging
    
@pytest.fixture
def stock():
    return StockFactory.create(
        symbol='TEST',
        name='Test Stock',
        current_price=Decimal('100.00')
    )

@pytest.fixture
def portfolio(user_factory):
    user = user_factory.create()
    portfolio = user.portfolios.get(is_default=True)
    return portfolio

@pytest.fixture
def user_factory():
    from users.tests.factories import UserFactory
    return UserFactory

@pytest.fixture
def holding(portfolio, stock):
    """Basic holding fixture"""
    return HoldingFactory.create(
        portfolio=portfolio,
        stock=stock,
        quantity=100,
        average_purchase_price=Decimal('50.00')
    )

@pytest.fixture
def portfolio_with_holding(holding):
    """Portfolio with existing holding"""
    return {
        'portfolio': holding.portfolio,
        'holding': holding
    }

@pytest.fixture
def sell_transaction(portfolio_with_holding):
    """Pre-configured sell transaction"""
    portfolio = portfolio_with_holding['portfolio']
    holding = portfolio_with_holding['holding']
    
    return TransactionFactory(
        portfolio=portfolio,
        transaction_type='SELL',
        stock=holding.stock,
        quantity=5,
        executed_price=holding.stock.current_price,
        amount=5 * holding.stock.current_price
    )

@pytest.fixture
def portfolio_with_history(user_factory):
    """Portfolio with historical transactions and snapshots"""
    user = user_factory.create()
    portfolio = user.portfolios.get(is_default=True)
    
    # Create historical transactions
    dates = [
        timezone.now() - timezone.timedelta(days=30),
        timezone.now() - timezone.timedelta(days=15),
        timezone.now()
    ]
    
    stock = StockFactory(current_price=Decimal('100.00'))
    
    for idx, txn_date in enumerate(dates):
        with timezone.override(datetime_timezone.utc):
            TransactionFactory(
                portfolio=portfolio,
                transaction_type='DEPOSIT' if idx % 2 == 0 else 'BUY',
                amount=Decimal('5000.00') if idx % 2 == 0 else None,
                stock=stock if idx % 2 != 0 else None,
                quantity=50 if idx % 2 != 0 else None,
                timestamp=txn_date
            )
    
    return portfolio

@pytest.fixture
def real_loss_portfolio(user_factory):
    user = user_factory.create()
    portfolio = user.portfolios.get(is_default=True)

    stock = StockFactory(current_price=Decimal('50.00'))

    # Buy at $50 (real money out)
    TransactionFactory(
        portfolio=portfolio,
        transaction_type='BUY',
        stock=stock,
        quantity=100,
        executed_price=Decimal('50.00'),
        amount=Decimal('5000.00')
    )

    # Market drops
    stock.current_price = Decimal('40.00')
    stock.save()

    # Sell at loss
    TransactionFactory(
        portfolio=portfolio,
        transaction_type='SELL',
        stock=stock,
        quantity=100,
        executed_price=Decimal('40.00'),
        amount=Decimal('4000.00')
    )

    return portfolio
