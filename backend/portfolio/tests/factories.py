# tests/factories.py
import factory
from factory import Faker, SubFactory
from factory.django import DjangoModelFactory
from portfolio.models import Portfolio, Holding, Transaction
from decimal import Decimal

class PortfolioFactory(DjangoModelFactory):
    class Meta:
        model = Portfolio
        skip_postgeneration_save = True

    user = factory.SubFactory('users.tests.factories.UserFactory')
    is_default = False
    cash_balance = Decimal('10000.00')

    class Params:
        default = factory.Trait(
            is_default=True,
            cash_balance=Decimal('10000.00')
        )

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        if kwargs.get('is_default', False):
            return model_class.objects.create(*args, **kwargs)
        return super()._create(model_class, *args, **kwargs)

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

    portfolio = SubFactory(PortfolioFactory)
    transaction_type = 'DEPOSIT'
    stock = None

    class Params:
        buy = factory.Trait(
            transaction_type='BUY',
            stock=factory.SubFactory(
                'stocks.tests.factories.StockFactory',
                current_price=factory.Faker('pydecimal', right_digits=2, min_value=10, max_value=50)
            ),
            quantity=factory.Faker('pyint', min_value=1, max_value=200),
            executed_price=factory.SelfAttribute('stock.current_price'),
            amount=factory.LazyAttribute(
                lambda o: (o.quantity * o.executed_price).quantize(Decimal('0.01'))
            )
        )
        sell = factory.Trait(
            transaction_type='SELL',
            stock=factory.SubFactory(
                'stocks.tests.factories.StockFactory', 
                current_price=factory.Faker('pydecimal', right_digits=2, min_value=10, max_value=50)
            ),
            quantity=factory.Faker('pyint', min_value=1, max_value=200),
            executed_price=factory.SelfAttribute('stock.current_price'),
            amount=factory.LazyAttribute(
                lambda o: (o.quantity * o.executed_price).quantize(Decimal('0.01'))
            )
        )
        deposit = factory.Trait(
            transaction_type='DEPOSIT',
            stock=None,
            quantity=None,
            executed_price=None,
            amount=factory.Faker('pydecimal', right_digits=2, min_value=10, max_value=1000)
        )