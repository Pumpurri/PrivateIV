from django.db import models
from decimal import Decimal


class FXRate(models.Model):
    class RateType(models.TextChoices):
        COMPRA = 'compra', 'compra'
        VENTA = 'venta', 'venta'
        MID = 'mid', 'mid'

    class Session(models.TextChoices):
        INTRADAY = 'intraday', 'intraday'
        CIERRE = 'cierre', 'cierre'
    """Daily FX rate for converting from a quote currency into a base currency.

    Example: base_currency='PEN', quote_currency='USD', rate=3.82  means 1 USD = 3.82 PEN
    """
    date = models.DateField()
    base_currency = models.CharField(max_length=3, help_text='ISO 4217 base currency code (e.g., PEN)')
    quote_currency = models.CharField(max_length=3, help_text='ISO 4217 quote currency code (e.g., USD)')
    rate = models.DecimalField(max_digits=16, decimal_places=6, help_text='How many base currency units per 1 quote currency unit')
    rate_type = models.CharField(max_length=10, choices=RateType.choices, default=RateType.COMPRA)
    session = models.CharField(max_length=10, choices=Session.choices, default=Session.CIERRE)
    # Metadata for auditability
    provider = models.CharField(max_length=50, blank=True, default='', help_text='Data provider name (e.g., BCRP)')
    source_series = models.CharField(max_length=20, blank=True, default='', help_text='Provider series code (e.g., PD04645PD)')
    fetched_at = models.DateTimeField(null=True, blank=True, help_text='When this rate was fetched from provider')
    notes = models.CharField(max_length=200, blank=True, default='', help_text='Optional notes')

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['date', 'base_currency', 'quote_currency', 'rate_type', 'session'],
                name='uniq_fxrate_date_pair'
            ),
        ]
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['base_currency', 'quote_currency']),
            models.Index(fields=['rate_type', 'session']),
        ]
        ordering = ['-date', 'base_currency', 'quote_currency']

    def __str__(self):
        return f"{self.date} {self.quote_currency}->{self.base_currency} {self.rate}"
