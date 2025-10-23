from decimal import Decimal
from django.apps import apps
from django.utils import timezone
import logging

from portfolio.integrations import bcrp_client as bcrp

logger = logging.getLogger(__name__)


def upsert_latest_from_bcrp(mode: str = 'auto'):
    """Fetch latest USD↔PEN from BCRP and upsert FXRate for USD->PEN (base PEN, quote USD).

    Returns a dict with details for compra and venta, e.g.:
      {
        'compra': {'series': 'PD04645PD', 'date': '2025-09-23', 'rate': Decimal('3.750')},
        'venta':  {'series': 'PD04646PD', 'date': '2025-09-23', 'rate': Decimal('3.760')},
        'saved':  {'base_currency': 'PEN', 'quote_currency': 'USD', 'date': '2025-09-23', 'rate': Decimal('3.750')}
      }

    Note: Current FXRate schema stores a single rate per (date, base, quote). We persist the 'compra'
    rate for USD->PEN conversions used in valuations. If you want to persist both compra/venta, extend
    the schema with a rate_type field.
    """
    FXRate = apps.get_model('portfolio', 'FXRate')

    out = {'compra': None, 'venta': None, 'saved': None}

    # Resolve latest compra (USD->PEN) and venta (PEN->USD)
    comp_series, comp_date, comp_rate = bcrp.resolve_latest_auto(mode=mode, direction='compra')
    out['compra'] = {'series': comp_series, 'date': comp_date, 'rate': comp_rate}

    ven_series, ven_date, ven_rate = bcrp.resolve_latest_auto(mode=mode, direction='venta')
    out['venta'] = {'series': ven_series, 'date': ven_date, 'rate': ven_rate}

    # Determine session from series or mode
    def session_from(series_code: str) -> str:
        if series_code in ("PD04643PD", "PD04644PD"):
            return 'intraday'
        if series_code in ("PD04645PD", "PD04646PD"):
            return 'cierre'
        # fallback based on mode/time will be acceptable
        return 'intraday' if mode == 'intraday' else 'cierre'

    comp_session = session_from(comp_series)
    ven_session = session_from(ven_series)

    ts = timezone.now()
    # Persist compra
    obj_c, _ = FXRate.objects.update_or_create(
        date=comp_date,
        base_currency='PEN',
        quote_currency='USD',
        rate_type='compra',
        session=comp_session,
        defaults={
            'rate': comp_rate,
            'provider': 'BCRP',
            'source_series': comp_series,
            'fetched_at': ts,
            'notes': ''
        }
    )
    # Persist venta
    obj_v, _ = FXRate.objects.update_or_create(
        date=ven_date,
        base_currency='PEN',
        quote_currency='USD',
        rate_type='venta',
        session=ven_session,
        defaults={
            'rate': ven_rate,
            'provider': 'BCRP',
            'source_series': ven_series,
            'fetched_at': ts,
            'notes': ''
        }
    )

    # Persist mid = average(compra, venta)
    try:
        mid_rate = (comp_rate + ven_rate) / Decimal('2')
        obj_m, _ = FXRate.objects.update_or_create(
            date=comp_date if comp_date == ven_date else comp_date,
            base_currency='PEN',
            quote_currency='USD',
            rate_type='mid',
            session=comp_session if comp_session == ven_session else comp_session,
            defaults={
                'rate': mid_rate,
                'provider': 'BCRP',
                'source_series': f"{comp_series}+{ven_series}",
                'fetched_at': ts,
                'notes': 'mid=(compra+venta)/2'
            }
        )
        mid_info = {'date': obj_m.date, 'session': obj_m.session, 'rate': obj_m.rate}
    except Exception as e:
        logger.warning(f"Failed to persist mid FX rate: {e}")
        mid_info = None

    out['saved'] = {
        'compra': {'date': comp_date, 'session': comp_session, 'rate': comp_rate},
        'venta': {'date': ven_date, 'session': ven_session, 'rate': ven_rate},
        'mid': mid_info,
    }
    return out
