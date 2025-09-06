# models/transaction.py
from django.db import models, transaction
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid

class TransactionManager(models.Manager):
    """Armored manager that prevents direct transaction creation"""
    def get_queryset(self):
        return super().get_queryset().filter(portfolio__is_deleted=False)
    
    def create(self, **kwargs):
        raise PermissionDenied(
            "Transaction objects must be created through TransactionService"
        )
    
    def bulk_create(self, objs, **kwargs):
        raise PermissionDenied(
            "Transaction objects must be created through TransactionService"
        )

class Transaction(models.Model):
    objects = TransactionManager()
    all_objects = models.Manager()

    class TransactionType(models.TextChoices):
        BUY = 'BUY', 'Buy Order'
        SELL = 'SELL', 'Sell Order'
        DEPOSIT = 'DEPOSIT', 'Cash Deposit'
        WITHDRAWAL = 'WITHDRAWAL', 'Cash Withdrawal'

    portfolio = models.ForeignKey(
        'portfolio.Portfolio',
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    idempotency_key = models.UUIDField(
        default=uuid.uuid4,
        help_text="Unique identifier for preventing duplicate processing",
        editable=False,
        db_index=True
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
    error_message = models.CharField(max_length=255, blank=True, null=True, default='')

    class Meta:
        ordering = ['-timestamp']
        unique_together = ('portfolio', 'idempotency_key')
        indexes = [
            models.Index(fields=['timestamp'], name='transaction_timestamp_idx'),
            models.Index(fields=['portfolio', 'idempotency_key'], name='portfolio_idempotency_idx'),
            models.Index(fields=['portfolio', 'timestamp'], name='portfolio_timestamp_idx'),
            models.Index(fields=['transaction_type', 'timestamp'], name='type_timestamp_idx'),
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
        if not self.stock.is_active:
            raise ValidationError({'stock': 'Cannot trade inactive securities'})
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
        """Nuclear validation for transaction persistence"""
        if not getattr(self, '_created_by_service', False) and not self.pk:
            raise PermissionDenied(
                "Transactions must be created via TransactionService"
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.transaction_type} - {self.amount or '0.00'}$"