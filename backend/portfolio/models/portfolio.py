from django.db import models
from django.db.models import Sum, F
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal, ROUND_HALF_UP

class Portfolio(models.Model):
    user = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.CASCADE,
        related_name='portfolios'
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Initial portfolio created automatically for new users"
    )
    cash_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'is_default'],
                condition=models.Q(is_default=True),
                name='unique_default_portfolio'
            )
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email}'s Portfolio"


    @property
    def total_value(self):
        return self.cash_balance + self.investment_value

    @property
    def investment_value(self):
        return self.holdings.annotate(
            value=F('quantity') * F('stock__current_price')
        ).aggregate(total=Sum('value'))['total'] or Decimal('0.00')
    
    def adjust_cash(self, amount):
        """Centralized method for cash adjustments"""
        new_balance = self.cash_balance + Decimal(amount)
        if new_balance < Decimal('0.00'):
            raise ValidationError("Insufficient funds")
        self.cash_balance = new_balance.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.save(update_fields=['cash_balance'])

    def clean(self):
        if self.cash_balance < Decimal('0'):
            raise ValidationError("Cash balance cannot be negative.")


    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)