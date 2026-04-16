import pytest
from django.test import Client


@pytest.mark.django_db
def test_healthz_returns_app_and_db_status():
    response = Client().get('/healthz/')

    assert response.status_code == 200
    assert response.json() == {
        'status': 'ok',
        'app': 'ok',
        'database': 'ok',
    }


def test_healthz_returns_503_when_database_check_fails(monkeypatch):
    class BrokenConnection:
        def cursor(self):
            raise RuntimeError('database unavailable')

    monkeypatch.setattr('TradeSimulator.health.connection', BrokenConnection())

    response = Client().get('/healthz/')

    assert response.status_code == 503
    assert response.json() == {
        'status': 'degraded',
        'app': 'ok',
        'database': 'error',
    }
