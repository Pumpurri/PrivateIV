from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal
from stocks.models import Stock

class Portfolio(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    cash = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('10000.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    @property
    def total_value(self):
        return self.cash + sum(
            holding.quantity * holding.stock.current_price 
            for holding in self.holdings.all()
        )

class Holding(models.Model):
    portfolio = models.ForeignKey(
        Portfolio,
        related_name='holdings',
        on_delete=models.CASCADE
    )
    stock = models.ForeignKey(
        Stock,
        related_name='holdings',
        on_delete=models.CASCADE
    )
    quantity = models.PositiveIntegerField(default=0)