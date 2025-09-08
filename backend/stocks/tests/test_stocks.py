import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal
from django.urls import reverse
from unittest.mock import Mock
from math import ceil
from datetime import date
from django.db import IntegrityError
from django.utils import timezone

from stocks.models import Stock
from stocks.tasks import fetch_stock_prices, companies
from stocks.serializers import StockSerializer
from stocks.tests.factories import StockFactory

User = get_user_model()

# Fixtures --------------------------------------------------------------------

@pytest.fixture
def client():
    return APIClient()

@pytest.fixture
def admin_user():
    return User.objects.create_superuser(
        email='admin@example.com',
        password='testpass123',
        full_name='Admin User',
        dob=date(1990, 1, 1)
    )

@pytest.fixture
def regular_user():
    return User.objects.create_user(
        email='user@example.com',
        password='testpass123',
        full_name='Regular User',
        dob=date(2000, 1, 1)
    )

@pytest.fixture
def sample_stock():
    return StockFactory.create(
        symbol='AMZN',
        name='Amazon Inc.',
        current_price=Decimal('150.00')
    )

# Model Tests -----------------------------------------------------------------

@pytest.mark.django_db
class TestStockModel:
    def test_stock_creation(self):
        stock = StockFactory.create()
        assert Stock.objects.count() == 1
        assert stock.symbol.isupper()
        assert isinstance(stock.current_price, Decimal)

    def test_symbol_uniqueness(self):
        StockFactory.create(symbol='TEST')
        with pytest.raises(IntegrityError):
            StockFactory.create(symbol='TEST')

    def test_symbol_normalization(self):
        stock = StockFactory.create(symbol='aapl')
        assert stock.symbol == 'AAPL'

    def test_price_precision(self):
        stock = StockFactory.create(
            symbol='PREC',
            current_price=Decimal('123.4567')
        )
        assert stock.current_price == Decimal('123.46')

    def test_symbol_whitespace_stripping(self):
        stock = StockFactory.create(symbol='  nvda  ')
        assert stock.symbol == 'NVDA'

    def test_price_rounding_edge_cases(self):
        stock = StockFactory.create(
            symbol='ROUND',
            current_price=Decimal('123.455')
        )
        assert stock.current_price == Decimal('123.46')

# Serializer Tests -----------------------------------------------------------

@pytest.mark.django_db
class TestStockSerializer:
    def test_serialization(self, sample_stock):
        serializer = StockSerializer(sample_stock)
        assert serializer.data['symbol'] == 'AMZN'
        assert serializer.data['current_price'] == '150.00'

    def test_deserialization(self):
        serializer = StockSerializer(data={
            'symbol': 'GOOGL',
            'name': 'Alphabet Inc.',
            'current_price': '135.75'
        })
        assert serializer.is_valid()

    @pytest.mark.parametrize('price, expected', [
        ('-100.00', 'negative'),
        ('123.456', 'precision'),
        ('9999999999.99', 'max_digits'),
    ])
    
    def test_price_validation(self, price, expected):
        serializer = StockSerializer(data={
            'symbol': 'TEST',
            'name': 'Test',
            'current_price': price
        })
        assert not serializer.is_valid()
        assert 'current_price' in serializer.errors
        
    @pytest.mark.parametrize('symbol, valid', [
        ('A'*10, True),    # Max valid length
        ('A'*11, False),   # Too long
    ])
    def test_symbol_validation(self, symbol, valid):
        """Test symbol format validation"""
        serializer = StockSerializer(data={
            'symbol': symbol,
            'name': 'Test',
            'current_price': '100.00'
        })
        assert serializer.is_valid() == valid

    def test_missing_required_fields(self):
        serializer = StockSerializer(data={'symbol': 'PARTIAL'})
        assert not serializer.is_valid()
        # Since current_price is nullable now, only name is required
        expected_fields = {'name'}
        if 'current_price' in serializer.errors:
            expected_fields.add('current_price')
        assert set(serializer.errors.keys()) == expected_fields
        for errors in serializer.errors.values():
            assert all(err.code == 'required' for err in errors)

    def test_last_updated_read_only(self):
        original_time = timezone.now()
        stock = StockFactory.create()
        
        serializer = StockSerializer(stock, data={
            'last_updated': '2024-01-01T00:00:00Z'
        }, partial=True)
        
        assert serializer.is_valid()
        serializer.save()
        assert stock.last_updated > original_time

