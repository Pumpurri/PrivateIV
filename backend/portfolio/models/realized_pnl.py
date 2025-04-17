from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.core.exceptions import ValidationError

class RealizedPNL(models.Model):
    portfolio = models.ForeignKey(
        'Portfolio',
        on_delete=models.CASCADE,
        related_name='realized_pnls'
    )
    transaction = models.OneToOneField(
        'Transaction',
        on_delete=models.CASCADE,
        related_name='realized_pnl'
    )
    stock = models.ForeignKey(
        'stocks.Stock',
        on_delete=models.CASCADE
    )
    quantity = models.PositiveIntegerField()
    purchase_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    sell_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    pnl = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Realized profit/loss (positive for gains)"
    )
    realized_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['portfolio', 'realized_at']),
            models.Index(fields=['stock', 'realized_at']),
        ]
        ordering = ['-realized_at']

    def save(self, *args, **kwargs):
        """Enforce immutability on save"""
        if self.pk:
            self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        """Prevent modifications to existing RealizedPNL records"""
        if self.pk:
            original = RealizedPNL.objects.get(pk=self.pk)
            for field in ['portfolio', 'transaction', 'stock', 'quantity', 
                        'purchase_price', 'sell_price', 'pnl']:
                if getattr(self, field) != getattr(original, field):
                    raise ValidationError("RealizedPNL records are immutable.")

    def __str__(self):
        return f"{self.portfolio} {self.stock} P&L: {self.pnl}"