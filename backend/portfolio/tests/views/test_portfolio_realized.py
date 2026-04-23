import pytest
from decimal import Decimal
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from portfolio.models import FXRate, RealizedPNL, Transaction
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
        stock = StockFactory(symbol='GAIN', current_price=Decimal('100.00'), currency='PEN')
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

        stock_gain = StockFactory(symbol='GAIN', current_price=Decimal('100.00'), currency='PEN')
        TransactionFactory(transaction_type='BUY', portfolio=portfolio, stock=stock_gain, quantity=5)
        stock_gain.current_price = Decimal('110.00')
        stock_gain.save()
        TransactionFactory(transaction_type='SELL', portfolio=portfolio, stock=stock_gain, quantity=5)

        stock_loss = StockFactory(symbol='LOSS', current_price=Decimal('50.00'), currency='PEN')
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

    def test_date_filter_uses_sell_transaction_timestamp(self):
        user = UserFactory()
        portfolio = user.portfolios.first()
        stock = StockFactory(symbol='OLD', current_price=Decimal('100.00'), currency='PEN')
        old_timestamp = timezone.now() - timezone.timedelta(days=400)

        # Old transaction (last year)
        old_buy = TransactionFactory(transaction_type='BUY', portfolio=portfolio, stock=stock, quantity=10)
        Transaction.all_objects.filter(pk=old_buy.pk).update(timestamp=old_timestamp - timezone.timedelta(days=30))
        stock.current_price = Decimal('120.00')
        stock.save()
        old_sell = TransactionFactory(transaction_type='SELL', portfolio=portfolio, stock=stock, quantity=10)
        Transaction.all_objects.filter(pk=old_sell.pk).update(timestamp=old_timestamp)
        RealizedPNL.objects.filter(transaction=old_sell).update(realized_at=timezone.now())

        # Recent transaction
        stock_recent = StockFactory(symbol='NEW', current_price=Decimal('80.00'), currency='PEN')
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

    def test_long_short_uses_buy_timestamp_when_acquisition_date_is_invalid(self):
        user = UserFactory()
        portfolio = user.portfolios.first()
        stock = StockFactory(symbol='LONG', current_price=Decimal('100.00'), currency='PEN')
        buy_timestamp = timezone.now() - timezone.timedelta(days=500)
        sell_timestamp = timezone.now()

        buy = TransactionFactory(transaction_type='BUY', portfolio=portfolio, stock=stock, quantity=10)
        Transaction.all_objects.filter(pk=buy.pk).update(timestamp=buy_timestamp)
        stock.current_price = Decimal('125.00')
        stock.save()
        sell = TransactionFactory(transaction_type='SELL', portfolio=portfolio, stock=stock, quantity=10)
        Transaction.all_objects.filter(pk=sell.pk).update(timestamp=sell_timestamp)
        # Simulate an imported/backfilled row where acquisition_date was created after the sale.
        RealizedPNL.objects.filter(transaction=sell).update(acquisition_date=sell_timestamp + timezone.timedelta(days=1))

        self.client.force_authenticate(user=user)
        url = reverse('dashboard-portfolio-realized', kwargs={'portfolio_id': portfolio.id})
        response = self.client.get(url, {'from': sell_timestamp.date().isoformat(), 'to': sell_timestamp.date().isoformat()})
        assert response.status_code == status.HTTP_200_OK
        assert response.data['long_short']['long_term'] == '250.00'
        assert response.data['long_short']['short_term'] == '0.00'

    def test_invalid_range_returns_400(self):
        user = UserFactory()
        portfolio = user.portfolios.first()
        self.client.force_authenticate(user=user)
        url = reverse('dashboard-portfolio-realized', kwargs={'portfolio_id': portfolio.id})
        response = self.client.get(url, {'from': '2024-12-01', 'to': '2024-01-01'})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_display_currency_uses_transaction_execution_fx_for_cross_currency_stock(self, set_fx_market_now):
        user = UserFactory()
        portfolio = user.portfolios.first()
        stock = StockFactory(symbol='USDX', current_price=Decimal('10.00'), currency='USD')

        today = timezone.now().date()
        set_fx_market_now(today)
        for session in ('intraday', 'cierre'):
            FXRate.objects.create(
                date=today,
                base_currency='PEN',
                quote_currency='USD',
                rate=Decimal('3.80'),
                rate_type='venta',
                session=session,
            )
            FXRate.objects.create(
                date=today,
                base_currency='PEN',
                quote_currency='USD',
                rate=Decimal('3.50'),
                rate_type='compra',
                session=session,
            )

        TransactionFactory(transaction_type='BUY', portfolio=portfolio, stock=stock, quantity=2)
        stock.current_price = Decimal('12.00')
        stock.save(update_fields=['current_price'])
        TransactionFactory(transaction_type='SELL', portfolio=portfolio, stock=stock, quantity=2)

        self.client.force_authenticate(user=user)
        url = reverse('dashboard-portfolio-realized', kwargs={'portfolio_id': portfolio.id})
        response = self.client.get(url, {'display_currency': 'USD'})
        assert response.status_code == status.HTTP_200_OK

        data = response.data
        assert data['display_currency'] == 'USD'
        assert data['totals']['proceeds'] == '24.00'
        assert data['totals']['cost_basis'] == '20.00'
        assert data['totals']['net_gain'] == '4.00'
        assert data['details'][0]['closing_price'] == '12.00'

    def test_display_currency_falls_back_to_historical_fx_dates_when_transaction_has_no_fx_rate(self, set_fx_market_now):
        user = UserFactory()
        portfolio = user.portfolios.first()
        stock = StockFactory(symbol='PENX', current_price=Decimal('100.00'), currency='PEN')
        buy_date = timezone.now() - timezone.timedelta(days=60)
        sell_date = timezone.now() - timezone.timedelta(days=5)

        set_fx_market_now(sell_date.date())
        for fx_date, rate in ((buy_date.date(), Decimal('4.00')), (sell_date.date(), Decimal('3.00'))):
            FXRate.objects.create(
                date=fx_date,
                base_currency='PEN',
                quote_currency='USD',
                rate=rate,
                rate_type='mid',
                session='cierre',
            )

        buy = TransactionFactory(transaction_type='BUY', portfolio=portfolio, stock=stock, quantity=1)
        Transaction.all_objects.filter(pk=buy.pk).update(timestamp=buy_date, fx_rate=None, fx_rate_type=None)

        stock.current_price = Decimal('120.00')
        stock.save(update_fields=['current_price'])
        sell = TransactionFactory(transaction_type='SELL', portfolio=portfolio, stock=stock, quantity=1)
        Transaction.all_objects.filter(pk=sell.pk).update(timestamp=sell_date, fx_rate=None, fx_rate_type=None)

        self.client.force_authenticate(user=user)
        url = reverse('dashboard-portfolio-realized', kwargs={'portfolio_id': portfolio.id})
        response = self.client.get(
            url,
            {
                'display_currency': 'USD',
                'from': sell_date.date().isoformat(),
                'to': sell_date.date().isoformat(),
            },
        )
        assert response.status_code == status.HTTP_200_OK

        data = response.data
        assert data['display_currency'] == 'USD'
        assert data['totals']['proceeds'] == '40.00'
        assert data['totals']['cost_basis'] == '25.00'
        assert data['totals']['net_gain'] == '15.00'

    def test_native_display_mode_keeps_summary_reporting_currency_and_detail_native_currency(self, set_fx_market_now):
        user = UserFactory()
        portfolio = user.portfolios.first()
        stock = StockFactory(symbol='NATV', current_price=Decimal('10.00'), currency='USD')

        today = timezone.now().date()
        set_fx_market_now(today)
        for session in ('intraday', 'cierre'):
            FXRate.objects.create(
                date=today,
                base_currency='PEN',
                quote_currency='USD',
                rate=Decimal('3.80'),
                rate_type='venta',
                session=session,
            )
            FXRate.objects.create(
                date=today,
                base_currency='PEN',
                quote_currency='USD',
                rate=Decimal('3.50'),
                rate_type='compra',
                session=session,
            )

        TransactionFactory(transaction_type='BUY', portfolio=portfolio, stock=stock, quantity=2)
        stock.current_price = Decimal('12.00')
        stock.save(update_fields=['current_price'])
        TransactionFactory(transaction_type='SELL', portfolio=portfolio, stock=stock, quantity=2)

        self.client.force_authenticate(user=user)
        url = reverse('dashboard-portfolio-realized', kwargs={'portfolio_id': portfolio.id})
        response = self.client.get(url, {'display_currency': 'NATIVE'})
        assert response.status_code == status.HTTP_200_OK

        data = response.data
        assert data['display_currency_mode'] == 'NATIVE'
        assert data['summary_currency'] == 'PEN'
        assert data['display_currency'] == 'PEN'
        assert data['totals']['net_gain'] == '8.00'
        assert data['native_summary']['USD']['net_gain'] == '4.00'
        assert data['native_summary']['PEN']['net_gain'] == '0.00'
        assert data['details'][0]['display_currency'] == 'USD'
        assert data['details'][0]['total'] == '4.00'
        assert data['details'][0]['chart_total'] == '8.00'

    def test_native_display_mode_summary_respects_symbol_filter(self, set_fx_market_now):
        user = UserFactory()
        portfolio = user.portfolios.first()
        today = timezone.now().date()
        set_fx_market_now(today)

        for session in ('intraday', 'cierre'):
            FXRate.objects.create(
                date=today,
                base_currency='PEN',
                quote_currency='USD',
                rate=Decimal('4.00'),
                rate_type='venta',
                session=session,
            )
            FXRate.objects.create(
                date=today,
                base_currency='PEN',
                quote_currency='USD',
                rate=Decimal('4.00'),
                rate_type='compra',
                session=session,
            )

        usd_stock = StockFactory(symbol='KEEP', current_price=Decimal('10.00'), currency='USD')
        pen_stock = StockFactory(symbol='DROP', current_price=Decimal('100.00'), currency='PEN')

        TransactionFactory(transaction_type='BUY', portfolio=portfolio, stock=usd_stock, quantity=2)
        usd_stock.current_price = Decimal('12.00')
        usd_stock.save(update_fields=['current_price'])
        TransactionFactory(transaction_type='SELL', portfolio=portfolio, stock=usd_stock, quantity=2)

        TransactionFactory(transaction_type='BUY', portfolio=portfolio, stock=pen_stock, quantity=1)
        pen_stock.current_price = Decimal('120.00')
        pen_stock.save(update_fields=['current_price'])
        TransactionFactory(transaction_type='SELL', portfolio=portfolio, stock=pen_stock, quantity=1)

        self.client.force_authenticate(user=user)
        url = reverse('dashboard-portfolio-realized', kwargs={'portfolio_id': portfolio.id})
        response = self.client.get(url, {'display_currency': 'NATIVE', 'symbol': 'KEEP'})
        assert response.status_code == status.HTTP_200_OK

        data = response.data
        assert {row['symbol'] for row in data['details']} == {'KEEP'}
        assert data['native_summary']['USD']['net_gain'] == '4.00'
        assert data['native_summary']['PEN']['net_gain'] == '0.00'

    def test_native_display_mode_summary_respects_date_filter(self, set_fx_market_now):
        user = UserFactory()
        portfolio = user.portfolios.first()
        sell_date = timezone.now() - timezone.timedelta(days=5)
        old_sell_date = timezone.now() - timezone.timedelta(days=40)
        buy_date = old_sell_date - timezone.timedelta(days=5)

        set_fx_market_now(sell_date.date())
        for fx_date in (buy_date.date(), old_sell_date.date(), sell_date.date()):
            FXRate.objects.create(
                date=fx_date,
                base_currency='PEN',
                quote_currency='USD',
                rate=Decimal('4.00'),
                rate_type='venta',
                session='cierre',
            )
            FXRate.objects.create(
                date=fx_date,
                base_currency='PEN',
                quote_currency='USD',
                rate=Decimal('4.00'),
                rate_type='compra',
                session='cierre',
            )

        stock = StockFactory(symbol='DATE', current_price=Decimal('10.00'), currency='USD')

        old_buy = TransactionFactory(transaction_type='BUY', portfolio=portfolio, stock=stock, quantity=1)
        Transaction.all_objects.filter(pk=old_buy.pk).update(timestamp=buy_date)
        stock.current_price = Decimal('11.00')
        stock.save(update_fields=['current_price'])
        old_sell = TransactionFactory(transaction_type='SELL', portfolio=portfolio, stock=stock, quantity=1)
        Transaction.all_objects.filter(pk=old_sell.pk).update(timestamp=old_sell_date)

        recent_buy = TransactionFactory(transaction_type='BUY', portfolio=portfolio, stock=stock, quantity=1)
        Transaction.all_objects.filter(pk=recent_buy.pk).update(timestamp=sell_date - timezone.timedelta(days=1))
        stock.current_price = Decimal('13.00')
        stock.save(update_fields=['current_price'])
        recent_sell = TransactionFactory(transaction_type='SELL', portfolio=portfolio, stock=stock, quantity=1)
        Transaction.all_objects.filter(pk=recent_sell.pk).update(timestamp=sell_date)

        self.client.force_authenticate(user=user)
        url = reverse('dashboard-portfolio-realized', kwargs={'portfolio_id': portfolio.id})
        response = self.client.get(
            url,
            {
                'display_currency': 'NATIVE',
                'from': sell_date.date().isoformat(),
                'to': sell_date.date().isoformat(),
            },
        )
        assert response.status_code == status.HTTP_200_OK

        data = response.data
        assert len(data['details']) == 1
        assert data['details'][0]['symbol'] == 'DATE'
        assert data['native_summary']['USD']['proceeds'] == '13.00'
        assert data['native_summary']['USD']['cost_basis'] == '11.00'
        assert data['native_summary']['USD']['net_gain'] == '2.00'
        assert data['native_summary']['PEN']['net_gain'] == '0.00'
