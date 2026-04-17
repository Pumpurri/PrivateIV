from datetime import time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone


def _resolve_instrument_context(stock=None, *, is_local=None, currency=None):
    if stock is not None:
        if is_local is None:
            is_local = getattr(stock, 'is_local', False)
        if currency is None:
            currency = getattr(stock, 'currency', '')
    return bool(is_local), (currency or '').upper()


def _parse_market_time(value, default):
    if isinstance(value, time):
        return value

    if isinstance(value, str):
        try:
            hour, minute = value.strip().split(':', 1)
            return time(int(hour), int(minute))
        except (TypeError, ValueError):
            pass

    return default


def get_market_timezone(stock=None, *, is_local=None, currency=None):
    is_local, currency = _resolve_instrument_context(stock, is_local=is_local, currency=currency)

    if is_local:
        tz_name = getattr(settings, 'LOCAL_MARKET_TIME_ZONE', getattr(settings, 'FX_MARKET_TIME_ZONE', 'America/Lima'))
    elif currency == 'USD':
        tz_name = getattr(settings, 'US_MARKET_TIME_ZONE', 'America/New_York')
    else:
        tz_name = getattr(settings, 'LOCAL_MARKET_TIME_ZONE', getattr(settings, 'FX_MARKET_TIME_ZONE', 'America/Lima'))

    try:
        return ZoneInfo(tz_name)
    except Exception:
        return timezone.get_default_timezone()


def get_market_close_time(stock=None, *, is_local=None, currency=None):
    is_local, currency = _resolve_instrument_context(stock, is_local=is_local, currency=currency)

    if is_local:
        value = getattr(settings, 'LOCAL_MARKET_CLOSE_TIME', '16:00')
    elif currency == 'USD':
        value = getattr(settings, 'US_MARKET_CLOSE_TIME', '16:00')
    else:
        value = getattr(settings, 'LOCAL_MARKET_CLOSE_TIME', '16:00')

    return _parse_market_time(value, default=time(16, 0))


def get_market_datetime(value=None, stock=None, *, is_local=None, currency=None):
    value = value or timezone.now()
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_default_timezone())
    return value.astimezone(get_market_timezone(stock, is_local=is_local, currency=currency))


def get_market_date(stock=None, *, now=None, is_local=None, currency=None):
    return get_market_datetime(now, stock, is_local=is_local, currency=currency).date()


def previous_business_day(day):
    day = day - timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def next_business_day(day):
    day = day + timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def get_trade_effective_market_date(value, stock=None, *, is_local=None, currency=None):
    market_dt = get_market_datetime(value, stock, is_local=is_local, currency=currency)
    if market_dt.timetz().replace(tzinfo=None) >= get_market_close_time(stock, is_local=is_local, currency=currency):
        return next_business_day(market_dt.date())
    return market_dt.date()
