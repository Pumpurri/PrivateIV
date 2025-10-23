import pytest
from decimal import Decimal
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from portfolio.models import RealizedPNL
from portfolio.tests.factories import PortfolioFactory, TransactionFactory
from stocks.tests.factories import StockFactory
from users.tests.factories import UserFactory


@pytest.mark.django_db
class TestPortfolioRealizedView:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()

    def test_requires_authentication(self):
        portfolio = PortfolioFactory()
        url = reverse('dashboard-portfolio-realized', kwargs={'portfolio_id': portfolio.id})
        response = self.client.get(url)
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_returns_realized_summary(self):
        user = UserFactory()
        portfolio = user.portfolios.first()

        # Create buy then sell to generate realized PnL
        stock = StockFactory(symbol='GAIN', current_price=Decimal('100.00'))
        TransactionFactory(transaction_type='BUY', portfolio=portfolio, stock=stock, quantity=10)
        stock.current_price = Decimal('120.00')
        stock.save()
        sell = TransactionFactory(transaction_type='SELL', portfolio=portfolio, stock=stock, quantity=5)

        pnl = RealizedPNL.objects.get(transaction=sell)
        expected_proceeds = pnl.sell_price * pnl.quantity  # 120 * 5 = 600
        expected_cost = pnl.purchase_price * pnl.quantity  # 100 * 5 = 500
        expected_net = pnl.pnl  # 100

        self.client.force_authenticate(user=user)
        url = reverse('dashboard-portfolio-realized', kwargs={'portfolio_id': portfolio.id})
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK

        data = response.data
        assert data['totals']['proceeds'] == f"{expected_proceeds:.2f}"
        assert data['totals']['cost_basis'] == f"{expected_cost:.2f}"
        assert data['totals']['net_gain'] == f"{expected_net:.2f}"
        assert any(detail['symbol'] == 'GAIN' for detail in data['details'])

    def test_filters_by_symbol(self):
        user = UserFactory()
        portfolio = user.portfolios.first()

        stock_gain = StockFactory(symbol='GAIN', current_price=Decimal('100.00'))
        TransactionFactory(transaction_type='BUY', portfolio=portfolio, stock=stock_gain, quantity=5)
        stock_gain.current_price = Decimal('110.00')
        stock_gain.save()
        TransactionFactory(transaction_type='SELL', portfolio=portfolio, stock=stock_gain, quantity=5)

        stock_loss = StockFactory(symbol='LOSS', current_price=Decimal('50.00'))
        TransactionFactory(transaction_type='BUY', portfolio=portfolio, stock=stock_loss, quantity=5)
        stock_loss.current_price = Decimal('40.00')
        stock_loss.save()
        TransactionFactory(transaction_type='SELL', portfolio=portfolio, stock=stock_loss, quantity=5)

        self.client.force_authenticate(user=user)
        url = reverse('dashboard-portfolio-realized', kwargs={'portfolio_id': portfolio.id})
        response = self.client.get(url, {'symbol': 'GAIN'})
        assert response.status_code == status.HTTP_200_OK
        symbols = {item['symbol'] for item in response.data['details']}
        assert symbols == {'GAIN'}

    def test_date_filter(self):
        user = UserFactory()
        portfolio = user.portfolios.first()
        stock = StockFactory(symbol='OLD', current_price=Decimal('100.00'))

        # Old transaction (last year)
        TransactionFactory(transaction_type='BUY', portfolio=portfolio, stock=stock, quantity=10)
        stock.current_price = Decimal('120.00')
        stock.save()
        old_sell = TransactionFactory(transaction_type='SELL', portfolio=portfolio, stock=stock, quantity=10)
        RealizedPNL.objects.filter(transaction=old_sell).update(
            realized_at=timezone.now() - timezone.timedelta(days=400)
        )

        # Recent transaction
        stock_recent = StockFactory(symbol='NEW', current_price=Decimal('80.00'))
        TransactionFactory(transaction_type='BUY', portfolio=portfolio, stock=stock_recent, quantity=4)
        stock_recent.current_price = Decimal('90.00')
        stock_recent.save()
        TransactionFactory(transaction_type='SELL', portfolio=portfolio, stock=stock_recent, quantity=4)

        self.client.force_authenticate(user=user)
        url = reverse('dashboard-portfolio-realized', kwargs={'portfolio_id': portfolio.id})
        response = self.client.get(url, {'from': f"{timezone.now().date().year}-01-01"})
        assert response.status_code == status.HTTP_200_OK
        symbols = {item['symbol'] for item in response.data['details']}
        assert symbols == {'NEW'}

    def test_invalid_range_returns_400(self):
        user = UserFactory()
        portfolio = user.portfolios.first()
        self.client.force_authenticate(user=user)
        url = reverse('dashboard-portfolio-realized', kwargs={'portfolio_id': portfolio.id})
        response = self.client.get(url, {'from': '2024-12-01', 'to': '2024-01-01'})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
