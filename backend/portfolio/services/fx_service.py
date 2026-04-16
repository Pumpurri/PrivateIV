from decimal import Decimal
import logging
from django.apps import apps
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


def _missing_fx_rate_error(snapshot_date, base_currency, quote_currency, rate_type, session):
    return ValidationError(
        f"Missing FX rate for {quote_currency}->{base_currency} on or before {snapshot_date} "
        f"(rate_type={rate_type}, session={session})"
    )


def get_fx_rate(snapshot_date, base_currency, quote_currency, rate_type='compra', session='cierre', require_rate=False):
    """Resolve FX for converting 1 quote unit to base units on a date, honoring rate type and session.

    - rate_type: 'compra' (USD->PEN), 'venta' (PEN->USD), 'mid'
    - session: 'intraday' or 'cierre'
    Fallbacks: exact date+session+type -> exact date other session -> latest prior same type (any session)
               -> latest prior other type (any session). If still missing, 1 for identical currencies else 1 with log.
    - require_rate: when True, raise ValidationError instead of returning the missing-rate fallback.
    """
    if not base_currency or not quote_currency:
        if require_rate:
            raise _missing_fx_rate_error(snapshot_date, base_currency, quote_currency, rate_type, session)
        return Decimal('1')

    if base_currency == quote_currency:
        return Decimal('1')

    try:
        FXRate = apps.get_model('portfolio', 'FXRate')

        # Helper query builder
        def find_rate(date_op, prefer_session=True, prefer_type=True):
            q = FXRate.objects.filter(
                base_currency=base_currency,
                quote_currency=quote_currency,
            )
            if date_op == 'exact':
                q = q.filter(date=snapshot_date)
            elif date_op == 'prior':
                q = q.filter(date__lt=snapshot_date)
            if prefer_type:
                q = q.filter(rate_type=rate_type)
            if prefer_session:
                q = q.filter(session=session)
            return q.order_by('-date').values_list('rate', flat=True).first()

        # 1) exact date, preferred session & type
        rate = find_rate('exact', prefer_session=True, prefer_type=True)
        if rate:
            return Decimal(rate)
        # 2) exact date, other session (same rate_type)
        rate = find_rate('exact', prefer_session=False, prefer_type=True)
        if rate:
            return Decimal(rate)
        # 2b) exact date, other rate_type (try preferred session first)
        rate = FXRate.objects.filter(
            date=snapshot_date,
            base_currency=base_currency,
            quote_currency=quote_currency,
            session=session
        ).exclude(rate_type=rate_type).order_by('-date').values_list('rate', flat=True).first()
        if rate:
            return Decimal(rate)
        # 2c) exact date, other rate_type any session
        rate = FXRate.objects.filter(
            date=snapshot_date,
            base_currency=base_currency,
            quote_currency=quote_currency,
        ).exclude(rate_type=rate_type).order_by('-date').values_list('rate', flat=True).first()
        if rate:
            return Decimal(rate)
        # 3) prior dates, preferred type any session
        rate = find_rate('prior', prefer_session=False, prefer_type=True)
        if rate:
            return Decimal(rate)
        # 4) prior dates, other type any session
        rate = find_rate('prior', prefer_session=False, prefer_type=False)
        if rate:
            return Decimal(rate)

        if require_rate:
            logger.error(
                f"Missing FX rate for {quote_currency}->{base_currency} on or before {snapshot_date}; failing strict lookup"
            )
            raise _missing_fx_rate_error(snapshot_date, base_currency, quote_currency, rate_type, session)
        logger.error(
            f"Missing FX rate for {quote_currency}->{base_currency} on or before {snapshot_date}; using 1.0"
        )
        return Decimal('1')
    except ValidationError:
        raise
    except Exception as e:
        logger.exception(f"FX resolution error: {quote_currency}->{base_currency} on {snapshot_date}: {e}")
        if require_rate:
            raise _missing_fx_rate_error(snapshot_date, base_currency, quote_currency, rate_type, session) from e
        return Decimal('1')
