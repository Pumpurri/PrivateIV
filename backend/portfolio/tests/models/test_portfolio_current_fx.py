from datetime import date, datetime, timezone as dt_timezone

import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError

from portfolio.models import Portfolio, Holding, FXRate
from stocks.models import Stock


@pytest.mark.django_db
def test_current_investment_value_uses_intraday_then_cierre(monkeypatch, user_factory):
    user = user_factory.create()
    p: Portfolio = user.portfolios.get(is_default=True)

    # USD stock
    s = Stock.objects.create(symbol='USDX', name='USD Asset', currency='USD', current_price=Decimal('10.00'))
    Holding.objects.create(portfolio=p, stock=s, quantity=1, average_purchase_price=Decimal('10.00'))

    today = date(2025, 9, 24)
    FXRate.objects.create(date=today, base_currency='PEN', quote_currency='USD', rate=Decimal('3.60'), rate_type='mid', session='intraday')
    FXRate.objects.create(date=today, base_currency='PEN', quote_currency='USD', rate=Decimal('3.70'), rate_type='mid', session='cierre')

    import portfolio.services.fx_service as fx_service

    # 16:10 UTC == 11:10 America/Lima -> intraday
    monkeypatch.setattr(fx_service.timezone, 'now', lambda: datetime(2025, 9, 24, 16, 10, tzinfo=dt_timezone.utc))
    val = p.current_investment_value
    assert val == Decimal('36.00')

    # 19:00 UTC == 14:00 America/Lima -> cierre
    monkeypatch.setattr(fx_service.timezone, 'now', lambda: datetime(2025, 9, 24, 19, 0, tzinfo=dt_timezone.utc))
    val2 = p.current_investment_value
    assert val2 == Decimal('37.00')


@pytest.mark.django_db
def test_current_investment_value_raises_when_fx_missing(monkeypatch, user_factory):
    user = user_factory.create()
    p: Portfolio = user.portfolios.get(is_default=True)

    s = Stock.objects.create(symbol='USDM', name='USD Missing FX', currency='USD', current_price=Decimal('10.00'))
    Holding.objects.create(portfolio=p, stock=s, quantity=1, average_purchase_price=Decimal('10.00'))

    import portfolio.services.fx_service as fx_service

    monkeypatch.setattr(fx_service.timezone, 'now', lambda: datetime(2025, 9, 24, 19, 0, tzinfo=dt_timezone.utc))

    with pytest.raises(ValidationError, match="Missing FX rate"):
        _ = p.current_investment_value


@pytest.mark.django_db
def test_total_cash_balance_raises_when_fx_missing(user_factory):
    user = user_factory.create()
    p: Portfolio = user.portfolios.get(is_default=True)
    p.base_currency = 'PEN'
    p.cash_balance = Decimal('0.00')
    p.cash_balance_usd = Decimal('25.00')
    p.save(update_fields=['base_currency', 'cash_balance', 'cash_balance_usd'])

    with pytest.raises(ValidationError, match="Missing FX rate"):
        p.get_total_cash_balance('PEN', snapshot_date=date(2025, 9, 24), session='cierre')
