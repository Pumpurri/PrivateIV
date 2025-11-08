from django.db import models
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache

class Stock(models.Model):
    symbol = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    company_code = models.CharField(
        max_length=20,
        blank=True,
        default='',
        help_text='Identifier provided by the exchange (e.g., BVL company code)'
    )
    is_local = models.BooleanField(
        default=False,
        help_text='True when the instrument corresponds to a local BVL listing'
    )
    currency = models.CharField(
        max_length=3,
        default='USD',
        help_text='ISO 4217 currency code of the stock pricing (e.g., USD, PEN)'
    )
    current_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    previous_close = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Previous day closing price for calculating daily changes'
    )
    is_active = models.BooleanField(default=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.symbol} ({self.name})"

    def save(self, *args, **kwargs):
        self.symbol = self.symbol.strip().upper()
        if self.current_price is not None:
            if isinstance(self.current_price, (int, float)):
                self.current_price = Decimal(str(self.current_price))
            self.current_price = self.current_price.quantize(Decimal('0.01'))
        if self.previous_close is not None:
            if isinstance(self.previous_close, (int, float)):
                self.previous_close = Decimal(str(self.previous_close))
            self.previous_close = self.previous_close.quantize(Decimal('0.01'))
        super().save(*args, **kwargs)

    def get_previous_close(self):
        """Get previous close from HistoricalStockPrice if not set"""
        if self.previous_close:
            return self.previous_close

        # Try to get from historical data (yesterday's price)
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)

        # Try up to 7 days back to find last trading day
        for i in range(1, 8):
            check_date = today - timedelta(days=i)
            hist_price = HistoricalStockPrice.get_price(self, check_date)
            if hist_price:
                return hist_price

        return None

    @property
    def price_change(self):
        """Price change from previous close"""
        if not self.current_price:
            return None

        prev_close = self.get_previous_close()
        if prev_close:
            return self.current_price - prev_close
        return None

    @property
    def price_change_percent(self):
        """Price change percentage from previous close"""
        if not self.current_price:
            return None

        prev_close = self.get_previous_close()
        if prev_close and prev_close != 0:
            return ((self.current_price - prev_close) / prev_close) * 100
        return None


class StockRefreshStatus(models.Model):
    """
    Tracks the most recent time stock prices were refreshed.
    Stores a single row keyed by singleton_id.
    """
    singleton_id = models.PositiveSmallIntegerField(default=1, unique=True, editable=False)
    last_refreshed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Stock refresh status"
        verbose_name_plural = "Stock refresh status"

    def save(self, *args, **kwargs):
        self.singleton_id = 1
        super().save(*args, **kwargs)

    @classmethod
    def mark_refreshed(cls, ts=None):
        """
        Update the singleton record with the latest refresh timestamp.
        """
        ts = ts or timezone.now()
        obj, created = cls.objects.get_or_create(singleton_id=1, defaults={'last_refreshed_at': ts})
        if not created:
            cls.objects.filter(pk=obj.pk).update(last_refreshed_at=ts)
            obj.refresh_from_db()
        return obj


class HistoricalStockPrice(models.Model):
    """
    Stores end-of-day historical prices for stocks.
    Used for portfolio valuation, performance tracking, and charting.
    """
    stock = models.ForeignKey(
        Stock,
        on_delete=models.CASCADE,
        related_name='price_history'
    )
    date = models.DateField(db_index=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['stock', 'date'], name='unique_stock_date')
        ]
        ordering = ['-date']
        db_table = 'stocks_historicalstockprice'

    def __str__(self):
        return f"{self.stock.symbol} @ {self.date}: ${self.price}"

    @classmethod
    def get_price(cls, stock, date):
        """Get cached price for a stock on a specific date"""
        cache_key = f'stock_price_{stock.id}_{date}'
        cached = cache.get(cache_key)
        if cached is not None:
            return Decimal(cached)

        try:
            price = cls.objects.get(stock=stock, date=date).price
            cache.set(cache_key, str(price), timeout=3600*24)  # Cache for 24h
            return price
        except cls.DoesNotExist:
            return None

    @classmethod
    def bulk_cache_prices(cls, stock_dates):
        """Optimized method for batch price lookups"""
        cache_keys = {}
        dates = {sd['date'] for sd in stock_dates}
        stock_ids = {sd['stock_id'] for sd in stock_dates}

        # Check cache first
        for sd in stock_dates:
            key = f'stock_price_{sd["stock_id"]}_{sd["date"]}'
            cached = cache.get(key)
            if cached is not None:
                cache_keys[(sd["stock_id"], sd["date"])] = Decimal(cached)

        # Find missing prices
        missing = []
        for sd in stock_dates:
            if (sd["stock_id"], sd["date"]) not in cache_keys:
                missing.append((sd["stock_id"], sd["date"]))

        # Batch query for missing prices
        if missing:
            stock_ids = {s[0] for s in missing}
            dates = {s[1] for s in missing}

            prices = cls.objects.filter(
                stock_id__in=stock_ids,
                date__in=dates
            ).values('stock_id', 'date', 'price')

            for p in prices:
                key = (p['stock_id'], p['date'])
                cache_keys[key] = p['price']
                cache.set(f'stock_price_{p["stock_id"]}_{p["date"]}',
                         str(p['price']),
                         timeout=3600*24)

        return cache_keys
