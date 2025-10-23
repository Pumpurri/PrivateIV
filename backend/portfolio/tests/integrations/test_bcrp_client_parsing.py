import pytest
from decimal import Decimal

from portfolio.integrations import bcrp_client as bcrp


@pytest.mark.django_db
def test_bcrp_json_dataset_parsing(monkeypatch):
    payload = {
        "data": {"dataset": {"data": [["2025-09-22", 3.75], ["2025-09-23", 3.76]]}}
    }
    monkeypatch.setattr(bcrp, '_fetch', lambda url: '{"ok":true}')
    monkeypatch.setattr(bcrp, '_ensure_json', lambda raw: payload)
    d, v = bcrp.get_latest('PDXXXXX')
    assert d == '2025-09-23'
    assert isinstance(v, Decimal) and v == Decimal('3.76')


@pytest.mark.django_db
def test_bcrp_json_series_parsing(monkeypatch):
    payload = {
        "series": [{"data": [{"fecha": "22.Set.25", "valor": "3.75"}, {"fecha": "23.Sep.2025", "valor": "3.77"}]}]
    }
    monkeypatch.setattr(bcrp, '_fetch', lambda url: '{"ok":true}')
    monkeypatch.setattr(bcrp, '_ensure_json', lambda raw: payload)
    d, v = bcrp.get_latest('PDXXXXX')
    assert d == '2025-09-23'
    assert v == Decimal('3.77')


@pytest.mark.django_db
def test_bcrp_csv_parsing(monkeypatch):
    csv = "Fecha,Valor\n2025-09-22,3.70\n2025-09-23,3.72\n"
    # Force CSV path by making JSON raise
    monkeypatch.setattr(bcrp, '_fetch', lambda url: csv)
    monkeypatch.setattr(bcrp, '_ensure_json', lambda raw: (_ for _ in ()).throw(ValueError('not json')))
    d, v = bcrp.get_latest('PDXXXXX')
    assert d == '2025-09-23'
    assert v == Decimal('3.72')

