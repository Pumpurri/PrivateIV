from unittest.mock import Mock

import pytest

from stocks import tasks


def test_active_companies_limit_live_fmp_requests_to_free_plan_symbols():
    assert [company['symbol'] for company in tasks.ACTIVE_COMPANIES] == tasks.FMP_FREE_PLAN_SYMBOLS
    assert any(company['symbol'] == 'IBM' for company in tasks.COMPANIES)
    assert not any(company['symbol'] == 'IBM' for company in tasks.ACTIVE_COMPANIES)
    assert any(company['symbol'] == 'BABA' for company in tasks.ACTIVE_COMPANIES)


def test_fetch_stock_prices_does_not_mark_refresh_when_all_upstreams_fail(monkeypatch):
    mark_refreshed = Mock()
    monkeypatch.setattr(tasks, 'update_local_stock_prices', lambda: False)
    monkeypatch.setattr(tasks, 'ACTIVE_COMPANIES', [{'symbol': 'AAPL'}])
    monkeypatch.setattr(tasks, 'fetch_data_for_companies', Mock(side_effect=RuntimeError('FMP failed')))
    monkeypatch.setattr(tasks.StockRefreshStatus, 'mark_refreshed', mark_refreshed)

    with pytest.raises(RuntimeError, match='all upstream calls failed'):
        tasks.fetch_stock_prices.run()

    mark_refreshed.assert_not_called()


def test_fetch_stock_prices_marks_refresh_when_any_upstream_succeeds(monkeypatch):
    mark_refreshed = Mock()
    update_us_stock_prices = Mock()
    fmp_fetch = Mock(side_effect=[
        RuntimeError('first batch failed'),
        [{'symbol': 'MSFT', 'price': 200.0}],
    ])
    monkeypatch.setattr(tasks, 'update_local_stock_prices', lambda: False)
    monkeypatch.setattr(tasks, 'ACTIVE_COMPANIES', [{'symbol': 'AAPL'}, {'symbol': 'MSFT'}])
    monkeypatch.setattr(tasks, 'fetch_data_for_companies', fmp_fetch)
    monkeypatch.setattr(tasks, 'update_us_stock_prices', update_us_stock_prices)
    monkeypatch.setattr(tasks.StockRefreshStatus, 'mark_refreshed', mark_refreshed)

    tasks.fetch_stock_prices.run()

    update_us_stock_prices.assert_called_once_with([{'symbol': 'MSFT', 'price': 200.0}])
    assert fmp_fetch.call_args_list[0].args == ('AAPL',)
    assert fmp_fetch.call_args_list[1].args == ('MSFT',)
    mark_refreshed.assert_called_once()


def test_fetch_eod_prices_does_not_mark_refresh_when_all_upstreams_fail(monkeypatch):
    mark_refreshed = Mock()
    monkeypatch.setattr(tasks, 'fetch_bvl_market_data', Mock(side_effect=RuntimeError('BVL failed')))
    monkeypatch.setattr(tasks, 'ACTIVE_COMPANIES', [{'symbol': 'AAPL'}])
    monkeypatch.setattr(tasks, 'fetch_data_for_companies', Mock(side_effect=RuntimeError('FMP failed')))
    monkeypatch.setattr(tasks.StockRefreshStatus, 'mark_refreshed', mark_refreshed)

    with pytest.raises(RuntimeError, match='all upstream calls failed'):
        tasks.fetch_eod_prices.run()

    mark_refreshed.assert_not_called()
