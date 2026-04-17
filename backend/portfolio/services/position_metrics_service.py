from decimal import Decimal, ROUND_HALF_UP

from portfolio.models import Transaction
from portfolio.services.currency_service import (
    DISPLAY_CURRENCY_NATIVE,
    convert_amount,
    get_portfolio_reporting_currency,
    get_transaction_amount_in_currency,
    normalize_currency,
)
from portfolio.services.fx_service import get_current_fx_context
from stocks.market import get_market_date, get_trade_effective_market_date


def _quantize_money(value):
    return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _quantize_percent(value):
    return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def get_position_market_date(stock, now=None):
    return get_market_date(stock, now=now)


def _resolve_target_currency(stock, portfolio, display_currency=None):
    if display_currency is None:
        return get_portfolio_reporting_currency(portfolio)

    normalized = normalize_currency(display_currency, allow_native=True)
    if normalized == DISPLAY_CURRENCY_NATIVE:
        return normalize_currency(getattr(stock, 'currency', None) or portfolio.base_currency)
    return normalized


def _convert_quote_amount(amount, stock, target_currency, *, snapshot_date=None, now=None, session=None):
    return convert_amount(
        amount or Decimal('0.00'),
        getattr(stock, 'currency', None) or target_currency,
        target_currency,
        snapshot_date=snapshot_date,
        now=now,
        session=session,
    )


def get_quote_metrics(stock, target_currency, now=None):
    target_currency = normalize_currency(target_currency)
    current_price_native = Decimal(stock.current_price or '0')
    current_fx_date, current_fx_session = get_current_fx_context(now)

    current_price_display = _convert_quote_amount(
        current_price_native,
        stock,
        target_currency,
        snapshot_date=current_fx_date,
        now=now,
        session=current_fx_session,
    )

    previous_close_native, previous_close_date = stock.get_previous_close_info(now=now)
    if previous_close_native is None or previous_close_date is None:
        return {
            'display_price': current_price_display,
            'previous_close_price': None,
            'price_change': None,
            'price_change_percent': None,
            'display_currency': target_currency,
        }

    previous_close_display = _convert_quote_amount(
        previous_close_native,
        stock,
        target_currency,
        snapshot_date=previous_close_date,
        session='cierre',
    )

    price_change = _quantize_money(current_price_display - previous_close_display)
    price_change_percent = None
    if previous_close_display != Decimal('0.00'):
        price_change_percent = _quantize_percent((price_change / previous_close_display) * Decimal('100'))

    return {
        'display_price': current_price_display,
        'previous_close_price': previous_close_display,
        'price_change': price_change,
        'price_change_percent': price_change_percent,
        'display_currency': target_currency,
    }


def _trade_transactions_for_holding(holding):
    prefetched = getattr(holding.portfolio, 'prefetched_transactions', None)
    if prefetched is not None:
        return [tx for tx in prefetched if tx.stock_id == holding.stock_id]

    return list(
        Transaction.objects.filter(
            portfolio=holding.portfolio,
            stock=holding.stock,
            transaction_type__in=[
                Transaction.TransactionType.BUY,
                Transaction.TransactionType.SELL,
            ],
        ).order_by('timestamp', 'id')
    )


def _consume_open_quantity(open_quantity, open_cost, quantity_to_consume):
    remaining = quantity_to_consume
    if open_quantity > 0 and remaining > 0:
        consumed = min(remaining, open_quantity)
        avg_cost = open_cost / Decimal(open_quantity)
        open_cost -= avg_cost * Decimal(consumed)
        open_quantity -= consumed
        remaining -= consumed
    return open_quantity, open_cost, remaining


def _fallback_cost_basis(holding, target_currency, *, now=None):
    base_cost = Decimal(holding.average_purchase_price or '0') * Decimal(holding.quantity or 0)
    if target_currency == holding.portfolio.base_currency:
        return _quantize_money(base_cost)
    return convert_amount(base_cost, holding.portfolio.base_currency, target_currency, now=now)


