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
    return Stock.objects.create(
        symbol='AMZN',
        name='Amazon Inc.',
        current_price=Decimal('150.00')
    )

# Model Tests -----------------------------------------------------------------

@pytest.mark.django_db
class TestStockModel:
    def test_stock_creation(self):
        """Test basic stock model creation"""
        stock = Stock.objects.create(
            symbol='AAPL',
            name='Apple Inc.',
            current_price=Decimal('185.50')
        )
        assert stock.symbol == 'AAPL'
        assert stock.name == 'Apple Inc.'
        assert stock.current_price == Decimal('185.50')
        assert stock.last_updated is not None

    def test_symbol_uniqueness(self):
        """Test unique symbol constraint"""
        Stock.objects.create(symbol='TEST', name='Test', current_price=100)
        with pytest.raises(IntegrityError):
            Stock.objects.create(symbol='TEST', name='Test Duplicate', current_price=200)

    def test_symbol_normalization(self):
        """Test automatic symbol uppercasing"""
        stock = Stock.objects.create(symbol='aapl', name='Test', current_price=100)
        assert stock.symbol == 'AAPL'

    def test_price_precision(self):
        """Test decimal price storage"""
        stock = Stock.objects.create(
            symbol='PREC',
            name='Precision Test',
            current_price=Decimal('123.4567')
        )
        assert stock.current_price == Decimal('123.46')

    def test_symbol_whitespace_stripping(self):
        """Test whitespace removal in symbols"""
        stock = Stock.objects.create(symbol='  nvda  ', name='Test', current_price=100)
        assert stock.symbol == 'NVDA'

    def test_price_rounding_edge_cases(self):
        """Test rounding behavior for exact halfway values"""
        stock = Stock.objects.create(
            symbol='ROUND',
            name='Rounding Test',
            current_price=Decimal('123.455')
        )
        assert stock.current_price == Decimal('123.46')

# Serializer Tests -----------------------------------------------------------

@pytest.mark.django_db
class TestStockSerializer:
    def test_valid_data(self):
        """Test valid serializer data"""
        data = {
            'symbol': 'GOOGL',
            'name': 'Alphabet Inc.',
            'current_price': '135.75'
        }
        assert StockSerializer(data=data).is_valid()

    @pytest.mark.parametrize('price, expected', [
        ('-100.00', 'negative'),
        ('123.456', 'precision'),
        ('9999999999.99', 'max_digits'),
    ])
    def test_price_validation(self, price, expected):
        """Test various price validation scenarios"""
        data = {
            'symbol': 'TEST',
            'name': 'Test',
            'current_price': price
        }
        serializer = StockSerializer(data=data)
        assert not serializer.is_valid()
        assert 'current_price' in serializer.errors

    @pytest.mark.parametrize('symbol, valid', [
        ('A'*10, True),    # Max valid length
        ('A'*11, False),   # Too long
    ])
    def test_symbol_validation(self, symbol, valid):
        """Test symbol format validation"""
        data = {
            'symbol': symbol,
            'name': 'Test',
            'current_price': '100.00'
        }
        serializer = StockSerializer(data=data)
        assert serializer.is_valid() == valid

    def test_missing_required_fields(self):
        """Test required field validation"""
        data = {'symbol': 'MISSING'}
        serializer = StockSerializer(data=data)
        assert not serializer.is_valid()
        assert 'name' in serializer.errors
        assert 'current_price' in serializer.errors

    def test_last_updated_read_only(self):
        """Test that last_updated cannot be modified"""
        data = {
            'symbol': 'TEST',
            'name': 'Test',
            'current_price': '100.00',
            'last_updated': '2024-01-01T00:00:00Z'
        }
        serializer = StockSerializer(data=data)
        assert serializer.is_valid()
        assert 'last_updated' not in serializer.validated_data

    


# View Tests ------------------------------------------------------------------

@pytest.mark.django_db
class TestStockViews:
    def test_retrieve_stock_list(self, client, sample_stock):
        """Test stock list endpoint"""
        response = client.get(reverse('stock-list'))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    def test_admin_create_stock(self, client, admin_user):
        """Test admin creation privileges"""
        client.force_authenticate(admin_user)
        response = client.post(reverse('stock-list'), {
            'symbol': 'NVDA',
            'name': 'NVIDIA Corp.',
            'current_price': '450.00'
        })
        assert response.status_code == status.HTTP_201_CREATED

    def test_regular_user_create_stock(self, client, regular_user):
        """Test regular user creation restrictions"""
        client.force_authenticate(regular_user)
        response = client.post(reverse('stock-list'), {
            'symbol': 'TEST',
            'name': 'Test Company',
            'current_price': '100.00'
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_price_update(self, client, admin_user, sample_stock):
        """Test stock price update functionality"""
        client.force_authenticate(admin_user)
        response = client.patch(
            reverse('stock-detail', kwargs={'pk': sample_stock.id}),
            {'current_price': 130}
        )
        assert response.status_code == status.HTTP_200_OK
        sample_stock.refresh_from_db()
        assert sample_stock.current_price == 130

    def test_delete_stock(self, client, admin_user, sample_stock):
        """Test stock deletion"""
        client.force_authenticate(admin_user)
        response = client.delete(
            reverse('stock-detail', kwargs={'pk': sample_stock.id})
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Stock.objects.filter(id=sample_stock.id).exists()

    def test_update_symbol_normalization(self, client, admin_user, sample_stock):
        """Test symbol normalization during updates"""
        client.force_authenticate(admin_user)
        response = client.patch(
            reverse('stock-detail', kwargs={'pk': sample_stock.id}),
            {'symbol': '  new  '}
        )
        assert response.status_code == status.HTTP_200_OK
        sample_stock.refresh_from_db()
        assert sample_stock.symbol == 'NEW'

# Security Tests -------------------------------------------------------------

@pytest.mark.django_db
class TestSecurity:
    def test_unauthenticated_access(self, client):
        """Test anonymous user restrictions"""
        response = client.post(reverse('stock-list'), {
            'symbol': 'TEST',
            'name': 'Test',
            'current_price': '100.00'
        })
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED, 
            status.HTTP_403_FORBIDDEN
        ]

    def test_sql_injection_prevention(self, client):
        """Test SQL injection protection"""
        response = client.post(reverse('stock-list'), {
            'symbol': "'; DROP TABLE stocks_stock; --",
            'name': 'Hack Attack',
            'current_price': '0.00'
        })
        assert response.status_code != status.HTTP_201_CREATED
        assert Stock.objects.filter(symbol__contains='DROP').count() == 0

    def test_oversized_payload_rejection(self, client, admin_user):
        """Test payload size validation"""
        client.force_authenticate(admin_user)
        response = client.post(reverse('stock-list'), {
            'symbol': 'BIG',
            'name': 'A' * 10001,
            'current_price': '100.00'
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

# TODO: Task Tests, Time-Related Tests, check for stuff like concurrency or api call failure