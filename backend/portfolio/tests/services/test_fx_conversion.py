import pytest
from decimal import Decimal
from django.utils import timezone

from portfolio.models import Portfolio, Transaction
from portfolio.services.snapshot_service import SnapshotService
from portfolio.models.fx_rate import FXRate
from stocks.models import Stock
from portfolio.models import Holding
from portfolio.tests.factories import TransactionFactory


@pytest.mark.django_db
def test_mixed_currency_snapshot_uses_base_currency(user_factory):
    user = user_factory.create()
    p: Portfolio = user.portfolios.get(is_default=True)
    # Ensure base currency is PEN for this test
    p.base_currency = 'PEN'
    p.cash_balance = Decimal('0.00')
    p.save()

    # Create two stocks: one USD, one PEN
    usd = Stock.objects.create(symbol='USD1', name='USD Asset', currency='USD', current_price=Decimal('10.00'))
    pen = Stock.objects.create(symbol='PEN1', name='PEN Asset', currency='PEN', current_price=Decimal('10.00'))

    # Fund portfolio and buy 1 share each via TransactionService
    TransactionFactory(portfolio=p, transaction_type=Transaction.TransactionType.DEPOSIT, amount=Decimal('1000.00'))
    TransactionFactory(portfolio=p, transaction_type=Transaction.TransactionType.BUY, stock=usd, quantity=1)
    TransactionFactory(portfolio=p, transaction_type=Transaction.TransactionType.BUY, stock=pen, quantity=1)

    # FX: 1 USD = 3.50 PEN today
    today = timezone.now().date()
    FXRate.objects.create(date=today, base_currency='PEN', quote_currency='USD', rate=Decimal('3.50'))

    # Snapshot today
    snap = SnapshotService.create_daily_snapshot(p, date=today)

    # Expected base investment: PEN(10) + USD(10) * 3.5 = 45.00
    assert snap.investment_value == Decimal('45.00')
    # Cash is based on deposits (default portfolio may start with 10000, plus our 1000 deposit)
    # So total equals investment + cash
    assert snap.total_value == snap.investment_value + snap.cash_balance


@pytest.mark.django_db
def test_fx_fallback_uses_prior_rate(user_factory):
    user = user_factory.create()
    p: Portfolio = user.portfolios.get(is_default=True)
    p.base_currency = 'PEN'
    p.cash_balance = Decimal('0.00')
    p.save()

    usd = Stock.objects.create(symbol='USD2', name='USD Asset 2', currency='USD', current_price=Decimal('20.00'))
    TransactionFactory(portfolio=p, transaction_type=Transaction.TransactionType.DEPOSIT, amount=Decimal('1000.00'))
    TransactionFactory(portfolio=p, transaction_type=Transaction.TransactionType.BUY, stock=usd, quantity=1)

    today = timezone.now().date()
    prior = today - timezone.timedelta(days=1)
    # Only prior rate exists
    FXRate.objects.create(date=prior, base_currency='PEN', quote_currency='USD', rate=Decimal('4.00'))

    snap = SnapshotService.create_daily_snapshot(p, date=today)
    # Expect conversion using prior rate: 20 * 4 = 80
    assert snap.investment_value == Decimal('80.00')
    assert snap.total_value == snap.investment_value + snap.cash_balance