def get_holding_metrics(holding, now=None, display_currency=None):
    target_currency = _resolve_target_currency(holding.stock, holding.portfolio, display_currency=display_currency)
    quote_metrics = get_quote_metrics(holding.stock, target_currency, now=now)

    quantity = Decimal(holding.quantity or 0)
    display_price = quote_metrics['display_price']
    current_value = _quantize_money(display_price * quantity)

    market_today = get_position_market_date(holding.stock, now=now)
    open_quantity = 0
    open_cost = Decimal('0.00')
    overnight_quantity = 0
    today_open_quantity = 0
    today_open_cost = Decimal('0.00')
    future_open_quantity = 0
    future_open_cost = Decimal('0.00')

    trade_transactions = _trade_transactions_for_holding(holding)

    if not trade_transactions:
        overnight_quantity = int(holding.quantity or 0)
        cost_basis = _fallback_cost_basis(holding, target_currency, now=now)
    else:
        for tx in trade_transactions:
            tx_market_date = get_trade_effective_market_date(tx.timestamp, holding.stock)
            if tx_market_date is None:
                continue

            tx_quantity = int(tx.quantity or 0)
            if tx_quantity <= 0:
                continue

            tx_amount_target = get_transaction_amount_in_currency(
                tx,
                target_currency,
                snapshot_date=tx_market_date,
            )

            if tx.transaction_type == Transaction.TransactionType.BUY:
                open_quantity += tx_quantity
                open_cost += tx_amount_target
            elif tx.transaction_type == Transaction.TransactionType.SELL:
                open_quantity, open_cost, _ = _consume_open_quantity(
                    open_quantity,
                    open_cost,
                    tx_quantity,
                )

            if tx_market_date < market_today:
                if tx.transaction_type == Transaction.TransactionType.BUY:
                    overnight_quantity += tx_quantity
                elif tx.transaction_type == Transaction.TransactionType.SELL:
                    overnight_quantity = max(0, overnight_quantity - tx_quantity)
                continue

            if tx.transaction_type == Transaction.TransactionType.BUY:
                if tx_market_date > market_today:
                    future_open_quantity += tx_quantity
                    future_open_cost += tx_amount_target
                else:
                    today_open_quantity += tx_quantity
                    today_open_cost += tx_amount_target
            elif tx.transaction_type == Transaction.TransactionType.SELL:
                remaining = tx_quantity
                if tx_market_date > market_today:
                    future_open_quantity, future_open_cost, remaining = _consume_open_quantity(
                        future_open_quantity,
                        future_open_cost,
                        remaining,
                    )
                today_open_quantity, today_open_cost, remaining = _consume_open_quantity(
                    today_open_quantity,
                    today_open_cost,
                    remaining,
                )
                if remaining > 0:
                    overnight_quantity = max(0, overnight_quantity - remaining)

        actual_quantity = int(holding.quantity or 0)
        if open_quantity < actual_quantity:
            missing_quantity = actual_quantity - open_quantity
            total_fallback_cost_basis = _fallback_cost_basis(holding, target_currency, now=now)
            remaining_cost_basis = total_fallback_cost_basis - _quantize_money(open_cost)
            if remaining_cost_basis < Decimal('0.00'):
                remaining_cost_basis = Decimal('0.00')
            open_quantity += missing_quantity
            open_cost += remaining_cost_basis
            overnight_quantity += missing_quantity
        elif open_quantity > actual_quantity:
            overflow = open_quantity - actual_quantity
            open_quantity, open_cost, _ = _consume_open_quantity(open_quantity, open_cost, overflow)

        computed_day_quantity = overnight_quantity + today_open_quantity + future_open_quantity
        if computed_day_quantity < actual_quantity:
            overnight_quantity += actual_quantity - computed_day_quantity
        elif computed_day_quantity > actual_quantity:
            overflow = computed_day_quantity - actual_quantity
            if overnight_quantity > 0:
                reduce_overnight = min(overflow, overnight_quantity)
                overnight_quantity -= reduce_overnight
                overflow -= reduce_overnight
            if overflow > 0:
                today_open_quantity, today_open_cost, overflow = _consume_open_quantity(
                    today_open_quantity,
                    today_open_cost,
                    overflow,
                )
            if overflow > 0:
                future_open_quantity, future_open_cost, overflow = _consume_open_quantity(
                    future_open_quantity,
                    future_open_cost,
                    overflow,
                )

        cost_basis = _quantize_money(open_cost)

    gain_loss = _quantize_money(current_value - cost_basis)
    gain_loss_percentage = Decimal('0.00')
    if cost_basis != Decimal('0.00'):
        gain_loss_percentage = _quantize_percent((gain_loss / cost_basis) * Decimal('100'))

    day_change = None
    day_change_percentage = None
    previous_close_price = quote_metrics['previous_close_price']

    if display_price is not None:
        baseline = Decimal('0.00')
        total_change = Decimal('0.00')
        can_value_overnight = overnight_quantity == 0 or previous_close_price is not None

        if can_value_overnight:
            if overnight_quantity > 0:
                overnight_qty_decimal = Decimal(overnight_quantity)
                baseline += previous_close_price * overnight_qty_decimal
                total_change += (display_price - previous_close_price) * overnight_qty_decimal

            if today_open_quantity > 0:
                today_qty_decimal = Decimal(today_open_quantity)
                average_today_cost = today_open_cost / today_qty_decimal
                baseline += average_today_cost * today_qty_decimal
                total_change += (display_price - average_today_cost) * today_qty_decimal

            if future_open_quantity > 0:
                future_qty_decimal = Decimal(future_open_quantity)
                average_future_cost = future_open_cost / future_qty_decimal
                baseline += average_future_cost * future_qty_decimal
                total_change += (display_price - average_future_cost) * future_qty_decimal

            day_change = _quantize_money(total_change)
            if baseline != Decimal('0.00'):
                day_change_percentage = _quantize_percent((day_change / baseline) * Decimal('100'))

    return {
        'display_currency': target_currency,
        'display_price': display_price,
        'previous_close_price': previous_close_price,
        'price_change': quote_metrics['price_change'],
        'price_change_percent': quote_metrics['price_change_percent'],
        'current_value': current_value,
        'cost_basis': cost_basis,
        'gain_loss': gain_loss,
        'gain_loss_percentage': gain_loss_percentage,
        'day_change': day_change,
        'day_change_percentage': day_change_percentage,
    }
