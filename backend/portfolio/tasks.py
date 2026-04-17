# backend/portfolio/tasks.py
from celery import shared_task
from portfolio.services import SnapshotService
from portfolio.models import Portfolio
from portfolio.models.daily_snapshot import DailyPortfolioSnapshot
from django.utils import timezone
from datetime import timedelta
from portfolio.services.performance_service import PerformanceCalculator
from portfolio.services.fx_ingest_service import upsert_latest_from_bcrp
import logging

logger = logging.getLogger(__name__)

@shared_task
def create_daily_snapshots():
    for portfolio in Portfolio.objects.all():
        SnapshotService.create_daily_snapshot(portfolio)

@shared_task
def update_all_time_weighted_returns():
    now = timezone.now()
    portfolios = Portfolio.objects.filter(is_deleted=False)

    for portfolio in portfolios:
        try:
            result = PerformanceCalculator.calculate_all_time_weighted_return(
                portfolio=portfolio,
                end_date=now
            )
            portfolio.performance.time_weighted_return = result
            portfolio.performance.save(update_fields=['time_weighted_return'])
        except Exception as e:
            print(f"Failed to update TWR for {portfolio.id}: {e}")


@shared_task
def fx_ingest_latest_auto(mode='auto'):
    """Fetch latest USD->PEN from BCRP and upsert into FXRate.

    - mode: 'auto' | 'intraday' | 'cierre'
    Returns a dict with compra/venta used and the saved row details.
    """
    try:
        return upsert_latest_from_bcrp(mode=mode)
    except Exception:
        logger.exception("FX ingest task failed for mode=%s", mode)
        raise
