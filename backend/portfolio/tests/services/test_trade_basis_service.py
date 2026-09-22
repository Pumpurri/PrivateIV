from decimal import Decimal
from types import SimpleNamespace

import pytest

from portfolio.services.trade_basis_service import TradeReplayError, replay_trade_basis


def trade(pk, kind, quantity, price, currency='PEN', rate='4.000000', stock_id=1):
    return SimpleNamespace(
        pk=pk,
        transaction_type=kind,
        quantity=quantity,
        executed_price=Decimal(price),
        stock_id=stock_id,
        stock=SimpleNamespace(currency=currency),
        fx_rate=Decimal(rate) if rate is not None else None,
    )


def test_replay_converts_weighted_basis_and_realized_pnl_to_usd():
    positions, realized = replay_trade_basis([
        trade(1, 'BUY', 2, '40.00'),
        trade(2, 'BUY', 1, '80.00'),
        trade(3, 'SELL', 1, '100.00'),
    ], 'USD')

    assert positions == {1: {'quantity': 2, 'average_price': Decimal('13.33')}}
    assert realized == {3: {
        'purchase_price': Decimal('13.33'),
        'sell_price': Decimal('25.00'),
        'pnl': Decimal('11.67'),
    }}


def test_replay_resets_basis_after_full_sale():
    positions, realized = replay_trade_basis([
        trade(1, 'BUY', 1, '20.00'),
        trade(2, 'SELL', 1, '24.00'),
        trade(3, 'BUY', 1, '40.00'),
    ], 'USD')

    assert positions[1]['average_price'] == Decimal('10.00')
    assert realized[2]['pnl'] == Decimal('1.00')


@pytest.mark.parametrize('trades', [
    [trade(1, 'BUY', 1, '10.00', rate=None)],
    [trade(1, 'SELL', 1, '10.00')],
    [trade(1, 'BUY', 0, '10.00')],
])
def test_replay_rejects_incomplete_or_inconsistent_history(trades):
    with pytest.raises(TradeReplayError):
        replay_trade_basis(trades, 'USD')
