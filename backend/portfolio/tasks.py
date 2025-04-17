# backend/portfolio/tasks.py
from celery import shared_task
from portfolio.services import SnapshotService
from portfolio.models import Portfolio

@shared_task
def create_daily_snapshots():
    for portfolio in Portfolio.objects.all():
        SnapshotService.create_daily_snapshot(portfolio)