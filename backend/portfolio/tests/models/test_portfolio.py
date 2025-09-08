import pytest
from decimal import Decimal
from django.db import IntegrityError, transaction
from django.test import override_settings
from portfolio.models import Portfolio, Holding, Transaction
from users.tests.factories import UserFactory
from stocks.tests.factories import StockFactory
from portfolio.tests.factories import HoldingFactory
from django.core.exceptions import ValidationError
from portfolio.tests.factories import TransactionFactory

# Fixtures --------------------------------------------------------------------
@pytest.fixture
def user():
    """User with default portfolio created via signals"""
    return UserFactory()

@pytest.fixture
def portfolio(user):
    """User's default portfolio"""
    return user.portfolios.get(is_default=True)

@pytest.fixture
def sample_stock():
    return StockFactory(current_price=Decimal('150.00'))

# Model Tests -----------------------------------------------------------------
@pytest.mark.django_db
class TestPortfolioModel:
    def test_default_portfolio_creation_via_signal(self, user):
        """Test automatic portfolio creation through Django signals"""
        assert Portfolio.objects.filter(user=user, is_default=True).exists()
        portfolio = user.portfolios.get(is_default=True)
        assert portfolio.cash_balance == Decimal('10000.00')

    @override_settings(DISABLE_SIGNALS=True)
    def test_unique_default_portfolio_constraint(self, user):
        """Test user can't have multiple default portfolios"""
        with transaction.atomic():
            test_user = UserFactory()
            
            Portfolio.objects.create(
                user=test_user,
                is_default=True,
                cash_balance=Decimal('10000.00')
            )
            
            with pytest.raises(IntegrityError) as excinfo:
                Portfolio.objects.create(
                    user=test_user,
                    is_default=True,
                    cash_balance=Decimal('20000.00')
                )
            # SQLite and PostgreSQL have different constraint error messages
            error_msg = str(excinfo.value).lower()
            assert any(phrase in error_msg for phrase in [
                'unique_default_portfolio', 
                'unique constraint failed',
                'portfolio.user_id, portfolio.is_default'
            ])

    def test_non_default_portfolio_creation(self, user):
        """Test creation of additional non-default portfolios"""
        portfolio = Portfolio.objects.create(user=user, is_default=False)
        assert portfolio.is_default is False
        assert user.portfolios.count() == 2

    def test_string_representation(self, portfolio):
        """Test __str__ method"""
        assert str(portfolio) == f"{portfolio.user.email}'s Portfolio"

@pytest.mark.django_db
class TestPortfolioCashManagement:
    def test_cash_adjustment_increases_balance(self, portfolio):
        """Test positive cash adjustment"""
        initial_balance = portfolio.cash_balance
        adjustment = Decimal('5000.00')
        portfolio.adjust_cash(adjustment)
        portfolio.refresh_from_db()
        assert portfolio.cash_balance == initial_balance + adjustment

    def test_cash_adjustment_decreases_balance(self, portfolio):
        """Test valid negative cash adjustment"""
        portfolio.cash_balance = Decimal('10000.00')
        portfolio.save()
        portfolio.adjust_cash(Decimal('-5000.00'))
        portfolio.refresh_from_db()
        assert portfolio.cash_balance == Decimal('5000.00')

    def test_insufficient_funds_validation(self, portfolio):
        """Test overdraft prevention"""
        with pytest.raises(ValidationError) as exc:
            portfolio.adjust_cash(Decimal('-15000.00'))
        assert "Insufficient funds" in str(exc.value)
        assert portfolio.cash_balance == Decimal('10000.00')

    def test_zero_cash_adjustment(self, portfolio):
        """Test edge case of zero adjustment"""
        initial_balance = portfolio.cash_balance
        portfolio.adjust_cash(Decimal('0.00'))
        portfolio.refresh_from_db()
        assert portfolio.cash_balance == initial_balance

