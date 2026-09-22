"""Replay immutable trades into base-currency positions and realized results."""

from decimal import Decimal, ROUND_HALF_UP

from portfolio.services.currency_service import convert_with_pen_per_usd_rate, normalize_currency


class TradeReplayError(ValueError):
    """A trade history cannot be reconstructed without making an assumption."""


def replay_trade_basis(transactions, base_currency):
    """Return ({stock_id: position}, {sell_transaction_id: realized_values}).

    Transactions must be ordered by timestamp and id. Cost basis follows the
    same per-share, two-decimal rounding as HoldingManager.process_purchase.
    """
    base_currency = normalize_currency(base_currency)
    positions = {}
    realized = {}

    for trade in transactions:
        if trade.transaction_type not in ('BUY', 'SELL'):
            continue
        if not trade.stock_id or not trade.stock or not trade.stock.currency:
            raise TradeReplayError(f"Trade {trade.pk} has no identifiable stock currency")
        if not trade.quantity or trade.quantity <= 0 or trade.executed_price is None or trade.executed_price <= 0:
            raise TradeReplayError(f"Trade {trade.pk} has incomplete quantity or price")

        native_currency = normalize_currency(trade.stock.currency)
        if native_currency != base_currency and (trade.fx_rate is None or trade.fx_rate <= 0):
            raise TradeReplayError(f"Trade {trade.pk} needs a recorded positive FX rate")
        price_base = convert_with_pen_per_usd_rate(
            trade.executed_price, native_currency, base_currency, trade.fx_rate
        )
        if price_base <= 0:
            raise TradeReplayError(f"Trade {trade.pk} converts to a zero cost basis")

        position = positions.get(trade.stock_id)
        if trade.transaction_type == 'BUY':
            if position is None:
                positions[trade.stock_id] = {
                    'quantity': trade.quantity,
                    'average_price': price_base,
                }
            else:
                quantity = position['quantity'] + trade.quantity
                cost = position['quantity'] * position['average_price'] + trade.quantity * price_base
                position['quantity'] = quantity
                position['average_price'] = (cost / quantity).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP
                )
            continue

        if position is None or position['quantity'] < trade.quantity:
            raise TradeReplayError(f"Trade {trade.pk} sells more shares than recorded buys")
        purchase_price = position['average_price']
        realized[trade.pk] = {
            'purchase_price': purchase_price,
            'sell_price': price_base,
            'pnl': ((price_base - purchase_price) * trade.quantity).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            ),
        }
        position['quantity'] -= trade.quantity
        if position['quantity'] == 0:
            del positions[trade.stock_id]

    return positions, realized
