import pytest
from decimal import Decimal
from django.db import IntegrityError
from portfolio.models import PortfolioPerformance
from portfolio.tests.factories import TransactionFactory

@pytest.mark.django_db
class TestPortfolioPerformanceModel:
    def test_autocreation(self, portfolio):
        """Test performance model auto-creation via signals"""
        assert hasattr(portfolio, 'performance')
        assert portfolio.performance.total_deposits == Decimal('0.00')

    def test_deposit_tracking(self, portfolio):
        """Test deposit amount aggregation"""
        TransactionFactory.create_batch(3,
            portfolio=portfolio,
            transaction_type='DEPOSIT',
            amount=Decimal('5000.00')
        )
        
        assert portfolio.performance.total_deposits == Decimal('15000.00')

    def test_one_to_one_constraint(self, portfolio):
        """Ensure only one performance record per portfolio"""
        with pytest.raises(IntegrityError):
            PortfolioPerformance.objects.create(portfolio=portfolio)

    def test_return_calculation_edge_cases(self, portfolio):
        """Test boundary conditions for returns"""
        portfolio.cash_balance = Decimal('0.00')
        portfolio.save()
        assert portfolio.performance.time_weighted_return == Decimal('0.0000')

        # Negative returns scenario
        # Requires complex setup with historical snapshots