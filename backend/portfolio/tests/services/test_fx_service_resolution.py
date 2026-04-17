from datetime import date, datetime, timezone as dt_timezone

import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.utils import timezone

from portfolio.services.fx_service import get_current_fx_context, get_fx_rate
from portfolio.models import FXRate


@pytest.mark.django_db
def test_fx_rate_priority_exact_session_and_type():
    today = timezone.now().date()
    # Exact today, cierre/compra
    FXRate.objects.create(
        date=today,
        base_currency='PEN', quote_currency='USD',
        rate=Decimal('3.500000'), rate_type='compra', session='cierre'
    )
    # Exact today, intraday/compra (should not be picked if asking cierre exact)
    FXRate.objects.create(
        date=today,
        base_currency='PEN', quote_currency='USD',
        rate=Decimal('3.400000'), rate_type='compra', session='intraday'
    )

    r = get_fx_rate(today, 'PEN', 'USD', rate_type='compra', session='cierre')
    assert r == Decimal('3.500000')


@pytest.mark.django_db
def test_fx_rate_fallback_other_session_then_prior():
    today = timezone.now().date()
    prior = today - timezone.timedelta(days=1)

    # Prior day cierre/compra
    FXRate.objects.create(
        date=prior, base_currency='PEN', quote_currency='USD',
        rate=Decimal('3.450000'), rate_type='compra', session='cierre'
    )
    # Today intraday/compra (should be used when asking cierre but exact not present)
    FXRate.objects.create(
        date=today, base_currency='PEN', quote_currency='USD',
        rate=Decimal('3.480000'), rate_type='compra', session='intraday'
    )

    r = get_fx_rate(today, 'PEN', 'USD', rate_type='compra', session='cierre')
    # Falls back to exact other session first
    assert r == Decimal('3.480000')

    # Remove intraday today to force prior day fallback
    FXRate.objects.filter(date=today, session='intraday').delete()
    r2 = get_fx_rate(today, 'PEN', 'USD', rate_type='compra', session='cierre')
    assert r2 == Decimal('3.450000')


@pytest.mark.django_db
def test_fx_rate_other_type_fallback():
    today = timezone.now().date()
    # No compra today or prior, but venta today exists
    FXRate.objects.create(
        date=today, base_currency='PEN', quote_currency='USD',
        rate=Decimal('3.600000'), rate_type='venta', session='cierre'
    )
    r = get_fx_rate(today, 'PEN', 'USD', rate_type='compra', session='cierre')
    assert r == Decimal('3.600000')


@pytest.mark.django_db
def test_fx_rate_missing_returns_one_for_non_strict_display():
    today = timezone.now().date()

    r = get_fx_rate(today, 'PEN', 'USD', rate_type='compra', session='cierre')

    assert r == Decimal('1')


@pytest.mark.django_db
def test_fx_rate_missing_raises_when_required():
    today = timezone.now().date()

    with pytest.raises(ValidationError, match="Missing FX rate"):
        get_fx_rate(today, 'PEN', 'USD', rate_type='compra', session='cierre', require_rate=True)


def test_current_fx_context_uses_market_timezone_when_app_timezone_is_utc(settings):
    settings.TIME_ZONE = 'UTC'
    settings.FX_MARKET_TIME_ZONE = 'America/Lima'

    fx_date, session = get_current_fx_context(
        datetime(2025, 9, 24, 16, 10, tzinfo=dt_timezone.utc)
    )
    assert fx_date == date(2025, 9, 24)
    assert session == 'intraday'

    next_fx_date, next_session = get_current_fx_context(
        datetime(2025, 9, 25, 2, 15, tzinfo=dt_timezone.utc)
    )
    assert next_fx_date == date(2025, 9, 24)
    assert next_session == 'cierre'
