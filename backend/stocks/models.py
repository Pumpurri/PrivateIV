from django.db import models
from decimal import Decimal

class Stock(models.Model):
    symbol = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    current_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    is_active = models.BooleanField(default=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.symbol} ({self.name})"

    def save(self, *args, **kwargs):
        self.symbol = self.symbol.strip().upper()
        if self.current_price is not None:
            if isinstance(self.current_price, (int, float)):
                self.current_price = Decimal(str(self.current_price))
            self.current_price = self.current_price.quantize(Decimal('0.01'))
        super().save(*args, **kwargs)