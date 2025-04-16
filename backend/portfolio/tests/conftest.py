import pytest
from decimal import Decimal
from django.db import transaction
from portfolio.tests.factories import PortfolioFactory, HoldingFactory, TransactionFactory
from users.tests.factories import UserFactory
from stocks.models import Stock
from portfolio.models import Portfolio, Holding, Transaction
from stocks.tests.factories import StockFactory
import logging

@pytest.fixture(scope="module")
def core_stock_data():
    return [
        {'symbol': 'AAPL', 'name': 'Apple Inc.', 'price': Decimal('189.84')},
        {'symbol': 'GOOGL', 'name': 'Alphabet Inc.', 'price': Decimal('136.22')},
        {'symbol': 'MSFT', 'name': 'Microsoft Corporation', 'price': Decimal('311.45')},
        {'symbol': 'AMZN', 'name': 'Amazon.com Inc.', 'price': Decimal('145.86')},
        {'symbol': 'TSLA', 'name': 'Tesla Inc.', 'price': Decimal('258.00')},
        {'symbol': 'META', 'name': 'Meta Platforms Inc.', 'price': Decimal('320.12')},
        {'symbol': 'NVDA', 'name': 'NVIDIA Corporation', 'price': Decimal('474.45')},
        {'symbol': 'NFLX', 'name': 'Netflix Inc.', 'price': Decimal('415.39')},
        {'symbol': 'JPM', 'name': 'JPMorgan Chase & Co.', 'price': Decimal('154.87')},
        {'symbol': 'BAC', 'name': 'Bank of America Corp.', 'price': Decimal('28.32')},
        {'symbol': 'V', 'name': 'Visa Inc.', 'price': Decimal('241.51')},
        {'symbol': 'MA', 'name': 'Mastercard Inc.', 'price': Decimal('379.77')},
        {'symbol': 'INTC', 'name': 'Intel Corporation', 'price': Decimal('34.22')},
    ]
    
@pytest.fixture
def stock():
    return StockFactory.create(
        symbol='TEST',
        name='Test Stock',
        current_price=Decimal('100.00')
    )

@pytest.fixture
def test_stocks(core_stock_data):
    return [
        StockFactory.create(
            symbol=data['symbol'],
            name=data['name'],
            current_price=data['price']
        ) for data in core_stock_data
    ]

@pytest.fixture
def portfolio(user_factory):
    user = user_factory.create()
    return user.portfolios.get(is_default=True)

@pytest.fixture
def user_factory():
    from users.tests.factories import UserFactory
    return UserFactory

@pytest.fixture
def funded_portfolio(portfolio):
    """Portfolio with initial cash balance"""
    portfolio.cash_balance = Decimal('10000.00')
    portfolio.save()
    return portfolio

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
def buy_transaction(funded_portfolio, stock):
    """Pre-configured buy transaction"""
    return TransactionFactory(
        portfolio=funded_portfolio,
        transaction_type='BUY',
        stock=stock,
        quantity=10,
        price=stock.current_price,
        amount=10 * stock.current_price
    )

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
        price=holding.stock.current_price,
        amount=5 * holding.stock.current_price
    )

@pytest.fixture
def aapl_holding(portfolio, test_stocks):
    return HoldingFactory(
        portfolio=portfolio,
        stock=test_stocks[0],  # AAPL
        quantity=100,
        average_purchase_price=150
    )

@pytest.fixture(autouse=True)
def cleanup_transactions():
    """Ensure clean state between tests"""
    yield
    try:
        with transaction.atomic():
            Transaction.objects.all().delete()
            Portfolio.objects.all().delete()
            Holding.objects.all().delete()
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Cleanup error: {str(e)}")