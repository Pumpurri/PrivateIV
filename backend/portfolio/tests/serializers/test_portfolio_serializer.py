import pytest

from portfolio.serializers.portfolio_serializers import PortfolioSerializer
from portfolio.tests.factories import PortfolioFactory


@pytest.mark.django_db
def test_base_currency_cannot_change_after_transactions(portfolio):
    serializer = PortfolioSerializer(portfolio, data={'base_currency': 'USD'}, partial=True)

    assert not serializer.is_valid()
    assert 'base_currency' in serializer.errors


@pytest.mark.django_db
def test_base_currency_can_change_before_first_transaction(portfolio):
    empty_portfolio = PortfolioFactory(user=portfolio.user)
    serializer = PortfolioSerializer(empty_portfolio, data={'base_currency': 'USD'}, partial=True)

    assert serializer.is_valid(), serializer.errors
