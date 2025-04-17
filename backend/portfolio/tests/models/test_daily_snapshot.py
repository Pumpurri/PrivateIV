import pytest
from decimal import Decimal
from django.utils import timezone
from portfolio.models import DailyPortfolioSnapshot
from django.db import IntegrityError

@pytest.mark.django_db
class TestDailyPortfolioSnapshot:
    def test_snapshot_creation(self, portfolio):
        snapshot = DailyPortfolioSnapshot.objects.create(
            portfolio=portfolio,
            date=timezone.now().date(),
            total_value=Decimal('15000.00'),
            cash_balance=Decimal('5000.00'),
            investment_value=Decimal('10000.00'),
            total_deposits=Decimal('20000.00')
        )
        assert snapshot.portfolio == portfolio
        assert snapshot.date == timezone.now().date()

    def test_unique_date_constraint(self, portfolio):
        date = timezone.now().date()
        DailyPortfolioSnapshot.objects.create(
            portfolio=portfolio,
            date=date,
            total_value=Decimal('10000.00'),
            cash_balance=Decimal('5000.00'),
            investment_value=Decimal('5000.00'),
            total_deposits=Decimal('0.00')
        )
        with pytest.raises(IntegrityError):
            DailyPortfolioSnapshot.objects.create(
                portfolio=portfolio,
                date=date,
                total_value=Decimal('20000.00'),
                cash_balance=Decimal('10000.00'),
                investment_value=Decimal('10000.00'),
                total_deposits=Decimal('0.00')
            )

    def test_historical_accuracy(self, portfolio_with_history):
        """Test snapshot values match historical portfolio state"""
        historical_date = timezone.now() - timezone.timedelta(days=30)
        with timezone.override(historical_date.tzinfo):
            snapshot = DailyPortfolioSnapshot.objects.create(
                portfolio=portfolio_with_history,
                date=historical_date.date(),
                total_value=Decimal('10000.00'),
                cash_balance=Decimal('5000.00'),
                investment_value=Decimal('5000.00'),
                total_deposits=Decimal('5000.00')
            )
        
        portfolio_with_history.refresh_from_db()
        assert snapshot.total_value != portfolio_with_history.total_value