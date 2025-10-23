import pytest
from decimal import Decimal
from django.utils import timezone

from portfolio.services.fx_service import get_fx_rate
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

