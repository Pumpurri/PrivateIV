import pytest
from decimal import Decimal
from django.utils import timezone

from portfolio.models import Portfolio, Holding, FXRate
from stocks.models import Stock


@pytest.mark.django_db
def test_current_investment_value_uses_intraday_then_cierre(monkeypatch, user_factory):
    user = user_factory.create()
    p: Portfolio = user.portfolios.get(is_default=True)

    # USD stock
    s = Stock.objects.create(symbol='USDX', name='USD Asset', currency='USD', current_price=Decimal('10.00'))
    Holding.objects.create(portfolio=p, stock=s, quantity=1, average_purchase_price=Decimal('10.00'))

    today = timezone.now().date()
    # Provide both intraday and cierre compra
    FXRate.objects.create(date=today, base_currency='PEN', quote_currency='USD', rate=Decimal('3.60'), rate_type='compra', session='intraday')
    FXRate.objects.create(date=today, base_currency='PEN', quote_currency='USD', rate=Decimal('3.70'), rate_type='compra', session='cierre')

    # Monkeypatch localtime used in Portfolio._calculate_investment_value
    import portfolio.models.portfolio as port_mod

    class FakeDT:
        def __init__(self, hour, minute):
            self._t = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time())).replace(hour=hour, minute=minute)
        def time(self):
            return self._t.timetz()

    # 11:10 -> intraday
    monkeypatch.setattr(port_mod, 'localtime', lambda: FakeDT(11, 10))
    val = p.current_investment_value
    # 1 share * $10 * 3.60 = 36.00 PEN
    assert val == Decimal('36.00')

    # 14:00 -> cierre
    monkeypatch.setattr(port_mod, 'localtime', lambda: FakeDT(14, 0))
    val2 = p.current_investment_value
    # 1 * 10 * 3.70 = 37.00 PEN
    assert val2 == Decimal('37.00')