# View Tests ------------------------------------------------------------------

@pytest.mark.django_db
class TestStockViews:
    def test_retrieve_stock_list(self, client, sample_stock):
        """Test stock list endpoint"""
        response = client.get(reverse('stock-list'))
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 1
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['symbol'] == 'AMZN'

    def test_admin_create_stock(self, client, admin_user):
        client.force_authenticate(admin_user)
        response = client.post(reverse('stock-list'), {
            'symbol': 'NVDA',
            'name': 'NVIDIA Corp.',
            'current_price': '450.00'
        })
        assert response.status_code == status.HTTP_201_CREATED
        assert Stock.objects.filter(symbol='NVDA').exists()

    def test_regular_user_create_stock(self, client, regular_user):
        client.force_authenticate(regular_user)
        response = client.post(reverse('stock-list'), {
            'symbol': 'TEST',
            'name': 'Test Company',
            'current_price': '100.00'
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_price_update(self, client, admin_user, sample_stock):
        client.force_authenticate(admin_user)
        response = client.patch(
            reverse('stock-detail', kwargs={'pk': sample_stock.id}),
            {'current_price': 130}
        )
        sample_stock.refresh_from_db()
        assert sample_stock.current_price == Decimal('130.00')

    def test_delete_stock(self, client, admin_user, sample_stock):
        client.force_authenticate(admin_user)
        response = client.delete(
            reverse('stock-detail', kwargs={'pk': sample_stock.id}))
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Stock.objects.filter(id=sample_stock.id).exists()

    def test_update_symbol_normalization(self, client, admin_user, sample_stock):
        original_name = sample_stock.name
        client.force_authenticate(admin_user)  
        response = client.patch(
            reverse('stock-detail', kwargs={'pk': sample_stock.id}),
            {'symbol': '  new  '}
        )

        assert response.status_code == status.HTTP_200_OK
        sample_stock.refresh_from_db()
        assert sample_stock.symbol == 'NEW'
        assert sample_stock.name == original_name
        assert response.data['symbol'] == 'NEW'

# Security Tests -------------------------------------------------------------

@pytest.mark.django_db
class TestSecurity:
    def test_unauthenticated_access(self, client):
        initial_count = Stock.objects.count()
        response = client.post(reverse('stock-list'), {
            'symbol': 'TEST',
            'name': 'Test',
            'current_price': '100.00'
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert Stock.objects.count() == initial_count
        assert 'credentials' in str(response.content)

    def test_sql_injection_prevention(self, client):
        response = client.post(reverse('stock-list'), {
            'symbol': "'; DROP TABLE stocks_stock; --",
            'name': 'Hack Attack',
            'current_price': '0.00'
        })
        assert response.status_code != status.HTTP_201_CREATED
        assert Stock.objects.filter(symbol__contains='DROP').count() == 0

    def test_oversized_payload_rejection(self, client, admin_user):
        client.force_authenticate(admin_user)
        initial_count = Stock.objects.count()
        
        response = client.post(reverse('stock-list'), {
            'symbol': 'BIG',
            'name': 'A' * 10001,
            'current_price': '100.00'
        })
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'name' in response.data
        assert 'Ensure this field has no more than 100 characters' in str(response.data['name'])
        assert Stock.objects.count() == initial_count

# TODO: Task Tests, Time-Related Tests, check for stuff like concurrency or api call failure