# models/holding.py
from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.core.exceptions import ValidationError
from portfolio.models import Portfolio
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
                    'average_purchase_price': price_per_share
                }
            )

            if not created:
                total_cost = (holding.quantity * holding.average_purchase_price) + (quantity * price_per_share)
                holding.quantity += quantity
                holding.average_purchase_price = total_cost / holding.quantity
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
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name='holdings')
    stock = models.ForeignKey('stocks.Stock', on_delete=models.CASCADE, related_name='holdings')
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)], help_text="Number of shares held")
    average_purchase_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Weighted average price per share"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = HoldingManager()

    @property
    def current_value(self):
        return self.quantity * self.stock.current_price

    @property
    def gain_loss(self):
        return (self.stock.current_price - self.average_purchase_price) * self.quantity
    
    def clean(self):
        if self.quantity < 0:
            raise ValidationError("Quantity cannot be negative")
        if self.average_purchase_price <= 0:
            raise ValidationError("Purchase price must be positive")

    class Meta:
        unique_together = ('portfolio', 'stock')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.portfolio.user}: {self.quantity} shares of {self.stock.symbol}"