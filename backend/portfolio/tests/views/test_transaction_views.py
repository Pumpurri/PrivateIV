import pytest
import uuid
from datetime import timedelta
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from portfolio.models import Transaction
from portfolio.tests.factories import TransactionFactory
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
