from django.db import models

class Stock(models.Model):
    symbol = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    current_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=100.00  
    )
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.symbol} ({self.name})"
