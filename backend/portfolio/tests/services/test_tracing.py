from contextlib import contextmanager
from decimal import Decimal

import pytest

from portfolio.models import Transaction
from portfolio.services import tracing
from portfolio.services.transaction_service import TransactionService
from users.tests.factories import UserFactory


def test_custom_spans_are_disabled_without_opt_in(monkeypatch, mocker):
    monkeypatch.delenv('DD_TRACE_ENABLED', raising=False)
    tracer = mocker.patch.object(tracing, '_dd_tracer')

    with tracing.span('portfolio.test') as active_span:
        assert active_span is None

    tracer.trace.assert_not_called()


def test_custom_spans_are_created_when_opted_in(monkeypatch, mocker):
    monkeypatch.setenv('DD_TRACE_ENABLED', 'true')
    tracer = mocker.patch.object(tracing, '_dd_tracer')

    with tracing.span('portfolio.test', resource='sample', tags={'count': 1}):
        pass

    tracer.trace.assert_called_once_with('portfolio.test', resource='sample')
    tracer.trace.return_value.__enter__.return_value.set_tag.assert_called_once_with('count', 1)


@pytest.mark.django_db
def test_transaction_spans_do_not_include_user_financial_data(monkeypatch):
    portfolio = UserFactory().portfolios.get(is_default=True)
    recorded = []

    @contextmanager
    def capture_span(name, **kwargs):
        recorded.append((name, kwargs))
        yield None

    monkeypatch.setattr('portfolio.services.transaction_service.span', capture_span)
    TransactionService.execute_transaction({
        'portfolio': portfolio,
        'transaction_type': Transaction.TransactionType.DEPOSIT,
        'amount': Decimal('123.45'),
        'cash_currency': 'PEN',
    })

    assert recorded == [
        ('transaction.execute', {}),
        ('transaction.process', {}),
        ('transaction.deposit', {}),
    ]
