import factory
from factory.django import DjangoModelFactory
from stocks.models import Stock

class StockFactory(DjangoModelFactory):
    class Meta:
        model = Stock
    
    symbol = factory.Sequence(lambda n: f"STK{n:03}")
    name = factory.Faker('company')
    current_price = factory.Faker('pydecimal', right_digits=2, min_value=1, max_value=1000)
    is_active = True