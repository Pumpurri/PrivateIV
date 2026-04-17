from decimal import Decimal, ROUND_HALF_UP

from portfolio.services.fx_service import get_current_fx_context, get_fx_rate


SUPPORTED_CURRENCIES = {'PEN', 'USD'}
DISPLAY_CURRENCY_NATIVE = 'NATIVE'


def quantize_money(value):
    return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def normalize_currency(value, *, default='PEN', allow_native=False):
    if value in (None, ''):
        return default

    normalized = str(value).strip().upper()
    if allow_native and normalized == DISPLAY_CURRENCY_NATIVE:
        return DISPLAY_CURRENCY_NATIVE
    if normalized in SUPPORTED_CURRENCIES:
        return normalized
    raise ValueError(f"Unsupported currency: {value}")


def get_snapshot_fx_context(*, snapshot_date=None, now=None, session=None):
    if snapshot_date is not None:
        return snapshot_date, session or 'cierre'
    fx_date, live_session = get_current_fx_context(now)
    return fx_date, session or live_session


def convert_amount(amount, from_currency, to_currency, *, snapshot_date=None, now=None, rate_type='mid', session=None, require_rate=False):
    amount = Decimal(amount or '0')
    from_currency = normalize_currency(from_currency)
    to_currency = normalize_currency(to_currency)

    if from_currency == to_currency:
        return quantize_money(amount)

    fx_date, fx_session = get_snapshot_fx_context(snapshot_date=snapshot_date, now=now, session=session)

    if from_currency == 'USD' and to_currency == 'PEN':
        rate = get_fx_rate(
            fx_date,
            'PEN',
            'USD',
            rate_type=rate_type,
            session=fx_session,
            require_rate=require_rate,
        )
        return quantize_money(amount * rate)

    if from_currency == 'PEN' and to_currency == 'USD':
        rate = get_fx_rate(
            fx_date,
            'PEN',
            'USD',
            rate_type=rate_type,
            session=fx_session,
            require_rate=require_rate,
        )
        return quantize_money(amount / rate)

    raise ValueError(f"Unsupported conversion: {from_currency}->{to_currency}")


def convert_with_pen_per_usd_rate(amount, from_currency, to_currency, pen_per_usd):
    amount = Decimal(amount or '0')
    from_currency = normalize_currency(from_currency)
    to_currency = normalize_currency(to_currency)

    if from_currency == to_currency:
        return quantize_money(amount)

    rate = Decimal(pen_per_usd or '0')
    if rate <= 0:
        raise ValueError("pen_per_usd must be positive")

    if from_currency == 'USD' and to_currency == 'PEN':
        return quantize_money(amount * rate)

    if from_currency == 'PEN' and to_currency == 'USD':
        return quantize_money(amount / rate)

    raise ValueError(f"Unsupported conversion: {from_currency}->{to_currency}")


def get_portfolio_reporting_currency(portfolio, requested=None):
    if requested not in (None, ''):
        return normalize_currency(requested)
    return normalize_currency(getattr(portfolio, 'reporting_currency', None) or getattr(portfolio, 'base_currency', 'PEN'))


def get_transaction_original_currency(transaction):
    if transaction.transaction_type in ('BUY', 'SELL'):
        return normalize_currency(getattr(transaction.stock, 'currency', None) or transaction.cash_currency or 'PEN')
    return normalize_currency(transaction.cash_currency or 'PEN')


def get_transaction_amount_in_currency(transaction, to_currency, *, use_counter_amount=False, snapshot_date=None):
    target_currency = normalize_currency(to_currency)

    if use_counter_amount and transaction.transaction_type == 'CONVERT' and transaction.counter_amount is not None:
        source_amount = Decimal(transaction.counter_amount or '0.00')
        source_currency = normalize_currency(transaction.counter_currency)
    else:
        source_amount = Decimal(transaction.amount or '0.00')
        source_currency = get_transaction_original_currency(transaction)

    if source_currency == target_currency:
        return quantize_money(source_amount)

    if transaction.fx_rate and {source_currency, target_currency} == {'PEN', 'USD'}:
        return convert_with_pen_per_usd_rate(
            source_amount,
            source_currency,
            target_currency,
            Decimal(transaction.fx_rate),
        )

    return convert_amount(
        source_amount,
        source_currency,
        target_currency,
        snapshot_date=snapshot_date,
        session='cierre',
    )
