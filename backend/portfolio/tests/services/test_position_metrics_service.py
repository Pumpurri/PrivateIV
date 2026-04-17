from datetime import date, datetime, timezone as datetime_timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from portfolio.models import FXRate, Transaction
from portfolio.services.position_metrics_service import get_holding_metrics, get_quote_metrics
from portfolio.tests.factories import HoldingFactory, PortfolioFactory
from stocks.tests.factories import StockFactory


pytestmark = pytest.mark.django_db


def _seed_mid_fx(snapshot_date, rate):
    FXRate.objects.create(
        date=snapshot_date,
        base_currency='PEN',
        quote_currency='USD',
        rate=Decimal(rate),
        rate_type='mid',
        session='cierre',
    )


def _create_buy_transaction(*, portfolio, stock, quantity, amount, fx_rate, timestamp):
    transaction = Transaction(
        portfolio=portfolio,
        transaction_type=Transaction.TransactionType.BUY,
        stock=stock,
        quantity=quantity,
        amount=Decimal(amount),
        executed_price=Decimal(amount) / Decimal(quantity),
        fx_rate=Decimal(fx_rate),
        fx_rate_type='venta',
        idempotency_key=uuid4(),
    )
    transaction._created_by_service = True
    transaction.save()
    Transaction.all_objects.filter(pk=transaction.pk).update(timestamp=timestamp)


def test_quote_metrics_use_previous_close_date_for_fx_baseline(set_quote_and_position_now):
    market_date = date(2026, 4, 21)
    set_quote_and_position_now(market_date)

    stock = StockFactory.create(
        symbol='NVDA',
        current_price=Decimal('10.00'),
        previous_close=Decimal('8.00'),
        previous_close_date=date(2026, 4, 17),
        currency='USD',
        is_local=False,
    )

    _seed_mid_fx(market_date, '3.50')
    _seed_mid_fx(date(2026, 4, 20), '3.45')
    _seed_mid_fx(date(2026, 4, 17), '3.40')

    metrics = get_quote_metrics(stock, 'PEN')

    assert metrics['display_price'] == Decimal('35.00')
    assert metrics['previous_close_price'] == Decimal('27.20')
    assert metrics['price_change'] == Decimal('7.80')
    assert metrics['price_change_percent'] == Decimal('28.68')


def test_holding_metrics_treat_previous_day_after_close_buy_as_current_session_open(set_quote_and_position_now):
    market_date = date(2026, 4, 17)
    set_quote_and_position_now(market_date)

    portfolio = PortfolioFactory()
    stock = StockFactory.create(
        symbol='AAL',
        current_price=Decimal('10.00'),
        previous_close=Decimal('8.00'),
        previous_close_date=date(2026, 4, 16),
        currency='USD',
        is_local=False,
    )
    holding = HoldingFactory.create(
        portfolio=portfolio,
        stock=stock,
        quantity=1,
        average_purchase_price=Decimal('36.00'),
    )

    _seed_mid_fx(market_date, '3.50')
    _seed_mid_fx(date(2026, 4, 16), '3.40')

    _create_buy_transaction(
        portfolio=portfolio,
        stock=stock,
        quantity=1,
        amount='10.00',
        fx_rate='3.600000',
        timestamp=datetime(2026, 4, 16, 21, 5, tzinfo=datetime_timezone.utc),
    )

    metrics = get_holding_metrics(holding)

    assert metrics['current_value'] == Decimal('35.00')
    assert metrics['cost_basis'] == Decimal('36.00')
    assert metrics['day_change'] == Decimal('-1.00')
    assert metrics['day_change_percentage'] == Decimal('-2.78')
    assert metrics['gain_loss'] == Decimal('-1.00')


def test_holding_metrics_treat_friday_after_close_buy_as_monday_open(set_quote_and_position_now):
    market_date = date(2026, 4, 20)
    set_quote_and_position_now(market_date)

    portfolio = PortfolioFactory()
    stock = StockFactory.create(
        symbol='DAL',
        current_price=Decimal('10.00'),
        previous_close=Decimal('8.00'),
        previous_close_date=date(2026, 4, 17),
        currency='USD',
        is_local=False,
    )
    holding = HoldingFactory.create(
        portfolio=portfolio,
        stock=stock,
        quantity=1,
        average_purchase_price=Decimal('36.00'),
    )

    _seed_mid_fx(market_date, '3.50')
    _seed_mid_fx(date(2026, 4, 17), '3.40')

    _create_buy_transaction(
        portfolio=portfolio,
        stock=stock,
        quantity=1,
        amount='10.00',
        fx_rate='3.600000',
        timestamp=datetime(2026, 4, 17, 21, 5, tzinfo=datetime_timezone.utc),
    )

    metrics = get_holding_metrics(holding)

    assert metrics['current_value'] == Decimal('35.00')
    assert metrics['day_change'] == Decimal('-1.00')
    assert metrics['day_change_percentage'] == Decimal('-2.78')
