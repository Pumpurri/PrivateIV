import pytest
from datetime import date
from decimal import Decimal
from django.core.cache import cache
from django.utils import timezone
from portfolio.models import FXRate
from portfolio.services import SnapshotService
from portfolio.models import DailyPortfolioSnapshot, Transaction
from portfolio.tests.factories import PortfolioFactory, TransactionFactory
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

    def test_historical_cash_reconstructs_usd_wallets_and_conversions(self, portfolio, set_fx_market_now):
        portfolio = PortfolioFactory(user=portfolio.user, is_default=False)
        trade_day = date(2026, 4, 16)
        snapshot_day = date(2026, 4, 17)

        FXRate.objects.create(
            date=trade_day,
            base_currency='PEN',
            quote_currency='USD',
            rate=Decimal('3.50'),
            rate_type='venta',
            session='cierre',
        )
        FXRate.objects.create(
            date=trade_day,
            base_currency='PEN',
            quote_currency='USD',
            rate=Decimal('3.45'),
            rate_type='mid',
            session='cierre',
        )
        FXRate.objects.create(
            date=snapshot_day,
            base_currency='PEN',
            quote_currency='USD',
            rate=Decimal('4.00'),
            rate_type='mid',
            session='cierre',
        )

        set_fx_market_now(trade_day)
        TransactionFactory(
            portfolio=portfolio,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal('350.00'),
            cash_currency='PEN',
        )
        TransactionFactory(
            portfolio=portfolio,
            transaction_type=Transaction.TransactionType.CONVERT,
            amount=Decimal('350.00'),
            cash_currency='PEN',
            counter_currency='USD',
        )

        historical_cash = SnapshotService._get_historical_cash(portfolio, snapshot_day)

        assert historical_cash == Decimal('400.00')
