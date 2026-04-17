import pytest
from decimal import Decimal
from django.core.cache import cache
from django.utils import timezone
from portfolio.services import SnapshotService
from portfolio.models import DailyPortfolioSnapshot, Transaction
from portfolio.tests.factories import TransactionFactory
from stocks.tests.factories import StockFactory
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

    def test_historical_holdings_cache_invalidates_when_transaction_count_changes(self, portfolio):
        cache.clear()

        stock_a = StockFactory(symbol='CACH1', current_price=Decimal('10.00'), currency='PEN')
        stock_b = StockFactory(symbol='CACH2', current_price=Decimal('5.00'), currency='PEN')

        TransactionFactory(
            portfolio=portfolio,
            transaction_type='DEPOSIT',
            amount=Decimal('1000.00'),
        )
        first_buy = TransactionFactory(
            portfolio=portfolio,
            transaction_type='BUY',
            stock=stock_a,
            quantity=1,
        )

        snapshot_date = first_buy.timestamp.date()
        holdings = SnapshotService._get_historical_holdings(portfolio, snapshot_date)
        assert set(holdings.keys()) == {stock_a.id}

        second_buy = TransactionFactory(
            portfolio=portfolio,
            transaction_type='BUY',
            stock=stock_b,
            quantity=1,
        )
        Transaction.all_objects.filter(pk=second_buy.pk).update(timestamp=first_buy.timestamp)

        refreshed_holdings = SnapshotService._get_historical_holdings(portfolio, snapshot_date)
        assert set(refreshed_holdings.keys()) == {stock_a.id, stock_b.id}
