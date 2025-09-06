# backend/portfolio/tasks.py
from celery import shared_task
from portfolio.services import SnapshotService
from portfolio.models import Portfolio
from django.utils import timezone
from portfolio.services.performance_service import PerformanceCalculator

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
            result = PerformanceCalculator.calculate_time_weighted_return(
                portfolio=portfolio,
                start_date=now.replace(hour=0, minute=0, second=0, microsecond=0),
                end_date=now
            )
            portfolio.performance.time_weighted_return = result
            portfolio.performance.save(update_fields=['time_weighted_return'])
        except Exception as e:
            print(f"Failed to update TWR for {portfolio.id}: {e}")