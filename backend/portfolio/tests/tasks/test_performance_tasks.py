import pytest
from decimal import Decimal
from unittest.mock import patch

from portfolio.tasks import update_all_time_weighted_returns
from users.tests.factories import UserFactory


@pytest.mark.django_db
class TestPerformanceTasks:
    @patch('portfolio.tasks.PerformanceCalculator.calculate_all_time_weighted_return')
    def test_update_all_time_weighted_returns_persists_all_time_value(self, mock_calculate):
        user = UserFactory.create()
        portfolio = user.portfolios.get(is_default=True)
        mock_calculate.return_value = Decimal('0.2500')

        update_all_time_weighted_returns()

        portfolio.performance.refresh_from_db()
        assert portfolio.performance.time_weighted_return == Decimal('0.2500')
        mock_calculate.assert_called_once()
