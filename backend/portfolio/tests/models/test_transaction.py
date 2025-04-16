import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from portfolio.models import Transaction, Holding
from portfolio.tests.factories import TransactionFactory
from stocks.tests.factories import StockFactory

# Fixtures --------------------------------------------------------------------
@pytest.fixture
def buy_transaction(funded_portfolio, stock):
    return TransactionFactory(
        portfolio=funded_portfolio,
        transaction_type='BUY',
        stock=stock,
        quantity=10,
    )

@pytest.fixture
def sell_transaction(portfolio_with_holding):
    portfolio = portfolio_with_holding['portfolio']
    holding = portfolio_with_holding['holding']
    return TransactionFactory(
        portfolio=portfolio,
        transaction_type='SELL',
        stock=holding.stock,
        quantity=5,
    )

# Model Tests -----------------------------------------------------------------
@pytest.mark.django_db
class TestTransactionModel:
    def test_transaction_creation(self, buy_transaction):
        assert Transaction.objects.count() == 1
        assert buy_transaction.portfolio.user.email is not None
        assert str(buy_transaction) == f"BUY - {buy_transaction.amount}$"

    def test_transaction_type_validation(self):
        with pytest.raises(ValidationError) as exc:
            TransactionFactory(transaction_type='INVALID')
        assert "is not a valid choice" in str(exc.value)

    def test_buy_transaction_validation(self, funded_portfolio):
        with pytest.raises(ValidationError) as exc:
            Transaction.objects.create(
                portfolio=funded_portfolio,
                transaction_type='BUY',
                quantity=10
            )
        assert "Stock required for trade transactions" in str(exc.value)

    def test_deposit_transaction_validation(self, funded_portfolio):
        with pytest.raises(ValidationError) as exc:
            Transaction.objects.create(
                portfolio=funded_portfolio,
                transaction_type='DEPOSIT',
                stock=StockFactory()
            )
        assert "Stock must be null for non-trade transactions" in str(exc.value)

    def test_transaction_price_auto_calculation(self, funded_portfolio, stock):
        stock.current_price = Decimal('150.00')
        stock.save()
        
        t = Transaction.objects.create(
            portfolio=funded_portfolio,
            transaction_type='BUY',
            stock=stock,
            quantity=10
        )
        t.refresh_from_db()
        assert t.executed_price == stock.current_price
        assert t.amount == Decimal('1500.00')

    def test_transaction_immutability(self, buy_transaction):
        with pytest.raises(ValidationError):
            buy_transaction.transaction_type = 'SELL'
            buy_transaction.full_clean()

# Service Tests ---------------------------------------------------------------
@pytest.mark.django_db
class TestTransactionService:
    def test_buy_transaction_processing(self, funded_portfolio, stock):
        stock.current_price = Decimal('100.00')
        stock.save()
        
        transaction = TransactionFactory.build(
            portfolio=funded_portfolio,
            transaction_type='BUY',
            stock=stock,
            quantity=10
        )
        
        initial_cash = funded_portfolio.cash_balance
        assert initial_cash == Decimal('10000.00'), "Initial cash not set correctly"

        transaction.save()
        
        funded_portfolio.refresh_from_db()
        transaction.refresh_from_db()
        
        expected_cash = initial_cash - (transaction.quantity * stock.current_price)
        assert funded_portfolio.cash_balance == expected_cash, "Cash not deducted properly"
        assert transaction.amount == transaction.quantity * stock.current_price
        assert funded_portfolio.holdings.count() == 1


    def test_sell_transaction_processing(self, portfolio_with_holding):
        portfolio = portfolio_with_holding['portfolio']
        holding = portfolio_with_holding['holding']
        
        stock = holding.stock
        stock.current_price = Decimal('100.00')
        stock.save()
        
        transaction = TransactionFactory.build(
            portfolio=portfolio,
            transaction_type='SELL',
            stock=stock,
            quantity=5
        )
        
        initial_cash = portfolio.cash_balance
        initial_quantity = holding.quantity
        
        transaction.save()
        
        portfolio.refresh_from_db()
        transaction.refresh_from_db()
        
        expected_cash = initial_cash + (transaction.quantity * stock.current_price)
        assert portfolio.cash_balance == expected_cash, "Cash not added properly"
        assert portfolio.holdings.get(stock=stock).quantity == initial_quantity - transaction.quantity

    def test_deposit_processing(self, funded_portfolio):
        initial_balance = funded_portfolio.cash_balance
        deposit = TransactionFactory(
            portfolio=funded_portfolio,
            transaction_type='DEPOSIT',
            amount=Decimal('5000.00')
        )
        
        deposit.save()
        
        funded_portfolio.refresh_from_db()
        assert funded_portfolio.cash_balance == initial_balance + deposit.amount

    def test_insufficient_funds_buy(self, funded_portfolio, stock):
        with pytest.raises(ValidationError), transaction.atomic():
            t = Transaction.objects.create(
                portfolio=funded_portfolio,
                transaction_type='BUY',
                stock=stock,
                quantity=100000  # Impossible quantity
            )
            t.save()

    def test_sell_nonexistent_holding(self, funded_portfolio, stock):
        with pytest.raises(ValidationError), transaction.atomic():
            t = Transaction.objects.create(
                portfolio=funded_portfolio,
                transaction_type='SELL',
                stock=stock,
                quantity=10
            )
            t.save()
        
    def test_transaction_rollback_on_failure(self, funded_portfolio, stock):
        initial_cash = funded_portfolio.cash_balance
        try:
            with transaction.atomic():
                # Valid transaction
                t1 = Transaction.objects.create(
                    portfolio=funded_portfolio,
                    transaction_type='BUY',
                    stock=stock,
                    quantity=50
                )
                t1.save()
                
                # Invalid transaction that should fail
                t2 = Transaction.objects.create(
                    portfolio=funded_portfolio,
                    transaction_type='BUY',
                    stock=stock,
                    quantity=100000  # Impossible quantity
                )
                t2.save()
        except ValidationError:
            pass

        funded_portfolio.refresh_from_db()
        assert funded_portfolio.cash_balance == initial_cash
        assert not funded_portfolio.holdings.exists()