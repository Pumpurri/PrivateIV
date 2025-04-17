from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal

class DailyPortfolioSnapshot(models.Model):
    portfolio = models.ForeignKey(
        'Portfolio',
        on_delete=models.CASCADE,
        related_name='daily_snapshots'
    )
    date = models.DateField()
    total_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    cash_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    investment_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    total_deposits = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    class Meta:
        unique_together = ('portfolio', 'date')
        ordering = ['-date']
        indexes = [
            models.Index(fields=['portfolio', 'date']),
        ]

    def __str__(self):
        return f"{self.portfolio} Snapshot ({self.date})"