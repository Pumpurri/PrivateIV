from decimal import Decimal

import pytest

from portfolio.serializers.portfolio_serializers import PortfolioPerformanceSerializer


@pytest.mark.django_db
def test_total_return_percentage_uses_gain_over_contributions(portfolio):
    portfolio.cash_balance = Decimal('11250.00')
    portfolio.save(update_fields=['cash_balance'])
    performance = portfolio.performance
    performance.refresh_from_db()
    performance.time_weighted_return = Decimal('0.5000')

    data = PortfolioPerformanceSerializer(performance).data

    assert Decimal(data['total_return_percentage']) == Decimal('12.50')


@pytest.mark.django_db
def test_total_return_percentage_accounts_for_withdrawals(portfolio):
    portfolio.cash_balance = Decimal('9000.00')
    portfolio.save(update_fields=['cash_balance'])
    performance = portfolio.performance
    performance.refresh_from_db()
    performance.total_withdrawals = Decimal('2000.00')

    data = PortfolioPerformanceSerializer(performance).data

    assert Decimal(data['total_return_percentage']) == Decimal('10.00')
