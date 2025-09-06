from django.db import models, transaction
from django.db.models import Sum, F, Q
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
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
        """Internal method for date-aware valuation"""
        if as_of_date == timezone.now().date():
            # Real-time calculation
            return self.holdings.filter(
                is_active=True,
                stock__is_active=True,
            ).annotate(
                value=F('quantity') * F('stock__current_price')
            ).aggregate(total=Sum('value'))['total'] or Decimal('0.00')
        else:
            # Historical calculation
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

                # Atomic update of replacement portfolio
                Portfolio.objects.filter(pk=replacement.pk).update(is_default=True)
                
                # Refresh instance to verify constraints
                replacement.refresh_from_db()

                # Mark self for deletion
                self.is_deleted = True
                self.deleted_at = timezone.now()
                self.save(update_fields=['is_deleted', 'deleted_at'])
                
                # Cascade to holdings
                self.holdings.update(is_active=False)
        else:
            with transaction.atomic():
                self.is_deleted = True
                self.deleted_at = timezone.now()
                self.save(update_fields=['is_deleted', 'deleted_at'])
                self.holdings.update(is_active=False)

        # Call super to maintain normal deletion behavior for non-default case
        super().delete(using=using, keep_parents=keep_parents)