@pytest.mark.django_db
class TestPortfolioValuation:
    def test_empty_portfolio_valuation(self, portfolio):
        """Test valuation of portfolio with no holdings"""
        assert portfolio.total_value == portfolio.cash_balance
        assert portfolio.investment_value == Decimal('0.00')

    def test_single_holding_valuation(self, portfolio, sample_stock):
        """Test valuation with one holding"""
        HoldingFactory.create(
            portfolio=portfolio,
            stock=sample_stock,
            quantity=100,
            average_purchase_price=sample_stock.current_price
        )
        expected_investment = 100 * sample_stock.current_price
        assert portfolio.investment_value == expected_investment
        assert portfolio.total_value == portfolio.cash_balance + expected_investment

    def test_multiple_holdings_valuation(self, portfolio):
        """Test valuation with multiple holdings"""
        stocks = [
            StockFactory(current_price=Decimal('200.00')),
            StockFactory(current_price=Decimal('300.00'))
        ]
        
        for stock in stocks:
            HoldingFactory(
                portfolio=portfolio,
                stock=stock,
                quantity=50,
                average_purchase_price=stock.current_price
            )
        
        expected_investment = sum(50 * stock.current_price for stock in stocks)
        assert portfolio.investment_value == expected_investment
        assert portfolio.total_value == portfolio.cash_balance + expected_investment

    def test_updated_valuation_after_price_change(self, portfolio, sample_stock):
        """Test valuation updates when stock prices change"""
        holding = HoldingFactory.create(
            portfolio=portfolio,
            stock=sample_stock,
            quantity=100,
            average_purchase_price=Decimal('100.00')
        )
        
        sample_stock.current_price = Decimal('200.00')
        sample_stock.save()
        
        portfolio.refresh_from_db()
        assert portfolio.investment_value == 100 * sample_stock.current_price
        assert portfolio.total_value == portfolio.cash_balance + (Decimal(100) * Decimal(200.00))


    def test_precision_handling_in_cash_adjustments(self, portfolio):
        """Test decimal precision maintenance"""
        portfolio.cash_balance = Decimal('0.00')
        portfolio.save()
        portfolio.adjust_cash(Decimal('1234.5678'))
        assert portfolio.cash_balance == Decimal('1234.57')

    def test_max_cash_value_handling(self, portfolio):
        """Test maximum cash value within field constraints"""
        max_value = Decimal('9999999999999.99') 
        portfolio.adjust_cash(max_value - portfolio.cash_balance)
        assert portfolio.cash_balance == max_value

    def test_valuation_with_zero_price_stock(self, portfolio):
        """Test handling of stocks with 0 price"""
        stock = StockFactory(current_price=Decimal('0.00'))
        HoldingFactory(portfolio=portfolio, stock=stock, quantity=100)
        assert portfolio.investment_value == Decimal('0.00')

    def test_negative_cash_edge_case(self):
        """Test portfolio creation with negative cash (should be impossible)"""
        user = UserFactory()
        portfolio = Portfolio(user=user, cash_balance=Decimal('-100.00'))
        with pytest.raises(ValidationError):
            portfolio.full_clean()
            portfolio.save()

    def test_insufficient_funds_buy(self, portfolio, stock):
        with pytest.raises(ValidationError):
            transaction = Transaction(
                portfolio=portfolio,
                transaction_type=Transaction.TransactionType.BUY,
                stock=stock,
                quantity=1000,
                amount=0  
            )
            transaction.full_clean()
            transaction.save()
    
    def test_portfolio_archive_soft_delete(self, portfolio):
        # Create a non-default portfolio for testing archival (soft-delete)
        test_portfolio = Portfolio.objects.create(
            user=portfolio.user,
            name="Test Portfolio",
            is_default=False,
            cash_balance=Decimal('10000.00')
        )

        stock = StockFactory(current_price=Decimal('100.00'))

        # Create through manager to ensure proper relationships
        holding = test_portfolio.holdings.process_purchase(
            portfolio=test_portfolio,
            stock=stock,
            quantity=100,
            price_per_share=Decimal('100.00')
        )

        transaction = TransactionFactory(
            portfolio=test_portfolio,
            transaction_type='BUY',
            stock=stock,
            quantity=100,
        )

        # Archive the portfolio
        test_portfolio.delete()

        # Portfolio should be soft-deleted
        test_portfolio.refresh_from_db()
        assert test_portfolio.is_deleted is True
        assert test_portfolio.deleted_at is not None

        # Holdings should be deactivated but retained for audit/history
        assert Holding.objects.filter(id=holding.id).exists()
        assert Holding.objects.get(id=holding.id).is_active is False

        # Transactions should remain for historical accuracy (use all_objects to bypass active filter)
        assert Transaction.all_objects.filter(id=transaction.id).exists()
 
    def test_micro_adjustments(self, portfolio):
        portfolio.cash_balance = Decimal('0.00')
        portfolio.save()
        portfolio.adjust_cash(Decimal('0.001'))
        assert portfolio.cash_balance == Decimal('0.00')
        portfolio.adjust_cash(Decimal('0.009'))
        assert portfolio.cash_balance == Decimal('0.01')

    def test_transaction_auto_amount_calculation(self, portfolio, stock):
        stock.current_price = Decimal('150.00')
        stock.save()
        
        transaction = TransactionFactory(
            portfolio=portfolio,
            transaction_type=Transaction.TransactionType.BUY,
            stock=stock,
            quantity=10
        )
        
        transaction.refresh_from_db()
        expected_amount = 10 * stock.current_price
        assert transaction.amount == expected_amount
        assert transaction.executed_price == stock.current_price

    def test_updates_value_when_stock_prices_change(self, portfolio, sample_stock):
        holding = HoldingFactory.create(
            portfolio=portfolio,
            stock=sample_stock,
            quantity=100,
            average_purchase_price=sample_stock.current_price
        )
        
        original_value = portfolio.investment_value
        new_price = sample_stock.current_price * Decimal('2')
        sample_stock.current_price = new_price
        sample_stock.save()
        
        portfolio.refresh_from_db()
        assert portfolio.investment_value == 100 * new_price
        assert portfolio.total_value == portfolio.cash_balance + (100 * new_price)

    def test_handles_zero_value_holdings(self, portfolio):
        zero_stock = StockFactory(current_price=Decimal('0.00'))
        HoldingFactory.create(
            portfolio=portfolio,
            stock=zero_stock,
            quantity=500,
            average_purchase_price=Decimal('50.00')
        )
        
        assert portfolio.investment_value == Decimal('0.00')
        assert portfolio.total_value == portfolio.cash_balance
