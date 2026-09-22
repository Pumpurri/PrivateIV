from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from portfolio.models import Holding, RealizedPNL, Transaction
from portfolio.models.holding_snapshot import HoldingSnapshot
from portfolio.tests.factories import PortfolioFactory
from stocks.tests.factories import StockFactory


pytestmark = pytest.mark.django_db


def make_trade(portfolio, stock, kind, quantity, price, rate='4.000000'):
    trade = Transaction(
        portfolio=portfolio,
        stock=stock,
        transaction_type=kind,
        quantity=quantity,
        amount=Decimal(price) * quantity,
        executed_price=Decimal(price),
        fx_rate=Decimal(rate) if rate is not None else None,
    )
    trade._created_by_service = True
    trade.save()
    return trade


def seed_legacy_basis():
    portfolio = PortfolioFactory(base_currency='USD', reporting_currency='USD')
    stock = StockFactory(currency='PEN')
    make_trade(portfolio, stock, 'BUY', 2, '40.00')
    sell = make_trade(portfolio, stock, 'SELL', 1, '80.00')
    holding = Holding.objects.create(
        portfolio=portfolio, stock=stock, quantity=1, average_purchase_price=Decimal('40.00')
    )
    pnl = RealizedPNL.objects.create(
        portfolio=portfolio, transaction=sell, stock=stock, quantity=1,
        purchase_price=Decimal('40.00'), sell_price=Decimal('80.00'), pnl=Decimal('40.00'),
    )
    snapshot = HoldingSnapshot.objects.create(
        portfolio=portfolio, stock=stock, date=timezone.localdate(), quantity=1,
        average_purchase_price=Decimal('40.00'), total_value=Decimal('80.00'),
    )
    return portfolio, holding, pnl, snapshot


def test_repair_is_dry_run_then_idempotent_apply():
    portfolio, holding, pnl, snapshot = seed_legacy_basis()
    output = StringIO()

    call_command('repair_trade_basis', portfolio_id=portfolio.pk, stdout=output)
    assert 'Dry run only' in output.getvalue()
    holding.refresh_from_db()
    assert holding.average_purchase_price == Decimal('40.00')

    call_command('repair_trade_basis', portfolio_id=portfolio.pk, apply=True, stdout=StringIO())
    holding.refresh_from_db()
    pnl.refresh_from_db()
    snapshot.refresh_from_db()
    assert holding.average_purchase_price == Decimal('10.00')
    assert (pnl.purchase_price, pnl.sell_price, pnl.pnl) == (
        Decimal('10.00'), Decimal('20.00'), Decimal('10.00')
    )
    assert snapshot.average_purchase_price == Decimal('10.00')

    output = StringIO()
    call_command('repair_trade_basis', portfolio_id=portfolio.pk, apply=True, stdout=output)
    assert '0 holding(s), 0 realized record(s), 0 holding snapshot(s)' in output.getvalue()


def test_repair_rejects_quantity_mismatch_without_writing():
    portfolio, holding, pnl, snapshot = seed_legacy_basis()
    Holding.objects.filter(pk=holding.pk).update(quantity=2)

    with pytest.raises(CommandError, match='quantity differs'):
        call_command('repair_trade_basis', portfolio_id=portfolio.pk, apply=True, stdout=StringIO())

    pnl.refresh_from_db()
    snapshot.refresh_from_db()
    assert pnl.purchase_price == Decimal('40.00')
    assert snapshot.average_purchase_price == Decimal('40.00')


def test_repair_rejects_missing_fx_rate_without_writing():
    portfolio, holding, pnl, _ = seed_legacy_basis()
    Transaction.all_objects.filter(pk=pnl.transaction_id).update(fx_rate=None)

    with pytest.raises(CommandError, match='recorded positive FX rate'):
        call_command('repair_trade_basis', portfolio_id=portfolio.pk, apply=True, stdout=StringIO())

    holding.refresh_from_db()
    assert holding.average_purchase_price == Decimal('40.00')
