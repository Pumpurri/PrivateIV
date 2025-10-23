import pytest
from decimal import Decimal
from django.utils import timezone

from portfolio.services.fx_ingest_service import upsert_latest_from_bcrp
from portfolio.models import FXRate


@pytest.mark.django_db
def test_ingest_idempotent_and_session_separation(monkeypatch):
    today = timezone.now().date()

    # First, intraday returns
    def resolve_intraday(mode, direction):
        d = today.strftime('%Y-%m-%d')
        if direction == 'compra':
            return ('PD04643PD', d, Decimal('3.700'))
        return ('PD04644PD', d, Decimal('3.750'))

    monkeypatch.setattr('portfolio.services.fx_ingest_service.bcrp.resolve_latest_auto', resolve_intraday)
    out1 = upsert_latest_from_bcrp(mode='intraday')

    # Re-run (idempotent)
    out1b = upsert_latest_from_bcrp(mode='intraday')

    # Exactly one row per (date, pair, type, session)
    assert FXRate.objects.filter(date=today, rate_type='compra', session='intraday', base_currency='PEN', quote_currency='USD').count() == 1
    assert FXRate.objects.filter(date=today, rate_type='venta', session='intraday', base_currency='PEN', quote_currency='USD').count() == 1
    assert FXRate.objects.filter(date=today, rate_type='mid', session='intraday', base_currency='PEN', quote_currency='USD').count() == 1

    # Now cierre returns different values
    def resolve_cierre(mode, direction):
        d = today.strftime('%Y-%m-%d')
        if direction == 'compra':
            return ('PD04645PD', d, Decimal('3.710'))
        return ('PD04646PD', d, Decimal('3.760'))

    monkeypatch.setattr('portfolio.services.fx_ingest_service.bcrp.resolve_latest_auto', resolve_cierre)
    out2 = upsert_latest_from_bcrp(mode='cierre')

    # Both sessions should now exist
    c_intraday = FXRate.objects.get(date=today, rate_type='compra', session='intraday', base_currency='PEN', quote_currency='USD')
    v_intraday = FXRate.objects.get(date=today, rate_type='venta', session='intraday', base_currency='PEN', quote_currency='USD')
    m_intraday = FXRate.objects.get(date=today, rate_type='mid', session='intraday', base_currency='PEN', quote_currency='USD')

    c_cierre = FXRate.objects.get(date=today, rate_type='compra', session='cierre', base_currency='PEN', quote_currency='USD')
    v_cierre = FXRate.objects.get(date=today, rate_type='venta', session='cierre', base_currency='PEN', quote_currency='USD')
    m_cierre = FXRate.objects.get(date=today, rate_type='mid', session='cierre', base_currency='PEN', quote_currency='USD')

    assert c_intraday.rate == Decimal('3.700')
    assert v_intraday.rate == Decimal('3.750')
    assert m_intraday.rate == Decimal('3.725')

    assert c_cierre.rate == Decimal('3.710')
    assert v_cierre.rate == Decimal('3.760')
    assert m_cierre.rate == Decimal('3.735')

