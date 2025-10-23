import pytest
from decimal import Decimal
from django.utils import timezone

from portfolio.services.fx_ingest_service import upsert_latest_from_bcrp
from portfolio.models import FXRate


@pytest.mark.django_db
def test_upsert_latest_from_bcrp_persists_compra_venta_mid(monkeypatch):
    # Monkeypatch client to return fixed series and rates
    def fake_resolve(mode, direction):
        today = timezone.now().date().strftime('%Y-%m-%d')
        if direction == 'compra':
            return ('PD04645PD', today, Decimal('3.750'))
        return ('PD04646PD', today, Decimal('3.800'))

    monkeypatch.setattr('portfolio.services.fx_ingest_service.bcrp.resolve_latest_auto', fake_resolve)

    out = upsert_latest_from_bcrp(mode='cierre')

    today = timezone.now().date()
    compra = FXRate.objects.get(date=today, rate_type='compra', session='cierre', base_currency='PEN', quote_currency='USD')
    venta = FXRate.objects.get(date=today, rate_type='venta', session='cierre', base_currency='PEN', quote_currency='USD')
    mid = FXRate.objects.get(date=today, rate_type='mid', session='cierre', base_currency='PEN', quote_currency='USD')

    assert compra.rate == Decimal('3.750')
    assert venta.rate == Decimal('3.800')
    assert mid.rate == Decimal('3.775')
    # Metadata
    assert compra.provider == 'BCRP'
    assert venta.provider == 'BCRP'
    assert mid.provider == 'BCRP'

