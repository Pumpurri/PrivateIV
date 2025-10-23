from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal, ROUND_HALF_UP
from django.core.exceptions import ValidationError
from django.db import transaction

class HoldingManager(models.Manager):
    def process_purchase(self, portfolio, stock, quantity, price_per_share):
        """Handle buy transactions"""
        with transaction.atomic():
            holding, created = self.select_for_update().get_or_create(
                portfolio=portfolio,
                stock=stock,
                defaults={
                    'quantity': quantity,
                    'average_purchase_price': price_per_share,
                    'is_active': True
                }
            )

            if not created:
                total_cost = (holding.quantity * holding.average_purchase_price) + (quantity * price_per_share)
                holding.quantity += quantity
                holding.average_purchase_price = (total_cost / holding.quantity).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP
                )
                holding.is_active = True
                holding.save()

            return holding
    
    def process_sale(self, portfolio, stock, quantity):
        """Handle sell transactions"""
        with transaction.atomic():
            try:
                holding = self.select_for_update().get(portfolio=portfolio, stock=stock)
            except self.model.DoesNotExist:
                raise ValidationError("Cannot sell stock not held in portfolio.")
            if holding.quantity < quantity:
                raise ValidationError("Insufficient shares to sell")

            holding.quantity -= quantity
            if holding.quantity == 0:
                holding.delete()
            else:
                holding.save()

            return holding

class Holding(models.Model):
    portfolio = models.ForeignKey('portfolio.Portfolio', on_delete=models.CASCADE, related_name='holdings')
    stock = models.ForeignKey('stocks.Stock', on_delete=models.CASCADE, related_name='holdings')
    quantity = models.PositiveIntegerField(help_text="Number of shares held")
    average_purchase_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Weighted average price per share"
    )
    is_active = models.BooleanField(default=True, help_text="False if position fully sold")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = HoldingManager()

    @property
    def current_value(self):
        """Current value in portfolio base currency"""
        from portfolio.services.fx_service import get_fx_rate
        from django.utils import timezone
        from django.utils.timezone import localtime
        from datetime import time

        price = self.stock.current_price
        if price is None:
            price = Decimal('0.00')

        native_value = Decimal(self.quantity) * price

        # Convert to portfolio base currency if needed
        if self.stock.currency and self.stock.currency != self.portfolio.base_currency:
            # Determine session for FX rate
            try:
                now_t = localtime().time()
            except Exception:
                now_t = timezone.now().time()
            cmp_t = now_t.replace(tzinfo=None) if getattr(now_t, 'tzinfo', None) else now_t
            session = 'intraday' if (cmp_t >= time(11,5) and cmp_t < time(13,30)) else 'cierre'

            # Use mid rate (average of compra/venta) for current valuation
            fx = get_fx_rate(timezone.now().date(), self.portfolio.base_currency, self.stock.currency, rate_type='mid', session=session)
            return (native_value * fx).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        return native_value

    @property
    def gain_loss(self):
        """Gain/loss in portfolio base currency"""
        from portfolio.services.fx_service import get_fx_rate
        from django.utils import timezone
        from django.utils.timezone import localtime
        from datetime import time

        price = self.stock.current_price
        if price is None:
            price = Decimal('0.00')

        # Convert current price to portfolio base currency if needed
        if self.stock.currency and self.stock.currency != self.portfolio.base_currency:
            try:
                now_t = localtime().time()
            except Exception:
                now_t = timezone.now().time()
            cmp_t = now_t.replace(tzinfo=None) if getattr(now_t, 'tzinfo', None) else now_t
            session = 'intraday' if (cmp_t >= time(11,5) and cmp_t < time(13,30)) else 'cierre'

            fx = get_fx_rate(timezone.now().date(), self.portfolio.base_currency, self.stock.currency, rate_type='mid', session=session)
            price_base = (price * fx).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        else:
            price_base = price

        # average_purchase_price is already in base currency (PEN)
        return (price_base - self.average_purchase_price) * Decimal(self.quantity)

    class Meta:
        unique_together = ('portfolio', 'stock')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['stock'], name='holding_stock_idx'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(quantity__gt=0) | models.Q(is_active=False),
                name="active_holding_positive_quantity"
            ),
            models.CheckConstraint(check=models.Q(average_purchase_price__gt=0), name="holding_price_positive"),
        ]

    def __str__(self):
        return f"{self.portfolio.user}: {self.quantity} shares of {self.stock.symbol}"
    
    def clean(self):
        if self.quantity < 0:
            raise ValidationError("Quantity cannot be negative")
        if self.average_purchase_price <= 0:
            raise ValidationError("Purchase price must be positive")
