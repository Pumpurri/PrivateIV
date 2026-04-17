import pytest
from datetime import date, timedelta
from decimal import Decimal
from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient
from portfolio.models import FXRate, Portfolio, Holding, PortfolioPerformance, Transaction
from portfolio.tests.factories import PortfolioFactory, HoldingFactory, TransactionFactory
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

    def test_create_portfolio_with_initial_deposit(self):
        user = UserFactory.create()
        self.client.force_authenticate(user=user)

        response = self.client.post(
            self.url,
            {
                'name': 'Trading Portfolio',
                'description': 'Short term account',
                'initial_deposit': '500.00',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        portfolio = Portfolio.objects.get(id=response.data['id'])
        assert portfolio.user == user
        assert portfolio.cash_balance == Decimal('500.00')
        assert Transaction.objects.filter(
            portfolio=portfolio,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal('500.00'),
        ).exists()

    def test_create_portfolio_rolls_back_if_initial_deposit_fails(self, monkeypatch):
        user = UserFactory.create()
        self.client.force_authenticate(user=user)

        def fail_deposit(_tx_data):
            raise ValidationError({'initial_deposit': 'Deposit failed.'})

        monkeypatch.setattr(
            'portfolio.views.portfolio_views.TransactionService.execute_transaction',
            fail_deposit,
        )

        response = self.client.post(
            self.url,
            {
                'name': 'Failed Portfolio',
                'description': 'Should not persist',
                'initial_deposit': '500.00',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not Portfolio.objects.filter(user=user, name='Failed Portfolio').exists()


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

    def test_holdings_list_uses_pen_quote_metrics_for_usd_positions(self, set_quote_and_position_now):
        user = UserFactory.create()
        portfolio = user.portfolios.first()
        stock = StockFactory.create(
            symbol='NVDA',
            current_price=Decimal('10.00'),
            previous_close=Decimal('8.00'),
            currency='USD',
            is_local=False,
        )
        HoldingFactory.create(
            portfolio=portfolio,
            stock=stock,
            quantity=2,
            average_purchase_price=Decimal('20.00'),
        )

        market_date = date(2026, 4, 17)
        set_quote_and_position_now(market_date)
        FXRate.objects.create(
            date=market_date,
            base_currency='PEN',
            quote_currency='USD',
            rate=Decimal('3.50'),
            rate_type='mid',
            session='cierre',
        )
        FXRate.objects.create(
            date=market_date - timedelta(days=1),
            base_currency='PEN',
            quote_currency='USD',
            rate=Decimal('3.40'),
            rate_type='mid',
            session='cierre',
        )

        self.client.force_authenticate(user=user)
        url = reverse('portfolio-holdings', kwargs={'portfolio_id': portfolio.id})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        holding_data = response.data['results'][0]
        assert Decimal(holding_data['stock']['display_price']) == Decimal('35.00')
        assert Decimal(holding_data['stock']['price_change']) == Decimal('7.80')
        assert Decimal(holding_data['stock']['price_change_percent']) == Decimal('28.68')
        assert Decimal(holding_data['current_value']) == Decimal('70.00')
        assert Decimal(holding_data['day_change']) == Decimal('15.60')
        assert Decimal(holding_data['day_change_percentage']) == Decimal('28.68')
        assert Decimal(holding_data['cost_basis']) == Decimal('40.00')
        assert Decimal(holding_data['gain_loss']) == Decimal('30.00')

    def test_holdings_list_uses_today_buy_price_for_position_day_change(self, set_quote_and_position_now):
        user = UserFactory.create()
        portfolio = user.portfolios.first()
        stock = StockFactory.create(
            symbol='AAL',
            current_price=Decimal('10.00'),
            previous_close=Decimal('8.00'),
            currency='USD',
            is_local=False,
        )
        market_date = date(2026, 4, 17)
        set_quote_and_position_now(market_date)

        FXRate.objects.create(
            date=market_date,
            base_currency='PEN',
            quote_currency='USD',
            rate=Decimal('3.50'),
            rate_type='mid',
            session='cierre',
        )
        FXRate.objects.create(
            date=market_date,
            base_currency='PEN',
            quote_currency='USD',
            rate=Decimal('3.60'),
            rate_type='venta',
            session='cierre',
        )
        FXRate.objects.create(
            date=market_date - timedelta(days=1),
            base_currency='PEN',
            quote_currency='USD',
            rate=Decimal('3.40'),
            rate_type='mid',
            session='cierre',
        )

        TransactionFactory(
            portfolio=portfolio,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal('1000.00'),
        )
        TransactionFactory(
            portfolio=portfolio,
            transaction_type=Transaction.TransactionType.BUY,
            stock=stock,
            quantity=1,
        )

        self.client.force_authenticate(user=user)
        url = reverse('portfolio-holdings', kwargs={'portfolio_id': portfolio.id})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        holding_data = response.data['results'][0]
        assert Decimal(holding_data['current_value']) == Decimal('35.00')
        assert Decimal(holding_data['cost_basis']) == Decimal('36.00')
        assert Decimal(holding_data['day_change']) == Decimal('-1.00')
        assert Decimal(holding_data['day_change_percentage']) == Decimal('-2.78')
        assert Decimal(holding_data['gain_loss']) == Decimal('-1.00')

    def test_holdings_list_splits_overnight_and_today_added_quantity_for_day_change(self, set_quote_and_position_now):
        user = UserFactory.create()
        portfolio = user.portfolios.first()
        stock = StockFactory.create(
            symbol='DAL',
            current_price=Decimal('10.00'),
            previous_close=Decimal('8.00'),
            currency='USD',
            is_local=False,
        )
        HoldingFactory.create(
            portfolio=portfolio,
            stock=stock,
            quantity=2,
            average_purchase_price=Decimal('30.00'),
        )
        market_date = date(2026, 4, 17)
        set_quote_and_position_now(market_date)

        FXRate.objects.create(
            date=market_date,
            base_currency='PEN',
            quote_currency='USD',
            rate=Decimal('3.50'),
            rate_type='mid',
            session='cierre',
        )
        FXRate.objects.create(
            date=market_date,
            base_currency='PEN',
            quote_currency='USD',
            rate=Decimal('3.60'),
            rate_type='venta',
            session='cierre',
        )
        FXRate.objects.create(
            date=market_date - timedelta(days=1),
            base_currency='PEN',
            quote_currency='USD',
            rate=Decimal('3.40'),
            rate_type='mid',
            session='cierre',
        )

        TransactionFactory(
            portfolio=portfolio,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal('1000.00'),
        )
        TransactionFactory(
            portfolio=portfolio,
            transaction_type=Transaction.TransactionType.BUY,
            stock=stock,
            quantity=1,
        )

        self.client.force_authenticate(user=user)
        url = reverse('portfolio-holdings', kwargs={'portfolio_id': portfolio.id})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        holding_data = response.data['results'][0]
        assert Decimal(holding_data['current_value']) == Decimal('105.00')
        assert Decimal(holding_data['cost_basis']) == Decimal('96.00')
        assert Decimal(holding_data['day_change']) == Decimal('14.60')
        assert Decimal(holding_data['day_change_percentage']) == Decimal('16.15')
        assert Decimal(holding_data['gain_loss']) == Decimal('9.00')

    def test_holdings_list_supports_explicit_usd_display_currency(self, set_quote_and_position_now):
        user = UserFactory.create()
        portfolio = user.portfolios.first()
        stock = StockFactory.create(
            symbol='QQQ',
            current_price=Decimal('10.00'),
            previous_close=Decimal('8.00'),
            previous_close_date=date(2026, 4, 16),
            currency='USD',
            is_local=False,
        )
        HoldingFactory.create(
            portfolio=portfolio,
            stock=stock,
            quantity=2,
            average_purchase_price=Decimal('20.00'),
        )
        market_date = date(2026, 4, 17)
        set_quote_and_position_now(market_date)

        FXRate.objects.create(
            date=market_date,
            base_currency='PEN',
            quote_currency='USD',
            rate=Decimal('3.50'),
            rate_type='mid',
            session='cierre',
        )
        FXRate.objects.create(
            date=market_date - timedelta(days=1),
            base_currency='PEN',
            quote_currency='USD',
            rate=Decimal('3.40'),
            rate_type='mid',
            session='cierre',
        )

        self.client.force_authenticate(user=user)
        url = reverse('portfolio-holdings', kwargs={'portfolio_id': portfolio.id})
        response = self.client.get(url, {'display_currency': 'USD'})

        assert response.status_code == status.HTTP_200_OK
        assert response.data['display_currency'] == 'USD'
        assert response.data['display_currency_mode'] == 'USD'
        assert response.data['summary']['summary_currency'] == 'USD'
        holding_data = response.data['results'][0]
        assert holding_data['stock']['display_currency'] == 'USD'
        assert Decimal(holding_data['stock']['display_price']) == Decimal('10.00')
        assert Decimal(holding_data['stock']['price_change']) == Decimal('2.00')
        assert Decimal(holding_data['stock']['price_change_percent']) == Decimal('25.00')
        assert Decimal(holding_data['current_value']) == Decimal('20.00')
        assert Decimal(holding_data['cost_basis']) == Decimal('11.43')

    def test_holdings_list_native_mode_keeps_row_native_and_summary_reporting_currency(self, set_quote_and_position_now):
        user = UserFactory.create()
        portfolio = user.portfolios.first()
        portfolio.reporting_currency = 'PEN'
        portfolio.save(update_fields=['reporting_currency'])
        stock = StockFactory.create(
            symbol='SHOP',
            current_price=Decimal('10.00'),
            previous_close=Decimal('8.00'),
            previous_close_date=date(2026, 4, 16),
            currency='USD',
            is_local=False,
        )
        HoldingFactory.create(
            portfolio=portfolio,
            stock=stock,
            quantity=2,
            average_purchase_price=Decimal('20.00'),
        )
        market_date = date(2026, 4, 17)
        set_quote_and_position_now(market_date)

        FXRate.objects.create(
            date=market_date,
            base_currency='PEN',
            quote_currency='USD',
            rate=Decimal('3.50'),
            rate_type='mid',
            session='cierre',
        )
        FXRate.objects.create(
            date=market_date - timedelta(days=1),
            base_currency='PEN',
            quote_currency='USD',
            rate=Decimal('3.40'),
            rate_type='mid',
            session='cierre',
        )

        self.client.force_authenticate(user=user)
        url = reverse('portfolio-holdings', kwargs={'portfolio_id': portfolio.id})
        response = self.client.get(url, {'display_currency': 'NATIVE'})

        assert response.status_code == status.HTTP_200_OK
        assert response.data['display_currency_mode'] == 'NATIVE'
        assert response.data['display_currency'] == 'PEN'
        assert response.data['summary']['summary_currency'] == 'PEN'
        holding_data = response.data['results'][0]
        assert holding_data['stock']['display_currency'] == 'USD'
        assert Decimal(holding_data['current_value']) == Decimal('20.00')

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
