from rest_framework import serializers
from .models import Stock, StockRefreshStatus
from decimal import Decimal, ROUND_HALF_UP

class StockSerializer(serializers.ModelSerializer):
    current_price = serializers.SerializerMethodField()
    price_change = serializers.SerializerMethodField()
    price_change_percent = serializers.SerializerMethodField()

    class Meta:
        model = Stock
        fields = '__all__'
        read_only_fields = ('last_updated', 'company_code', 'is_local')

    def get_current_price(self, obj):
        """Return price in portfolio base currency using mid FX rate"""
        from portfolio.services.fx_service import get_fx_rate
        from django.utils import timezone
        from django.utils.timezone import localtime
        from datetime import time

        price = obj.current_price
        if price is None:
            return Decimal('0.00')

        # Get portfolio context from parent serializer if available
        parent = self.parent
        portfolio = None

        # Try to get portfolio from the holding context
        if hasattr(parent, 'instance') and parent.instance:
            if hasattr(parent.instance, 'portfolio'):
                portfolio = parent.instance.portfolio
            elif hasattr(parent.instance, '__iter__'):
                # Handle queryset case
                try:
                    first_item = next(iter(parent.instance), None)
                    if first_item and hasattr(first_item, 'portfolio'):
                        portfolio = first_item.portfolio
                except:
                    pass

        # If no portfolio context, return native price
        if not portfolio or not obj.currency or obj.currency == portfolio.base_currency:
            return price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Determine session for FX rate
        try:
            now_t = localtime().time()
        except Exception:
            now_t = timezone.now().time()
        cmp_t = now_t.replace(tzinfo=None) if getattr(now_t, 'tzinfo', None) else now_t
        session = 'intraday' if (cmp_t >= time(11, 5) and cmp_t < time(13, 30)) else 'cierre'

        # Use mid rate (average of compra/venta) for display
        fx = get_fx_rate(
            timezone.now().date(),
            portfolio.base_currency,
            obj.currency,
            rate_type='mid',
            session=session
        )
        price_converted = (price * fx).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return price_converted

    def get_price_change(self, obj):
        """Return price change in portfolio base currency using mid FX rate"""
        from portfolio.services.fx_service import get_fx_rate
        from django.utils import timezone
        from django.utils.timezone import localtime
        from datetime import time

        change = obj.price_change
        if change is None:
            return None

        # Get portfolio context from parent serializer if available
        parent = self.parent
        portfolio = None

        # Try to get portfolio from the holding context
        if hasattr(parent, 'instance') and parent.instance:
            if hasattr(parent.instance, 'portfolio'):
                portfolio = parent.instance.portfolio
            elif hasattr(parent.instance, '__iter__'):
                try:
                    first_item = next(iter(parent.instance), None)
                    if first_item and hasattr(first_item, 'portfolio'):
                        portfolio = first_item.portfolio
                except:
                    pass

        # If no portfolio context or same currency, return native change
        if not portfolio or not obj.currency or obj.currency == portfolio.base_currency:
            return change.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Determine session for FX rate
        try:
            now_t = localtime().time()
        except Exception:
            now_t = timezone.now().time()
        cmp_t = now_t.replace(tzinfo=None) if getattr(now_t, 'tzinfo', None) else now_t
        session = 'intraday' if (cmp_t >= time(11, 5) and cmp_t < time(13, 30)) else 'cierre'

        # Use mid rate (average of compra/venta) for display
        fx = get_fx_rate(
            timezone.now().date(),
            portfolio.base_currency,
            obj.currency,
            rate_type='mid',
            session=session
        )
        change_converted = (change * fx).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return change_converted

    def get_price_change_percent(self, obj):
        """Return price change percentage (no conversion needed)"""
        pct = obj.price_change_percent
        if pct is not None:
            return pct.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return None

    def validate_current_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Price cannot be negative")
        if not isinstance(value, Decimal):
            value = Decimal(str(value))
        return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class StockRefreshStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockRefreshStatus
        fields = ('last_refreshed_at',)
