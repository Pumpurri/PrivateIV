# models/transaction.py
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from decimal import Decimal

class Transaction(models.Model):
    class TransactionType(models.TextChoices):
        BUY = 'BUY', 'Buy Order'
        SELL = 'SELL', 'Sell Order'
        DEPOSIT = 'DEPOSIT', 'Cash Deposit'

    portfolio = models.ForeignKey(
        'Portfolio',
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    transaction_type = models.CharField(max_length=10, choices=TransactionType.choices)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        null=True,
        blank=True
    )
    stock = models.ForeignKey(
        'stocks.Stock',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        null=True,
        blank=True
    )
    executed_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        editable=False
    )
    timestamp = models.DateTimeField(auto_now_add=True, editable=False)
    error_message = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['portfolio', 'timestamp']),
            models.Index(fields=['transaction_type']),
        ]

    def clean(self):
        if self.pk:
            original = Transaction.objects.get(pk=self.pk)
            if original.transaction_type != self.transaction_type:
                raise ValidationError("Transaction type cannot be changed after creation")
        self._validate_transaction_logic()
        self._validate_amount_positive()
    
    def _validate_transaction_logic(self):
        trade_types = [self.TransactionType.BUY, self.TransactionType.SELL]
        if self.transaction_type in trade_types:
            self._validate_trade_transaction()
        else:
            self._validate_non_trade_transaction()

    def _validate_trade_transaction(self):
        errors = {}
        if not self.stock:
            raise ValidationError({'stock': 'Stock required for trade transactions'})
        if not self.quantity:
            raise ValidationError({'quantity': 'Quantity required for trade transactions'})
        if self.executed_price is None and self.amount is not None:
            errors['amount'] = 'Amount should be calculated automatically for trades'
        
        if errors:
            raise ValidationError(errors)

    def _validate_non_trade_transaction(self):
        if self.stock is not None:
            raise ValidationError({'stock': 'Stock must be null for non-trade transactions'})
        if self.quantity is not None:
            raise ValidationError({'quantity': 'Quantity must be null for non-trade transactions'})
        if self.amount is None:
            raise ValidationError({'amount': 'Amount required for non-trade transactions'})
    
    def _validate_amount_positive(self):
        if self.amount is not None and self.amount <= Decimal('0'):
            raise ValidationError({'amount': 'Amount must be positive'})

    def save(self, *args, **kwargs):
        self.full_clean()
        is_new = self.pk is None
        with transaction.atomic():
            super().save(*args, **kwargs)
            if is_new:
                from portfolio.services.transaction_services import TransactionService
                TransactionService.execute_transaction(self)

    def __str__(self):
        return f"{self.transaction_type} - {self.amount or '0.00'}$"