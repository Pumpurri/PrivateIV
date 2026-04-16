import logging
from unittest.mock import Mock

import pytest
import requests

from stocks.services import fetch_data_for_companies


def test_fetch_data_for_companies_requires_fmp_api_key(monkeypatch, caplog):
    monkeypatch.delenv('FMP_API', raising=False)

    with caplog.at_level(logging.ERROR), pytest.raises(RuntimeError, match='FMP_API'):
        fetch_data_for_companies('AAPL')

    assert any(
        getattr(record, 'provider', None) == 'fmp' and getattr(record, 'symbols', None) == 'AAPL'
        for record in caplog.records
    )


def test_fetch_data_for_companies_uses_timeout_and_keeps_key_out_of_url(monkeypatch):
    monkeypatch.setenv('FMP_API', 'secret-key')
    monkeypatch.setenv('FMP_API_TIMEOUT', '3.5')
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return [{'symbol': 'AAPL', 'price': 123.45}]

    def fake_get(url, params, timeout):
        captured['url'] = url
        captured['params'] = params
        captured['timeout'] = timeout
        return Response()

    monkeypatch.setattr('stocks.services.requests.get', fake_get)

    data = fetch_data_for_companies('AAPL')

    assert data == [{'symbol': 'AAPL', 'price': 123.45}]
    assert captured['url'] == 'https://financialmodelingprep.com/api/v3/quote/AAPL/'
    assert captured['params'] == {'apikey': 'secret-key'}
    assert captured['timeout'] == 3.5
    assert 'secret-key' not in captured['url']


def test_fetch_data_for_companies_raises_on_request_failure(monkeypatch, caplog):
    monkeypatch.setenv('FMP_API', 'secret-key')
    monkeypatch.setenv('FMP_API_TIMEOUT', '2')
    get = Mock(side_effect=requests.exceptions.Timeout('timed out'))
    monkeypatch.setattr('stocks.services.requests.get', get)

    with caplog.at_level(logging.ERROR), pytest.raises(RuntimeError, match='Error fetching current price'):
        fetch_data_for_companies('AAPL')

    assert get.call_args.kwargs['timeout'] == 2.0
    assert any(
        getattr(record, 'provider', None) == 'fmp' and getattr(record, 'symbols', None) == 'AAPL'
        for record in caplog.records
    )
