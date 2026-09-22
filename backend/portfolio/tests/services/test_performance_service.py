import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone
from unittest.mock import patch
from portfolio.services.performance_service import PerformanceCalculator
from portfolio.tests.factories import TransactionFactory
from portfolio.models import Transaction

@pytest.mark.django_db
class TestPerformanceService:
    def test_time_weighted_return(self, portfolio_with_history):
        """Test Modified Dietz method with actual cash flows"""
        start_date = timezone.now() - timedelta(days=365)
        end_date = timezone.now()
        
        result = PerformanceCalculator.calculate_time_weighted_return(
            portfolio_with_history,
            start_date,
            end_date
        )
        
        assert isinstance(result, Decimal)
        assert result >= Decimal('-1.0000')
        assert result.is_finite()
        assert result.as_tuple().exponent >= -4  # 4 decimal places

    def test_zero_duration_return(self, portfolio):
        """Test edge case where start == end date"""
        date = timezone.now()
        result = PerformanceCalculator.calculate_time_weighted_return(
            portfolio,
            date,
            date
        )
        assert result == Decimal('0.0000')

    @pytest.mark.parametrize(
        ('transaction_type', 'value_after_flow'),
        [
            (Transaction.TransactionType.DEPOSIT, Decimal('11000.00')),
            (Transaction.TransactionType.WITHDRAWAL, Decimal('9000.00')),
        ],
    )
    def test_external_cash_flows_are_not_returns(self, portfolio, transaction_type, value_after_flow):
        start = timezone.make_aware(datetime(2025, 1, 1, 12))
        flow_at = timezone.make_aware(datetime(2025, 7, 1, 12))
        end = timezone.make_aware(datetime(2026, 1, 1, 12))
        initial_deposit = portfolio.transactions.get(transaction_type=Transaction.TransactionType.DEPOSIT)
        Transaction.all_objects.filter(pk=initial_deposit.pk).update(timestamp=start)
        TransactionFactory(
            portfolio=portfolio,
            transaction_type=transaction_type,
            amount=Decimal('1000.00'),
            timestamp=flow_at,
        )

        values = {
            start.date(): Decimal('10000.00'),
            flow_at.date(): value_after_flow,
            end.date(): value_after_flow,
        }
        with patch(
            'portfolio.services.performance_service.HistoricalValuationService.get_historical_value',
            side_effect=lambda _portfolio, date: values[date],
        ):
            result = PerformanceCalculator.calculate_time_weighted_return(portfolio, start, end)

        assert result == Decimal('0.0000')

    def test_growth_after_deposit_is_linked_without_counting_deposit(self, portfolio):
        start = timezone.make_aware(datetime(2025, 1, 1, 12))
        flow_at = timezone.make_aware(datetime(2025, 7, 1, 12))
        end = timezone.make_aware(datetime(2026, 1, 1, 12))
        initial_deposit = portfolio.transactions.get(transaction_type=Transaction.TransactionType.DEPOSIT)
        Transaction.all_objects.filter(pk=initial_deposit.pk).update(timestamp=start)
        TransactionFactory(
            portfolio=portfolio,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal('1000.00'),
            timestamp=flow_at,
        )

        values = {
            start.date(): Decimal('10000.00'),
            flow_at.date(): Decimal('11000.00'),
            end.date(): Decimal('12100.00'),
        }
        with patch(
            'portfolio.services.performance_service.HistoricalValuationService.get_historical_value',
            side_effect=lambda _portfolio, date: values[date],
        ):
            result = PerformanceCalculator.calculate_time_weighted_return(portfolio, start, end)

        assert result == Decimal('0.1000')

    def test_performance_attribution(self, real_loss_portfolio):
        """Test cash vs investment contribution breakdown"""
        calculator = PerformanceCalculator()
        result = calculator.calculate_total_growth(real_loss_portfolio)

        expected_loss = Decimal('-1000.00')
        assert result['investment_growth'] == expected_loss
        assert result['total_return'] == real_loss_portfolio.total_value

    @patch('portfolio.services.performance_service.PerformanceCalculator.calculate_time_weighted_return')
    def test_all_time_return_uses_first_transaction_timestamp(self, mock_calculate_twr, portfolio):
        first_txn_at = timezone.now() - timedelta(days=90)
        end_date = timezone.now()
        mock_calculate_twr.return_value = Decimal('0.1234')

        class FakeTransactionQuerySet:
            def order_by(self, *_args, **_kwargs):
                return self

            def values_list(self, *_args, **_kwargs):
                return self

            def first(self):
                return first_txn_at

        with patch('portfolio.services.performance_service.Transaction.all_objects.filter', return_value=FakeTransactionQuerySet()):
            result = PerformanceCalculator.calculate_all_time_weighted_return(
                portfolio=portfolio,
                end_date=end_date,
            )

        assert result == Decimal('0.1234')
        mock_calculate_twr.assert_called_once_with(
            portfolio=portfolio,
            start_date=first_txn_at,
            end_date=end_date,
        )

    def test_all_time_return_without_transactions_is_zero(self, portfolio):
        portfolio.transactions.all().delete()

        result = PerformanceCalculator.calculate_all_time_weighted_return(
            portfolio=portfolio,
            end_date=timezone.now(),
        )

        assert result == Decimal('0.0000')
