import pytest
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
        url = reverse('transaction-history')
        response = self.client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_authenticated_user_sees_only_their_transactions(self):
        user1 = UserFactory()
        user2 = UserFactory()

        t1 = TransactionFactory(
            portfolio__user=user1,
            buy=True,
            stock=StockFactory(current_price=Decimal('50.00')),
            quantity=100
        )
        t2 = TransactionFactory(portfolio__user=user2, deposit=True)

        self.client.force_authenticate(user=user1)
        response = self.client.get(reverse('transaction-history'))
        assert response.status_code == status.HTTP_200_OK
        results = response.json()['results']

        transaction_ids = [str(item['id']) for item in results]
        assert str(t1.id) in transaction_ids
        assert len(results) == 1


    def test_filtering_functionality(self):
        user = UserFactory()
        portfolio1 = user.portfolios.first()

        stocks = [
            StockFactory(current_price=Decimal('30.00')), 
            StockFactory(current_price=Decimal('30.00')),
            StockFactory(current_price=Decimal('30.00'))
        ]
        for stock in stocks:
            TransactionFactory(
                portfolio=portfolio1,
                buy=True,
                stock=stock,
                quantity=30,
            )

        self.client.force_authenticate(user=user)
        response = self.client.get(f"{reverse('transaction-history')}?portfolio={portfolio1.id}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['count'] == 3 

    def test_response_structure(self):
        user = UserFactory()
        transaction = TransactionFactory(portfolio__user=user, buy=True)
        
        self.client.force_authenticate(user=user)
        response = self.client.get(reverse('transaction-history'))
        
        result = response.json()['results'][0]
        assert all(field in result for field in [
            'id', 'transaction_type', 'stock_symbol', 
            'stock_name', 'quantity', 'executed_price',
            'amount', 'timestamp', 'portfolio_id'
        ])
        assert result['transaction_type'] == 'Buy Order'

    def test_pagination(self):
        user = UserFactory()
        TransactionFactory.create_batch(35, portfolio__user=user, deposit=True)

        self.client.force_authenticate(user=user)
        response = self.client.get(reverse('transaction-history'))
        
        data = response.json()
        assert data['count'] == 35
        assert len(data['results']) == 10  # Default page size
        assert 'next' in data

    def test_ordering(self):
        user = UserFactory()
        TransactionFactory.create_batch(
            5, 
            portfolio__user=user,
            deposit=True
        )
        
        self.client.force_authenticate(user=user)
        response = self.client.get(reverse('transaction-history'))
        
        timestamps = [t['timestamp'] for t in response.json()['results']]
        assert timestamps == sorted(timestamps, reverse=True)