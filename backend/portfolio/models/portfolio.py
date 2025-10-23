from django.db import models, transaction
from django.db.models import Sum, F, Q
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.timezone import localtime
from decimal import Decimal, ROUND_HALF_UP
from portfolio.services.historical_valuation import HistoricalValuationService


class ActivePortfolioManager(models.Manager):
    """Manager to exclude soft-deleted portfolios by default."""
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

class Portfolio(models.Model):
    objects = ActivePortfolioManager()  
    all_objects = models.Manager()

    user = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.CASCADE,
        related_name='portfolios'
    )
    name = models.CharField(
        max_length=100,
        default='My Portfolio',
        help_text='User-defined name for this portfolio'
    )
    description = models.TextField(
        blank=True,
        help_text='Optional description of the portfolio’s purpose or goals'
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Initial portfolio created automatically for new users"
    )
    base_currency = models.CharField(
        max_length=3,
        default='PEN',
        help_text='ISO 4217 currency code used as the base for valuation (e.g., PEN, USD)'
    )
    cash_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'is_default'],
                condition=models.Q(is_default=True),
                name='unique_default_portfolio'
            ),
            models.CheckConstraint(
                check=Q(cash_balance__gte=0),
                name='cash_balance_non_negative'
            )
        ]
        indexes = [
            models.Index(fields=['user', 'is_deleted']),
            models.Index(fields=['is_default'])
        ]
        ordering = ['-created_at']


    def __str__(self):
        return f"{self.user.email}'s Portfolio"

    @property
    def total_value(self):
        return self.cash_balance + self.current_investment_value

    @property
    def current_investment_value(self):
        """Real-time value using CURRENT prices"""
        return self._calculate_investment_value(timezone.now().date())
    
    @property  
    def investment_value(self):
        """Alias for current_investment_value for backward compatibility"""
        return self.current_investment_value
    
    def _calculate_investment_value(self, as_of_date):
        """Internal method for date-aware valuation, converted to base currency."""
        from portfolio.services.fx_service import get_fx_rate
        from datetime import time
        if as_of_date == timezone.now().date():
            # Real-time calculation (convert each holding to base using today's/last-known FX)
            total = Decimal('0.00')
            for h in self.holdings.select_related('stock').filter(is_active=True, stock__is_active=True):
                price = h.stock.current_price or Decimal('0.00')
                native_value = Decimal(h.quantity) * price
                # Choose intraday during 11:05–13:29 local time, otherwise cierre
                try:
                    now_t = localtime().time()
                except Exception:
                    now_t = timezone.now().time()
                # Normalize to naive time for safe comparison
                cmp_t = now_t.replace(tzinfo=None) if getattr(now_t, 'tzinfo', None) else now_t
                session = 'intraday' if (cmp_t >= time(11,5) and cmp_t < time(13,30)) else 'cierre'
                # Use mid for live marking by estimate
                rate = get_fx_rate(as_of_date, self.base_currency, getattr(h.stock, 'currency', 'USD'), rate_type='mid', session=session)
                total += (native_value * rate)
            return total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        else:
            # Historical calculation (uses historical FX internally)
            return HistoricalValuationService.get_historical_value(self, as_of_date)
    
    def adjust_cash(self, amount):
        amount = Decimal(amount)
        with transaction.atomic():
            locked = Portfolio.objects.select_for_update().get(pk=self.pk)
            new_balance = locked.cash_balance + amount
            if new_balance < Decimal('0'):
                raise ValidationError("Insufficient funds")
            locked.cash_balance = new_balance.quantize(
                Decimal('0.01'),
                rounding=ROUND_HALF_UP
            )
            locked.save(update_fields=['cash_balance'])
            self.cash_balance = locked.cash_balance

    def clean(self):
        if self.cash_balance < Decimal('0'):
            raise ValidationError("Cash balance cannot be negative.")

    def delete(self, using=None, keep_parents=False):
        if self.is_deleted:
            return

        if self.is_default:
            with transaction.atomic():
                # Lock all active portfolios for this user during selection
                portfolios = self.user.portfolios.select_for_update().filter(
                    is_deleted=False
                )

                # Verify we're still the default (prevent race condition)
                current_default = portfolios.filter(is_default=True).first()
                if current_default != self:
                    raise ValidationError("Portfolio is no longer the default")

                # Find replacement with lock
                replacement = portfolios.exclude(pk=self.pk).first()
                if not replacement:
                    raise ValidationError(
                        "You must create another portfolio before deleting the default one."
                    )

                # First unset current default to satisfy unique constraint
                self.is_default = False
                self.save(update_fields=['is_default'])

                # Then set replacement as default
                Portfolio.objects.filter(pk=replacement.pk).update(is_default=True)

                # Mark self archived (soft-delete)
                self.is_deleted = True
                self.deleted_at = timezone.now()
                self.save(update_fields=['is_deleted', 'deleted_at'])

                # Deactivate holdings
                self.holdings.update(is_active=False)
        else:
            with transaction.atomic():
                self.is_deleted = True
                self.deleted_at = timezone.now()
                self.save(update_fields=['is_deleted', 'deleted_at'])
                self.holdings.update(is_active=False)
