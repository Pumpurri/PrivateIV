import pytest
from decimal import Decimal
from django.utils import timezone

from portfolio.services.fx_service import get_fx_rate


@pytest.mark.django_db
def test_get_fx_rate_base_equals_quote_returns_one():
    today = timezone.now().date()
    r = get_fx_rate(today, 'PEN', 'PEN', rate_type='compra', session='cierre')
    assert r == Decimal('1')

