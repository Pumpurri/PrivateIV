import pytest
from decimal import Decimal
from django.utils import timezone

from portfolio.services.snapshot_service import SnapshotService
from portfolio.models import FXRate, Transaction
from portfolio.tests.factories import TransactionFactory
from stocks.models import Stock


@pytest.mark.django_db
def test_snapshot_uses_cierre_compra_rate(user_factory):
    user = user_factory.create()
    p = user.portfolios.get(is_default=True)

    # One USD asset
    s = Stock.objects.create(symbol='USDC', name='USD Close', currency='USD', current_price=Decimal('10.00'))
    # Deposit and buy 1 share via service
    TransactionFactory(portfolio=p, transaction_type=Transaction.TransactionType.DEPOSIT, amount=Decimal('1000.00'))
    TransactionFactory(portfolio=p, transaction_type=Transaction.TransactionType.BUY, stock=s, quantity=1)

    today = timezone.now().date()
    # Provide cierre compra = 3.80
    FXRate.objects.create(date=today, base_currency='PEN', quote_currency='USD', rate=Decimal('3.80'), rate_type='compra', session='cierre')

    snap = SnapshotService.create_daily_snapshot(p, date=today)
    # 1 * $10 * 3.80 = 38.00 PEN investment
    assert snap.investment_value == Decimal('38.00')

