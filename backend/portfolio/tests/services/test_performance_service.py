import pytest
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
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
        assert -1 <= result <= 1  # Realistic return range
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

    def test_performance_attribution(self, funded_portfolio):
        """Test cash vs investment contribution breakdown"""
        # Setup deposits and investment activity
        TransactionFactory(
            portfolio=funded_portfolio,
            transaction_type='DEPOSIT',
            amount=Decimal('5000.00')
        )
        # ... create investment transactions ...
        
        result = PerformanceCalculator.calculate_total_growth(
            funded_portfolio
        )
        
        assert 'cash_contribution' in result
        assert 'investment_growth' in result
        assert 'total_return' in result
        assert result['total_return'] == (
            result['cash_contribution'] + result['investment_growth']
        )

    def test_negative_returns_attribution(self, portfolio_with_loss):
        """Test proper handling of negative investment growth"""
        result = PerformanceCalculator.calculate_total_growth(
            portfolio_with_loss
        )
        assert result['investment_growth'] < Decimal('0.00')