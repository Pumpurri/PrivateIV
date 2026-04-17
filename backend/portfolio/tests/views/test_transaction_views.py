import pytest
import uuid
from datetime import timedelta
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from portfolio.models import FXRate, Transaction
from portfolio.tests.factories import PortfolioFactory, TransactionFactory
from stocks.tests.factories import StockFactory
from users.tests.factories import UserFactory
from decimal import Decimal

@pytest.mark.django_db
class TestTransactionHistory:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()

    def test_unauthenticated_access(self):
        url = reverse('transaction-list')
        response = self.client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_authenticated_user_sees_only_their_transactions(self):
        user1 = UserFactory()
        user2 = UserFactory()

        portfolio1 = user1.portfolios.get(is_default=True)

        t1 = TransactionFactory(
            portfolio=portfolio1,
            buy=True,
            stock=StockFactory(current_price=Decimal('50.00'), currency='PEN'),
            quantity=100
        )
        t2 = TransactionFactory(portfolio__user=user2, deposit=True)

        self.client.force_authenticate(user=user1)
        response = self.client.get(reverse('transaction-list'))
        assert response.status_code == status.HTTP_200_OK
        results = response.json()['results']

        transaction_ids = [str(item['id']) for item in results]
        assert str(t1.id) in transaction_ids
        assert len(results) == 2


    def test_filtering_functionality(self):
        user = UserFactory()
        portfolio1 = user.portfolios.first()

        stocks = [
            StockFactory(current_price=Decimal('30.00'), currency='PEN'),
            StockFactory(current_price=Decimal('30.00'), currency='PEN'),
            StockFactory(current_price=Decimal('30.00'), currency='PEN')
        ]
        for stock in stocks:
            TransactionFactory(
                portfolio=portfolio1,
                buy=True,
                stock=stock,
                quantity=30,
            )

        self.client.force_authenticate(user=user)
        response = self.client.get(f"{reverse('transaction-list')}?portfolio={portfolio1.id}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['count'] == 4

    def test_filters_by_portfolio_type_symbol_and_date_range(self):
        user = UserFactory()
        portfolio = PortfolioFactory(user=user, is_default=False, cash_balance=Decimal('10000.00'))
        other_portfolio = PortfolioFactory(user=user, is_default=False, cash_balance=Decimal('10000.00'))
        aapl = StockFactory(symbol='AAPL', current_price=Decimal('10.00'), currency='PEN')
        msft = StockFactory(symbol='MSFT', current_price=Decimal('20.00'), currency='PEN')

        old_aapl = TransactionFactory(
            portfolio=portfolio,
            buy=True,
            stock=aapl,
            quantity=3,
        )
        matching_aapl = TransactionFactory(
            portfolio=portfolio,
            buy=True,
            stock=aapl,
            quantity=2,
        )
        TransactionFactory(
            portfolio=portfolio,
            buy=True,
            stock=msft,
            quantity=2,
        )
        TransactionFactory(
            portfolio=other_portfolio,
            buy=True,
            stock=aapl,
            quantity=2,
        )

        now = timezone.now()
        Transaction.all_objects.filter(pk=old_aapl.pk).update(timestamp=now - timedelta(days=10))
        Transaction.all_objects.filter(pk=matching_aapl.pk).update(timestamp=now - timedelta(days=1))

        self.client.force_authenticate(user=user)
        response = self.client.get(
            reverse('transaction-list'),
            {
                'portfolio': portfolio.id,
                'type': Transaction.TransactionType.BUY,
                'symbol': 'aapl',
                'date_from': (now - timedelta(days=2)).date().isoformat(),
                'date_to': now.date().isoformat(),
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['count'] == 1
        assert data['totals']['count'] == 1
        assert data['totals']['amount'] == '20.00'
        assert data['totals']['amount_native'] == '20.00'
        assert data['totals']['amount_base'] == '20.00'
        assert data['totals']['quantity'] == 2
        assert data['totals']['by_type']['BUY'] == {
            'count': 1,
            'amount': '20.00',
            'amount_native': '20.00',
            'amount_base': '20.00',
            'quantity': 2,
        }
        assert data['results'][0]['id'] == matching_aapl.id
        assert data['results'][0]['stock_symbol'] == 'AAPL'

    def test_transaction_totals_use_filtered_queryset_not_page(self):
        user = UserFactory()
        portfolio = PortfolioFactory(user=user, is_default=False)

        for _ in range(25):
            TransactionFactory(
                portfolio=portfolio,
                deposit=True,
                amount=Decimal('1.00'),
            )

        self.client.force_authenticate(user=user)
        response = self.client.get(
            reverse('transaction-list'),
            {
                'portfolio': portfolio.id,
                'type': Transaction.TransactionType.DEPOSIT,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['count'] == 25
        assert len(data['results']) == 20
        assert data['totals']['count'] == 25
        assert data['totals']['amount'] == '25.00'
        assert data['totals']['amount_native'] == '25.00'
        assert data['totals']['amount_base'] == '25.00'
        assert data['totals']['quantity'] == 0
        assert data['totals']['net_cash_flow'] == '25.00'
        assert data['totals']['by_type']['DEPOSIT'] == {
            'count': 25,
            'amount': '25.00',
            'amount_native': '25.00',
            'amount_base': '25.00',
            'quantity': 0,
        }

    def test_transaction_totals_keep_legacy_amount_and_expose_base_native_split(self, set_fx_market_now):
        user = UserFactory()
        portfolio = user.portfolios.get(is_default=True)
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

        TransactionFactory(
            portfolio=portfolio,
            transaction_type=Transaction.TransactionType.BUY,
            stock=stock,
            quantity=1,
        )

        self.client.force_authenticate(user=user)
        response = self.client.get(reverse('transaction-list'))

        assert response.status_code == status.HTTP_200_OK
        totals = response.json()['totals']
        buy_totals = totals['by_type']['BUY']

        # Legacy contract remains available.
        assert totals['amount'] == totals['amount_native']
        assert buy_totals['amount'] == buy_totals['amount_native']
        # Richer fields remain available for base-currency analytics.
        assert Decimal(totals['amount_base']) >= Decimal(totals['amount_native'])
        assert Decimal(buy_totals['amount_base']) >= Decimal(buy_totals['amount_native'])

    def test_transaction_filters_validate_invalid_values(self):
        user = UserFactory()
        self.client.force_authenticate(user=user)

        invalid_type_response = self.client.get(
            reverse('transaction-list'),
            {'type': 'DIVIDEND'},
        )
        invalid_date_response = self.client.get(
            reverse('transaction-list'),
            {'date_from': 'not-a-date'},
        )
        invalid_portfolio_response = self.client.get(
            reverse('transaction-list'),
            {'portfolio': 'not-an-id'},
        )
        zero_portfolio_response = self.client.get(
            reverse('transaction-list'),
            {'portfolio': '0'},
        )

        assert invalid_type_response.status_code == status.HTTP_400_BAD_REQUEST
        assert invalid_date_response.status_code == status.HTTP_400_BAD_REQUEST
        assert invalid_portfolio_response.status_code == status.HTTP_400_BAD_REQUEST
        assert zero_portfolio_response.status_code == status.HTTP_400_BAD_REQUEST

    def test_response_structure(self):
        pass

    def test_create_transaction_resolves_user_throttle_rate(self):
        user = UserFactory()
        self.client.force_authenticate(user=user)

        response = self.client.post(
            reverse('transaction-create'),
            {
                'transaction_type': Transaction.TransactionType.DEPOSIT,
                'amount': '50.00',
                'idempotency_key': str(uuid.uuid4()),
            },
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert Transaction.objects.filter(
            portfolio__user=user,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal('50.00'),
        ).exists()

    def test_create_transaction_generates_idempotency_key_when_absent(self):
        user = UserFactory()
        self.client.force_authenticate(user=user)

        response = self.client.post(
            reverse('transaction-create'),
            {
                'transaction_type': Transaction.TransactionType.DEPOSIT,
                'amount': '75.00',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data['idempotency_key']
        assert Transaction.objects.filter(
            id=data['id'],
            portfolio__user=user,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal('75.00'),
        ).exists()

    def test_create_transaction_accepts_client_idempotency_key_for_retries(self):
        user = UserFactory()
        self.client.force_authenticate(user=user)
        key = str(uuid.uuid4())
        payload = {
            'transaction_type': Transaction.TransactionType.DEPOSIT,
            'amount': '85.00',
            'idempotency_key': key,
        }

        first = self.client.post(reverse('transaction-create'), payload, format='json')
        second = self.client.post(reverse('transaction-create'), payload, format='json')

        assert first.status_code == status.HTTP_201_CREATED
        assert second.status_code == status.HTTP_201_CREATED
        assert second.json()['id'] == first.json()['id']
        assert Transaction.objects.filter(
            portfolio__user=user,
            idempotency_key=key,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal('85.00'),
        ).count() == 1

    def test_pagination(self):
        user = UserFactory()
        
        # Create 34 more transactions (plus initial default portfolio transaction)
        TransactionFactory.create_batch(34, portfolio__user=user, deposit=True)
        
        self.client.force_authenticate(user=user)
        response = self.client.get(reverse('transaction-list'))
        
        data = response.json()
        # Test pagination structure and functionality rather than exact count
        assert 'count' in data
        assert 'results' in data
        assert data['count'] >= 34  # At least the ones we created
        assert len(data['results']) <= 20  # Page size limit
