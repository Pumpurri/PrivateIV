import pytest
from decimal import Decimal
from django.utils import timezone

from portfolio.tests.factories import TransactionFactory
from portfolio.models import Transaction
from portfolio.models import FXRate
from stocks.models import Stock


@pytest.mark.django_db
def test_buy_uses_venta_rate_for_cash():
    user_portfolio = None
    from users.tests.factories import UserFactory
    u = UserFactory()
    p = u.portfolios.get(is_default=True)

    # USD stock
    s = Stock.objects.create(symbol='BUYX', name='Buy FX', currency='USD', current_price=Decimal('10.00'))

    # Provide both intraday and cierre venta with same value for determinism
    today = timezone.now().date()
    FXRate.objects.create(date=today, base_currency='PEN', quote_currency='USD', rate=Decimal('3.50'), rate_type='venta', session='intraday')
    FXRate.objects.create(date=today, base_currency='PEN', quote_currency='USD', rate=Decimal('3.50'), rate_type='venta', session='cierre')

    # Deposit and buy 1 share
    TransactionFactory(portfolio=p, transaction_type=Transaction.TransactionType.DEPOSIT, amount=Decimal('1000.00'))
    cash_before = p.cash_balance
    TransactionFactory(portfolio=p, transaction_type=Transaction.TransactionType.BUY, stock=s, quantity=1)
    p.refresh_from_db()
    # Cash reduced by 10 * 3.5 = 35 PEN
    assert p.cash_balance == (cash_before - Decimal('35.00'))


@pytest.mark.django_db
def test_sell_uses_venta_rate_for_cash():
    from users.tests.factories import UserFactory
    u = UserFactory()
    p = u.portfolios.get(is_default=True)

    s = Stock.objects.create(symbol='SELLX', name='Sell FX', currency='USD', current_price=Decimal('10.00'))
    today = timezone.now().date()
    # Provide both compra and venta (we will assert SELL uses compra)
    FXRate.objects.create(date=today, base_currency='PEN', quote_currency='USD', rate=Decimal('3.55'), rate_type='compra', session='cierre')
    FXRate.objects.create(date=today, base_currency='PEN', quote_currency='USD', rate=Decimal('3.60'), rate_type='venta', session='cierre')

    TransactionFactory(portfolio=p, transaction_type=Transaction.TransactionType.DEPOSIT, amount=Decimal('1000.00'))
    TransactionFactory(portfolio=p, transaction_type=Transaction.TransactionType.BUY, stock=s, quantity=1)
    cash_before = p.cash_balance

    # Sell 1 share; expect + 10 * 3.55 = +35.50 PEN using compra
    TransactionFactory(portfolio=p, transaction_type=Transaction.TransactionType.SELL, stock=s, quantity=1)
    p.refresh_from_db()
    assert p.cash_balance == cash_before + Decimal('35.50')
