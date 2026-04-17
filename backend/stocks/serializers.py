from rest_framework import serializers
from .models import Stock, StockRefreshStatus
from decimal import Decimal, ROUND_HALF_UP

from portfolio.services.currency_service import DISPLAY_CURRENCY_NATIVE, normalize_currency
from portfolio.services.position_metrics_service import get_quote_metrics

class StockSerializer(serializers.ModelSerializer):
    display_price = serializers.SerializerMethodField()
    price_change = serializers.SerializerMethodField()
    price_change_percent = serializers.SerializerMethodField()
    display_currency = serializers.SerializerMethodField()

    class Meta:
        model = Stock
        fields = '__all__'
        read_only_fields = ('last_updated', 'company_code', 'is_local')

    def _get_portfolio(self):
        parent = self.parent
        if hasattr(parent, 'instance') and parent.instance:
            if hasattr(parent.instance, 'portfolio'):
                return parent.instance.portfolio
            if hasattr(parent.instance, '__iter__'):
                try:
                    first_item = next(iter(parent.instance), None)
                    if first_item and hasattr(first_item, 'portfolio'):
                        return first_item.portfolio
                except Exception:
                    pass
        return self.context.get('portfolio')

    def get_display_price(self, obj):
        price = obj.current_price
        if price is None:
            return Decimal('0.00')

        portfolio = self._get_portfolio()
        if not portfolio:
            return Decimal(price).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        display_currency = self._resolve_display_currency(obj, portfolio)
        return get_quote_metrics(obj, display_currency or portfolio.reporting_currency)['display_price']

    def get_price_change(self, obj):
        change = obj.price_change
        if change is None:
            return None

        portfolio = self._get_portfolio()
        if not portfolio:
            return Decimal(change).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        display_currency = self._resolve_display_currency(obj, portfolio)
        return get_quote_metrics(obj, display_currency or portfolio.reporting_currency)['price_change']

    def get_price_change_percent(self, obj):
        portfolio = self._get_portfolio()
        if portfolio:
            display_currency = self._resolve_display_currency(obj, portfolio)
            pct = get_quote_metrics(obj, display_currency or portfolio.reporting_currency)['price_change_percent']
            if pct is not None:
                return pct

        pct = obj.price_change_percent
        if pct is not None:
            return pct.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return None

    def get_display_currency(self, obj):
        portfolio = self._get_portfolio()
        if not portfolio:
            return obj.currency or 'PEN'
        display_currency = self._resolve_display_currency(obj, portfolio)
        return get_quote_metrics(obj, display_currency or portfolio.reporting_currency)['display_currency']

    def _resolve_display_currency(self, obj, portfolio):
        raw_display_currency = self.context.get('display_currency')
        if raw_display_currency in (None, ''):
            return None
        normalized = normalize_currency(raw_display_currency, allow_native=True)
        if normalized == DISPLAY_CURRENCY_NATIVE:
            return (obj.currency or portfolio.reporting_currency or 'PEN').upper()
        return normalized

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
