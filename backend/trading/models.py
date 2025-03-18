from django.db import models
from stocks.models import Stock
from portfolio.models import Portfolio


class Transaction(models.Model):
    BUY = 'BUY'
    SELL = 'SELL'
    TYPE_CHOICES = [
        (BUY, 'Buy'),
        (SELL, 'Sell')
    ]

    portfolio = models.ForeignKey(
        Portfolio,
        related_name='transactions',
        on_delete=models.CASCADE
    )
    stock = models.ForeignKey(
        Stock,
        related_name='transactions',
        on_delete=models.CASCADE
    )
    type = models.CharField(max_length=4, choices=TYPE_CHOICES)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    timestamp = models.DateTimeField(auto_now_add=True)