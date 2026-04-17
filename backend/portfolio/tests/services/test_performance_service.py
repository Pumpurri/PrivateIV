import pytest
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from unittest.mock import patch
from portfolio.services.performance_service import PerformanceCalculator
from portfolio.tests.conftest import portfolio_with_history
from portfolio.tests.factories import TransactionFactory

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
