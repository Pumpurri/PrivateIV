import pytest
from decimal import Decimal
from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError
from portfolio.models import Holding
from portfolio.tests.factories import HoldingFactory, PortfolioFactory
from stocks.tests.factories import StockFactory

# Fixtures --------------------------------------------------------------------
@pytest.fixture
def portfolio():
    return PortfolioFactory()

@pytest.fixture
def stock():
    return StockFactory(current_price=Decimal('100.00'))

# Core Functionality Tests ----------------------------------------------------
@pytest.mark.django_db
class TestHoldingManager:
    def test_create_new_position(self, portfolio, stock):
        """Test initial purchase creates new holding"""
        holding = Holding.objects.process_purchase(
            portfolio=portfolio,
            stock=stock,
            quantity=100,
            price_per_share=Decimal('50.00')
        )
        
        assert holding.quantity == 100
        assert holding.average_purchase_price == Decimal('50.00')
        assert portfolio.holdings.count() == 1

    def test_average_price_calculation(self, portfolio, stock):
        """Test multiple purchases average correctly"""
        # First purchase
        Holding.objects.process_purchase(
            portfolio, stock, 100, Decimal('50.00'))
        
        # Second purchase
        holding = Holding.objects.process_purchase(
            portfolio, stock, 100, Decimal('100.00'))
        
        assert holding.quantity == 200
        assert holding.average_purchase_price == Decimal('75.00')

    def test_full_sale(self, portfolio, stock):
        """Test selling entire position deletes holding"""
        holding = HoldingFactory(
            portfolio=portfolio,
            stock=stock,
            quantity=100,
            average_purchase_price=Decimal('50.00')
        )
        
        Holding.objects.process_sale(portfolio, stock, 100)
        assert not Holding.objects.filter(id=holding.id).exists()

    def test_partial_sale(self, portfolio, stock):
        """Test partial sale updates quantity"""
        holding = HoldingFactory(
            portfolio=portfolio,
            stock=stock,
            quantity=100,
            average_purchase_price=Decimal('50.00')
        )
        
        updated = Holding.objects.process_sale(portfolio, stock, 40)
        assert updated.quantity == 60
        assert Holding.objects.filter(id=holding.id).exists()

    def test_sell_nonexistent_position(self, portfolio, stock):
        """Test selling unheld stock raises error"""
        with pytest.raises(ValidationError) as exc:
            Holding.objects.process_sale(portfolio, stock, 10)
        assert "Cannot sell stock not held" in str(exc.value)

    def test_overselling_position(self, portfolio, stock):
        """Test selling more shares than held"""
        HoldingFactory(
            portfolio=portfolio,
            stock=stock,
            quantity=100,
            average_purchase_price=Decimal('50.00')
        )
        
        with pytest.raises(ValidationError) as exc:
            Holding.objects.process_sale(portfolio, stock, 150)
        assert "Insufficient shares" in str(exc.value)

# Model Validation Tests ------------------------------------------------------
@pytest.mark.django_db
class TestHoldingModel:
    def test_current_value_calculation(self, stock):
        holding = HoldingFactory(
            quantity=100,
            average_purchase_price=Decimal('50.00'),
            stock=stock
        )
        stock.current_price = Decimal('75.00')
        assert holding.current_value == Decimal('7500.00')

    def test_gain_loss_calculation(self, stock):
        holding = HoldingFactory(
            quantity=100,
            average_purchase_price=Decimal('50.00'),
            stock=stock
        )
        stock.current_price = Decimal('60.00')
        assert holding.gain_loss == Decimal('1000.00')

    def test_negative_quantity_validation(self):
        holding = HoldingFactory.build(quantity=-10)
        with pytest.raises(ValidationError) as excinfo:
            holding.full_clean()
        assert 'quantity' in excinfo.value.message_dict

    def test_zero_price_validation(self):
        holding = HoldingFactory.build(average_purchase_price=Decimal('0.00')) 
        with pytest.raises(ValidationError) as excinfo:
            holding.full_clean()
        assert 'average_purchase_price' in excinfo.value.message_dict

    def test_unique_portfolio_stock_constraint(self, portfolio, stock):
        HoldingFactory(portfolio=portfolio, stock=stock)
        with pytest.raises(IntegrityError):
            HoldingFactory(portfolio=portfolio, stock=stock)