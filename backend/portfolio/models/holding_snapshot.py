from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal

class HoldingSnapshot(models.Model):
    portfolio = models.ForeignKey(
        'Portfolio',
        on_delete=models.CASCADE,
        related_name='holding_snapshots'
    )
    stock = models.ForeignKey(
        'stocks.Stock',
        on_delete=models.CASCADE
    )
    date = models.DateField(db_index=True)
    quantity = models.PositiveIntegerField()
    average_purchase_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    total_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    class Meta:
        unique_together = ('portfolio', 'stock', 'date')
        ordering = ['-date']
        indexes = [
            models.Index(fields=['date', 'portfolio'], name='holding_date_portfolio_idx'),
            models.Index(fields=['stock', 'date'], name='holding_stock_date_idx')
        ]

    def __str__(self):
        return f"{self.portfolio} - {self.stock} @ {self.date}"