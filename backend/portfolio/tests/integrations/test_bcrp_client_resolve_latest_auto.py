import pytest
from decimal import Decimal
from django.utils import timezone

from portfolio.integrations import bcrp_client as bcrp


@pytest.mark.django_db
def test_resolve_latest_auto_skips_stale_intraday(monkeypatch):
    """If intraday series returns a stale date, resolver should try cierre next."""
    today = timezone.now().date().strftime('%Y-%m-%d')
    yesterday = (timezone.now().date() - timezone.timedelta(days=1)).strftime('%Y-%m-%d')

    # Map series code to (date, value)
    series_map = {
        'PD04643PD': (yesterday, Decimal('3.700')),  # intraday compra (stale)
        'PD04645PD': (today,     Decimal('3.710')),  # cierre compra (fresh)
        'PD04639PD': (today,     Decimal('3.690')),  # fallback SBS
    }

    def fake_get_latest(code):
        d, v = series_map[code]
        return d, v

    # Force 'auto' to consider we are within intraday window (11:10)
    class FakeDT:
        @classmethod
        def now(cls, tz=None):
            from datetime import datetime
            return datetime(2025, 9, 24, 11, 10, 0)

    monkeypatch.setattr(bcrp, 'get_latest', fake_get_latest)
    monkeypatch.setattr(bcrp, 'datetime', FakeDT)
    monkeypatch.setattr(bcrp, 'ZoneInfo', None)

    used, d, v = bcrp.resolve_latest_auto(mode='auto', direction='compra')
    # Should skip PD04643PD (stale) and select PD04645PD
    assert used == 'PD04645PD'
    assert d == today
    assert v == Decimal('3.710')

