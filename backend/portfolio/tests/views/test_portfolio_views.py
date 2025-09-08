import pytest
from decimal import Decimal
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from portfolio.models import Portfolio, Holding, PortfolioPerformance
from portfolio.tests.factories import PortfolioFactory, HoldingFactory
from stocks.tests.factories import StockFactory
from users.tests.factories import UserFactory


@pytest.mark.django_db
class TestPortfolioListView:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        self.url = reverse('portfolio-list')

    def test_unauthenticated_access(self):
        response = self.client.get(self.url)
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_empty_portfolio_list(self):
        user = UserFactory.create()
        self.client.force_authenticate(user=user)
        response = self.client.get(self.url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1  # Default portfolio created via signal
        assert response.data['results'][0]['is_default'] is True

    def test_multiple_portfolios(self):
        user = UserFactory.create()
        # Additional portfolio (default already created via signal)
        PortfolioFactory.create(user=user, name="Trading Portfolio", is_default=False)
        
        self.client.force_authenticate(user=user)
        response = self.client.get(self.url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 2

    def test_user_only_sees_own_portfolios(self):
        user1 = UserFactory.create()
        user2 = UserFactory.create()
        PortfolioFactory.create(user=user2, name="Other User Portfolio")
        
        self.client.force_authenticate(user=user1)
        response = self.client.get(self.url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1  # Only user1's default portfolio
        assert all(portfolio['name'] != "Other User Portfolio" for portfolio in response.data['results'])

    def test_response_structure(self):
        user = UserFactory.create()
        stock = StockFactory.create(symbol='AAPL', current_price=Decimal('150.00'))
        portfolio = user.portfolios.first()  # Default portfolio
        HoldingFactory.create(portfolio=portfolio, stock=stock, quantity=10)
        
        self.client.force_authenticate(user=user)
        response = self.client.get(self.url)
        
        assert response.status_code == status.HTTP_200_OK
        portfolio_data = response.data['results'][0]
        
        # Check required fields
        required_fields = [
            'id', 'name', 'description', 'is_default', 'cash_balance',
            'total_value', 'current_investment_value', 'holdings_count',
            'created_at', 'updated_at'
        ]
        for field in required_fields:
            assert field in portfolio_data

        # Check calculated values
        assert portfolio_data['holdings_count'] == 1
        assert Decimal(portfolio_data['current_investment_value']) == Decimal('1500.00')  # 10 * 150


@pytest.mark.django_db 
class TestPortfolioDetailView:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()

    def test_unauthenticated_access(self):
        portfolio = PortfolioFactory.create()
        url = reverse('portfolio-detail', kwargs={'pk': portfolio.id})
        response = self.client.get(url)
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_portfolio_detail_with_holdings(self):
        user = UserFactory.create()
        stock1 = StockFactory.create(symbol='AAPL', current_price=Decimal('150.00'))
        stock2 = StockFactory.create(symbol='MSFT', current_price=Decimal('300.00'))
        portfolio = user.portfolios.first()  # Default portfolio
        
        HoldingFactory.create(
            portfolio=portfolio, stock=stock1, quantity=10,
            average_purchase_price=Decimal('140.00')
        )
        HoldingFactory.create(
            portfolio=portfolio, stock=stock2, quantity=5,
            average_purchase_price=Decimal('280.00')
        )
        
        self.client.force_authenticate(user=user)
        url = reverse('portfolio-detail', kwargs={'pk': portfolio.id})
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Check holdings are included
        assert 'holdings' in response.data
        assert len(response.data['holdings']) == 2
        
        # Check holding details
        holdings = response.data['holdings']
        aapl_holding = next(h for h in holdings if h['stock']['symbol'] == 'AAPL')
        assert aapl_holding['quantity'] == 10
        assert Decimal(aapl_holding['current_value']) == Decimal('1500.00')
        assert Decimal(aapl_holding['gain_loss']) == Decimal('100.00')  # (150-140)*10

    def test_cannot_access_other_user_portfolio(self):
        user1 = UserFactory.create()
        user2 = UserFactory.create()
        portfolio = user2.portfolios.first()
        
        self.client.force_authenticate(user=user1)
        url = reverse('portfolio-detail', kwargs={'pk': portfolio.id})
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestPortfolioHoldingsView:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()

    def test_unauthenticated_access(self):
        portfolio = PortfolioFactory.create()
        url = reverse('portfolio-holdings', kwargs={'portfolio_id': portfolio.id})
        response = self.client.get(url)
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_holdings_list(self):
        user = UserFactory.create()
        stock1 = StockFactory.create(symbol='AAPL', current_price=Decimal('150.00'))
        stock2 = StockFactory.create(symbol='MSFT', current_price=Decimal('300.00'))
        portfolio = user.portfolios.first()
        
        holding1 = HoldingFactory.create(
            portfolio=portfolio, stock=stock1, quantity=10,
            average_purchase_price=Decimal('140.00')
        )
        holding2 = HoldingFactory.create(
            portfolio=portfolio, stock=stock2, quantity=5,
            average_purchase_price=Decimal('280.00')
        )
        
        self.client.force_authenticate(user=user)
        url = reverse('portfolio-holdings', kwargs={'portfolio_id': portfolio.id})
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 2
        
        # Check holding calculations
        aapl_data = next(h for h in response.data['results'] if h['stock']['symbol'] == 'AAPL')
        assert Decimal(aapl_data['current_value']) == Decimal('1500.00')
        assert Decimal(aapl_data['gain_loss']) == Decimal('100.00')
        assert float(aapl_data['gain_loss_percentage']) == 7.14  # (100 / 1400) * 100

    def test_empty_holdings(self):
        user = UserFactory.create()
        portfolio = user.portfolios.first()
        
        self.client.force_authenticate(user=user)
        url = reverse('portfolio-holdings', kwargs={'portfolio_id': portfolio.id})
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['results'] == []

    def test_cannot_access_other_user_holdings(self):
        user1 = UserFactory.create()
        user2 = UserFactory.create()
        portfolio = user2.portfolios.first()
        
        self.client.force_authenticate(user=user1)
        url = reverse('portfolio-holdings', kwargs={'portfolio_id': portfolio.id})
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestPortfolioPerformanceView:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()

    def test_unauthenticated_access(self):
        portfolio = PortfolioFactory.create()
        url = reverse('portfolio-performance', kwargs={'portfolio_id': portfolio.id})
        response = self.client.get(url)
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_performance_data_creation(self):
        user = UserFactory.create()
        portfolio = user.portfolios.first()
        
        # Update existing performance data (auto-created by signals)
        performance = PortfolioPerformance.objects.get(portfolio=portfolio)
        performance.total_deposits = Decimal('10000.00')
        performance.total_withdrawals = Decimal('1000.00')
        performance.time_weighted_return = Decimal('0.1250')
        performance.save()
        
        self.client.force_authenticate(user=user)
        url = reverse('portfolio-performance', kwargs={'portfolio_id': portfolio.id})
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert Decimal(response.data['total_deposits']) == Decimal('10000.00')
        assert Decimal(response.data['total_withdrawals']) == Decimal('1000.00')

    def test_performance_auto_creation(self):
        user = UserFactory.create()
        portfolio = user.portfolios.first()
        
        # Performance record already exists due to signals
        assert PortfolioPerformance.objects.filter(portfolio=portfolio).exists()
        
        self.client.force_authenticate(user=user)
        url = reverse('portfolio-performance', kwargs={'portfolio_id': portfolio.id})
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        # Performance record should exist and be accessible
        assert 'total_deposits' in response.data

    def test_cannot_access_other_user_performance(self):
        user1 = UserFactory.create()
        user2 = UserFactory.create()
        portfolio = user2.portfolios.first()
        
        self.client.force_authenticate(user=user1)
        url = reverse('portfolio-performance', kwargs={'portfolio_id': portfolio.id})
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestPortfolioSecurity:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()

    def test_nonexistent_portfolio_access(self):
        user = UserFactory.create()
        self.client.force_authenticate(user=user)
        
        # Test all portfolio endpoints with nonexistent ID
        endpoints = [
            ('portfolio-detail', 99999),
            ('portfolio-holdings', 99999),
            ('portfolio-performance', 99999)
        ]
        
        for endpoint_name, portfolio_id in endpoints:
            if endpoint_name == 'portfolio-detail':
                url = reverse(endpoint_name, kwargs={'pk': portfolio_id})
            else:
                url = reverse(endpoint_name, kwargs={'portfolio_id': portfolio_id})
            
            response = self.client.get(url)
            assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_sql_injection_prevention(self):
        user = UserFactory.create()
        self.client.force_authenticate(user=user)
        
        # Try SQL injection in URL parameters
        malicious_ids = ["1'; DROP TABLE portfolio_portfolio; --", "1 OR 1=1", "' UNION SELECT * FROM users"]
        
        for malicious_id in malicious_ids:
            url = f"/api/portfolios/{malicious_id}/"
            response = self.client.get(url)
            # Should return 404 (not found) or 400 (bad request), not 500 (server error)
            assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND]