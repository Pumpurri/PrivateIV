from django.db import models
from django.core.cache import cache
from decimal import Decimal
from django.utils.translation import gettext_lazy as _
from decimal import Decimal, ROUND_HALF_UP
from portfolio.services.snapshot_service import SnapshotService

class HistoricalStockPrice(models.Model):
    stock = models.ForeignKey(
        'stocks.Stock',
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

    @classmethod
    def get_price(cls, stock, date):
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
    

