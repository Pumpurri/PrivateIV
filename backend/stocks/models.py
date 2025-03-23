from django.db import models

class Stock(models.Model):
    symbol = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    current_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.symbol} ({self.name})"

    def save(self, *args, **kwargs):
        self.symbol = self.symbol.strip().upper()
        self.current_price = round(self.current_price, 2)
        super().save(*args, **kwargs)