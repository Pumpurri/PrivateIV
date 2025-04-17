import pytest
from decimal import Decimal
from django.utils import timezone
from portfolio.services import SnapshotService
from portfolio.models import DailyPortfolioSnapshot
from datetime import timedelta

@pytest.mark.django_db
class TestSnapshotService:
    def test_snapshot_creation(self, portfolio):
        snapshot = SnapshotService.create_daily_snapshot(portfolio)
        assert snapshot.total_value == portfolio.total_value
        assert snapshot.cash_balance == portfolio.cash_balance
        assert snapshot.investment_value == portfolio.investment_value

    def test_multiple_day_snapshots(self, portfolio):
        dates = [timezone.now() - timedelta(days=i) for i in range(3)]
        for day in dates:
            SnapshotService.create_daily_snapshot(portfolio, date=day.date())
        
        assert DailyPortfolioSnapshot.objects.count() == 3