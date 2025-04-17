from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal

class PortfolioPerformance(models.Model):
    portfolio = models.OneToOneField(
        'Portfolio',
        on_delete=models.CASCADE,
        related_name='performance'
    )
    time_weighted_return = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal('0.0000'),
        help_text="Annualized time-weighted return"
    )
    total_deposits = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Portfolio Performances"

    def __str__(self):
        return f"{self.portfolio} Performance"