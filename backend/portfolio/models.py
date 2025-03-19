# portfolios/models.py (partial)
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal

class PortfolioManager(models.Manager):
    def create_portfolio(self, user, name, initial_deposit=Decimal('0.00')):
        if initial_deposit < Decimal('0.00'):
            raise ValidationError("Initial deposit cannot be negative")
            
        return self.create(
            user=user,
            name=name,
            initial_deposit=initial_deposit,
            cash_balance=initial_deposit,
            total_value=initial_deposit,
            total_contributions=initial_deposit
        )

class Portfolio(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='portfolios'
    )
    name = models.CharField(max_length=50, db_index=True)
    created_date = models.DateTimeField(default=timezone.now, editable=False)
    initial_deposit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    total_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    cash_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    total_contributions = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )

    objects = PortfolioManager()

    class Meta:
        unique_together = ('user', 'name')
        ordering = ['-created_date']

    def __str__(self):
        return f"{self.user.email}'s {self.name} Portfolio"

# portfolios/models.py (partial)
class HoldingManager(models.Manager):
    def get_holding(self, portfolio, symbol):
        return self.get_queryset().get(
            portfolio=portfolio,
            symbol=symbol.upper()
        )

class Holding(models.Model):
    portfolio = models.ForeignKey(
        Portfolio,
        related_name='holdings',
        on_delete=models.CASCADE
    )
    symbol = models.CharField(max_length=10, db_index=True)
    quantity = models.PositiveIntegerField(default=0)
    average_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    objects = HoldingManager()

    class Meta:
        unique_together = ('portfolio', 'symbol')
        ordering = ['symbol']

    @property
    def current_price(self):
        from .services import get_current_price
        return get_current_price(self.symbol)

    @property
    def market_value(self):
        return Decimal(self.quantity) * self.current_price

    @property
    def unrealized_gain(self):
        return (self.current_price - self.average_cost) * self.quantity

    def update_average_cost(self, new_quantity, new_price):
        total_cost = (self.quantity * self.average_cost) + (new_quantity * new_price)
        total_shares = self.quantity + new_quantity
        self.average_cost = total_cost / total_shares
        self.save()


class Contribution(models.Model):
    portfolio = models.ForeignKey(
        Portfolio,
        related_name='contributions',
        on_delete=models.CASCADE
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    date = models.DateTimeField(default=timezone.now, db_index=True)

    objects = ContributionManager()

    class Meta:
        ordering = ['-date']