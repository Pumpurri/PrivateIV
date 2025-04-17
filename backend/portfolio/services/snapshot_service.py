from django.utils import timezone
from portfolio.models import DailyPortfolioSnapshot

class SnapshotService:
    @classmethod
    def create_daily_snapshot(cls, portfolio, date=None):
        """
        Creates or updates end-of-day portfolio snapshot.
        """
        snapshot_date = date or timezone.now().date()
        snapshot, created = DailyPortfolioSnapshot.objects.get_or_create(
            portfolio=portfolio,
            date=snapshot_date,
            defaults={
                'total_value': portfolio.total_value,
                'cash_balance': portfolio.cash_balance,
                'investment_value': portfolio.investment_value,
                'total_deposits': portfolio.performance.total_deposits
            }
        )
        if not created:
            snapshot.total_value = portfolio.total_value
            snapshot.cash_balance = portfolio.cash_balance
            snapshot.investment_value = portfolio.investment_value
            snapshot.total_deposits = portfolio.performance.total_deposits
            snapshot.save()
        return snapshot

