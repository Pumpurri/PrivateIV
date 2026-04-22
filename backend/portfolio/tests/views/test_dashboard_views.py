import pytest
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from portfolio.models import DailyPortfolioSnapshot, PortfolioPerformance
from portfolio.tests.factories import HoldingFactory, PortfolioFactory, TransactionFactory
from stocks.tests.factories import StockFactory
from users.tests.factories import UserFactory


@pytest.mark.django_db
class TestDashboardView:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()

    def test_requires_authentication(self):
        response = self.client.get(reverse('dashboard'))
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_returns_only_authenticated_user_dashboard_data(self):
        user = UserFactory()
        other_user = UserFactory()

        portfolio = user.portfolios.get(is_default=True)
        other_portfolio = other_user.portfolios.get(is_default=True)
        extra_portfolio = PortfolioFactory(user=user, name='Growth', is_default=False)

        performance = PortfolioPerformance.objects.get(portfolio=portfolio)
        performance.total_deposits = Decimal('10000.00')
        performance.total_withdrawals = Decimal('1000.00')
        performance.time_weighted_return = Decimal('0.1250')
        performance.save()

        stock = StockFactory(symbol='PEN1', current_price=Decimal('120.00'))
        HoldingFactory(
            portfolio=portfolio,
            stock=stock,
            quantity=2,
            average_purchase_price=Decimal('100.00')
        )

        yesterday = timezone.now().date() - timezone.timedelta(days=1)
        DailyPortfolioSnapshot.objects.create(
            portfolio=portfolio,
            date=yesterday,
            total_value=Decimal('9900.00'),
            cash_balance=Decimal('9700.00'),
            investment_value=Decimal('200.00'),
            total_deposits=Decimal('10000.00')
        )

        TransactionFactory(portfolio=other_portfolio, transaction_type='DEPOSIT', amount=Decimal('500.00'))

        self.client.force_authenticate(user=user)
        response = self.client.get(reverse('dashboard'))

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data['user']['email'] == user.email
        assert data['default_portfolio_id'] == portfolio.id
        assert len(data['portfolios']) == 2
        assert {item['id'] for item in data['portfolios']} == {portfolio.id, extra_portfolio.id}
        assert all(item['id'] != other_portfolio.id for item in data['portfolios'])
        assert all(tx['portfolio_id'] != other_portfolio.id for tx in data['recent_transactions'])

        default_item = next(item for item in data['portfolios'] if item['id'] == portfolio.id)
        assert default_item['holdings_count'] == 1
        assert Decimal(default_item['cash_balance']) == Decimal('10000.00')
        assert Decimal(default_item['current_investment_value']) == Decimal('240.00')
        assert Decimal(default_item['day_change_abs']) == Decimal('340.00')
        assert Decimal(default_item['since_inception_abs']) == Decimal('1240.00')
        assert Decimal(default_item['twr_annualized']) == Decimal('0.1250')


@pytest.mark.django_db
class TestPortfolioOverviewView:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()

    def test_requires_authentication(self):
        portfolio = PortfolioFactory()
        response = self.client.get(
            reverse('dashboard-portfolio-overview', kwargs={'portfolio_id': portfolio.id})
        )
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_returns_overview_composition_transactions_and_snapshots(self):
        user = UserFactory()
        portfolio = user.portfolios.get(is_default=True)

        performance = PortfolioPerformance.objects.get(portfolio=portfolio)
        performance.total_deposits = Decimal('10000.00')
        performance.total_withdrawals = Decimal('1000.00')
        performance.time_weighted_return = Decimal('0.0500')
        performance.save()

        stock = StockFactory(symbol='OVRVW', name='Overview Asset', current_price=Decimal('120.00'))
        HoldingFactory(
            portfolio=portfolio,
            stock=stock,
            quantity=2,
            average_purchase_price=Decimal('100.00')
        )

        today = timezone.now().date()
        five_days_ago = today - timezone.timedelta(days=5)
        forty_days_ago = today - timezone.timedelta(days=40)

        DailyPortfolioSnapshot.objects.create(
            portfolio=portfolio,
            date=five_days_ago,
            total_value=Decimal('9950.00'),
            cash_balance=Decimal('9750.00'),
            investment_value=Decimal('200.00'),
            total_deposits=Decimal('10000.00')
        )
        DailyPortfolioSnapshot.objects.create(
            portfolio=portfolio,
            date=forty_days_ago,
            total_value=Decimal('9800.00'),
            cash_balance=Decimal('9600.00'),
            investment_value=Decimal('200.00'),
            total_deposits=Decimal('10000.00')
        )

        self.client.force_authenticate(user=user)
        response = self.client.get(
            reverse('dashboard-portfolio-overview', kwargs={'portfolio_id': portfolio.id}),
            {'days': 7}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data['portfolio']['id'] == portfolio.id
        assert data['portfolio']['name'] == portfolio.name
        assert Decimal(data['portfolio']['current_investment_value']) == Decimal('240.00')
        assert data['portfolio']['holdings_count'] == 1
        assert Decimal(str(data['portfolio']['twr_annualized'])).quantize(Decimal('0.0001')) == Decimal('0.0500')

        assert len(data['composition']) == 1
        composition = data['composition'][0]
        assert composition['symbol'] == 'OVRVW'
        assert composition['quantity'] == 2
        assert Decimal(composition['current_value']) == Decimal('240.00')
        assert Decimal(composition['gain_loss']) == Decimal('40.00')
        assert Decimal(composition['cost_basis']) == Decimal('200.00')

        assert len(data['recent_transactions']) >= 1
        assert all('portfolio_id' not in snapshot for snapshot in data['snapshots'])
        assert len(data['snapshots']) == 1
        assert data['snapshots'][0]['date'] == five_days_ago.isoformat()

    def test_cannot_access_other_users_portfolio_overview(self):
        user = UserFactory()
        other_user = UserFactory()
        other_portfolio = other_user.portfolios.get(is_default=True)

        self.client.force_authenticate(user=user)
        response = self.client.get(
            reverse('dashboard-portfolio-overview', kwargs={'portfolio_id': other_portfolio.id})
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
