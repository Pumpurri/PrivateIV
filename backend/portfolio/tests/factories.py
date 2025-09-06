# tests/factories.py
import factory
from factory import Faker, SubFactory
from factory.django import DjangoModelFactory
from portfolio.models import Portfolio, Holding, Transaction
from portfolio.services.transaction_service import TransactionService
from decimal import Decimal
import uuid

class PortfolioFactory(DjangoModelFactory):
    class Meta:
        model = Portfolio
        skip_postgeneration_save = True

    user = factory.SubFactory('users.tests.factories.UserFactory')
    is_default = False
    cash_balance = Decimal('0.00')

    class Params:
        default = factory.Trait(
            is_default=True,
        )
        funded = factory.Trait(
            cash_balance=Decimal('10000.00')
        )
        
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        cash_balance = kwargs.pop('cash_balance', Decimal('0.00'))
        portfolio = super()._create(model_class, *args, **kwargs)
        
        if cash_balance != Decimal('0.00'):
            # Create deposit transaction through service
            TransactionService.execute_transaction({
                'portfolio': portfolio,
                'transaction_type': Transaction.TransactionType.DEPOSIT,
                'amount': cash_balance,
                'idempotency_key': str(uuid.uuid4())
            })
        return portfolio

class HoldingFactory(DjangoModelFactory):
    class Meta:
        model = Holding

    portfolio = factory.SubFactory(PortfolioFactory)
    stock = SubFactory('stocks.tests.factories.StockFactory')
    quantity = Faker('pyint', min_value=1, max_value=1000)
    average_purchase_price = Faker('pydecimal', left_digits=4, right_digits=2, positive=True)

class TransactionFactory(DjangoModelFactory):
    class Meta:
        model = Transaction

    portfolio = SubFactory(PortfolioFactory, funded=True)
    transaction_type = 'DEPOSIT'
    stock = None
    amount = factory.Faker('pydecimal', right_digits=2, min_value=10, max_value=1000)

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        # Extract data needed for service call
        portfolio = kwargs.get('portfolio')
        transaction_type = kwargs.get('transaction_type', 'DEPOSIT')
        stock = kwargs.get('stock')
        quantity = kwargs.get('quantity')
        amount = kwargs.get('amount')
        
        # Build transaction data for service
        transaction_data = {
            'portfolio': portfolio,
            'transaction_type': transaction_type,
            'idempotency_key': str(uuid.uuid4())
        }
        
        if stock:
            transaction_data['stock'] = stock
        if quantity:
            transaction_data['quantity'] = quantity
        if amount and transaction_type in ['DEPOSIT', 'WITHDRAWAL']:
            transaction_data['amount'] = amount
            
        # Create through service
        return TransactionService.execute_transaction(transaction_data)

    class Params:
        buy = factory.Trait(
            transaction_type='BUY',
            stock=factory.SubFactory(
                'stocks.tests.factories.StockFactory',
                current_price=factory.Faker('pydecimal', right_digits=2, min_value=10, max_value=50)
            ),
            quantity=factory.Faker('pyint', min_value=1, max_value=200),
            amount=None  # Will be calculated by service
        )
        sell = factory.Trait(
            transaction_type='SELL',
            stock=factory.SubFactory(
                'stocks.tests.factories.StockFactory', 
                current_price=factory.Faker('pydecimal', right_digits=2, min_value=10, max_value=50)
            ),
            quantity=factory.Faker('pyint', min_value=1, max_value=200),
            amount=None  # Will be calculated by service
        )
        deposit = factory.Trait(
            transaction_type='DEPOSIT',
            stock=None,
            quantity=None,
            amount=factory.Faker('pydecimal', right_digits=2, min_value=10, max_value=1000)
        )