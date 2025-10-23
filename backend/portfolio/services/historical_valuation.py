import decimal
import logging
from decimal import Decimal
from django.db import models, transaction
from django.db.models import (
    Case, When, F, Value, DurationField, IntegerField, Sum, Avg, ExpressionWrapper
)
from portfolio.models.historical_price import HistoricalStockPrice
from portfolio.services.snapshot_service import SnapshotService
from portfolio.services.fx_service import get_fx_rate
from stocks.models import Stock
from portfolio.models.transaction import Transaction


class HistoricalValuationService:
    @classmethod
    def get_historical_value(cls, portfolio, date):
        """
        Calculate portfolio value as of specific date using ONLY historical data
        """
        holdings = SnapshotService._get_historical_holdings(portfolio, date)
        total_value = Decimal('0')
        
        stock_dates = [{'stock_id': sid, 'date': date} for sid in holdings.keys()]
        price_map = HistoricalStockPrice.bulk_cache_prices(stock_dates)
        
        for stock_id, holding in holdings.items():
            price = price_map.get((stock_id, date))
            if price is None:
                price = cls._get_fallback_price(stock_id, date, portfolio)
            # Convert native price to portfolio base currency
            try:
                stock = Stock.objects.get(pk=stock_id)
                native_value = price * holding['quantity']
                # Historical valuations prefer cierre (EOD) mid (estimate)
                rate = get_fx_rate(date, portfolio.base_currency, stock.currency, rate_type='mid', session='cierre')
                base_value = native_value * rate
            except Exception:
                base_value = price * holding['quantity']
            total_value += base_value
            
        # Cash assumed in base currency
        return (total_value + SnapshotService._get_historical_cash(portfolio, date)).quantize(Decimal('0.01'))

    @classmethod
    def _get_fallback_price(cls, stock_id, date, portfolio):
        """Enterprise-grade historical price fallback resolution with cascading tiers"""
        from portfolio.models import HistoricalStockPrice, Transaction
        logger = logging.getLogger(__name__)
        decimal_context = decimal.getcontext()
        decimal_context.rounding = decimal.ROUND_HALF_UP

        try:
            stock = Stock.objects.get(pk=stock_id)
        except Stock.DoesNotExist:
            logger.error(f"Stock {stock_id} not found")
            return Decimal('0.00').quantize(Decimal('0.01'))

        # Tier 1: Nearest historical price (before preferred)
        nearest_price = HistoricalStockPrice.objects.filter(
            stock=stock
        ).annotate(
            date_diff=Case(
                When(date__lte=date, then=date - F('date')),
                When(date__gt=date, then=F('date') - date),
                output_field=DurationField()
            ),
            date_priority=Case(
                When(date__lte=date, then=Value(1)),
                default=Value(2),
                output_field=IntegerField()
            )
        ).order_by('date_priority', 'date_diff').values_list('price', flat=True).first()

        if nearest_price:
            logger.warning(f"Using nearest historical price for {stock.symbol} on {date}")
            return nearest_price.quantize(Decimal('0.01'))

        # Tier 2: Portfolio-specific FIFO acquisition cost
        try:
            historical_holdings = SnapshotService._get_historical_holdings(portfolio, date)
            if stock_id in historical_holdings:
                holding = historical_holdings[stock_id]
                logger.warning(
                    f"Using portfolio's FIFO average price for {stock.symbol} on {date}: "
                    f"{holding['average_price']}"
                )
                return holding['average_price'].quantize(Decimal('0.01'))
        except Exception as e:
            logger.error(f"Failed to get historical holdings: {str(e)}")

        # Tier 3: Global volume-weighted average price (VWAP)
        vwap = Transaction.objects.filter(
            stock=stock,
            transaction_type=Transaction.TransactionType.BUY,
            timestamp__date__lte=date
        ).exclude(executed_price=None).aggregate(
            vwap=ExpressionWrapper(
                Sum(F('executed_price') * F('quantity')) / Sum(F('quantity')),
                output_field=models.DecimalField()
            )
        )['vwap']

        if vwap:
            logger.warning(f"Using global VWAP for {stock.symbol} on {date}")
            return vwap.quantize(Decimal('0.01'))

        # Tier 4: Volatility-adjusted moving average
        try:
            ma_window = 30
            moving_avg = HistoricalStockPrice.objects.filter(
                stock=stock,
                date__lt=date
            ).order_by('-date')[:ma_window].aggregate(
                avg_price=Avg('price')
            )['avg_price']
            
            if moving_avg:
                logger.warning(f"Using {ma_window}-day moving average for {stock.symbol} on {date}")
                return moving_avg.quantize(Decimal('0.01'))
        except Exception as e:
            logger.error(f"MA calculation failed: {str(e)}")

        # Final fallback with circuit breaker
        logger.critical(f"Price resolution failed for {stock.symbol} on {date}")
        raise ValueError(f"Could not determine historical price for {stock.symbol} on {date}")
