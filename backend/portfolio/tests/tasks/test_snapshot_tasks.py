import pytest
from unittest.mock import patch
from portfolio.tasks import create_daily_snapshots
from portfolio.models import DailyPortfolioSnapshot
from users.tests.factories import UserFactory
from portfolio.models import Portfolio

@pytest.mark.django_db
class TestSnapshotTasks:
    @patch('portfolio.services.SnapshotService.create_daily_snapshot')
    def test_task_execution(self, mock_snapshot):
        create_daily_snapshots()
        assert mock_snapshot.call_count == Portfolio.objects.count()

    def test_real_snapshot_creation(self):
        from portfolio.models import Portfolio
        Portfolio.objects.all().delete()
        
        user = UserFactory()
        
        create_daily_snapshots()
        assert DailyPortfolioSnapshot.objects.count() == 1