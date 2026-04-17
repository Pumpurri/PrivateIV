from rest_framework import serializers
from portfolio.models import Portfolio, Holding, PortfolioPerformance
from stocks.serializers import StockSerializer
from decimal import Decimal, ROUND_HALF_UP

from portfolio.services.currency_service import convert_amount, get_portfolio_reporting_currency, normalize_currency
from portfolio.services.position_metrics_service import get_holding_metrics


class HoldingSerializer(serializers.ModelSerializer):
    stock = StockSerializer(read_only=True)
    current_value = serializers.SerializerMethodField()
    gain_loss = serializers.SerializerMethodField()
    gain_loss_percentage = serializers.SerializerMethodField()
    cost_basis = serializers.SerializerMethodField()
    day_change = serializers.SerializerMethodField()
    day_change_percentage = serializers.SerializerMethodField()

    class Meta:
        model = Holding
        fields = [
            'id', 'stock', 'quantity', 'average_purchase_price',
            'current_value', 'gain_loss', 'gain_loss_percentage',
            'cost_basis', 'day_change', 'day_change_percentage',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def _get_metrics(self, obj):
        cache = self.context.setdefault('_holding_metrics_cache', {})
        display_currency = (self.context.get('display_currency') or '').upper() or None
        cache_key = (obj.pk, display_currency)
        if cache_key not in cache:
            cache[cache_key] = get_holding_metrics(obj, display_currency=display_currency)
        return cache[cache_key]

    def get_current_value(self, obj):
        return self._get_metrics(obj)['current_value']

    def get_cost_basis(self, obj):
        return self._get_metrics(obj)['cost_basis']

    def get_gain_loss(self, obj):
        return self._get_metrics(obj)['gain_loss']

    def get_gain_loss_percentage(self, obj):
        return self._get_metrics(obj)['gain_loss_percentage']

    def get_day_change(self, obj):
        return self._get_metrics(obj)['day_change']

    def get_day_change_percentage(self, obj):
        return self._get_metrics(obj)['day_change_percentage']


class PortfolioPerformanceSerializer(serializers.ModelSerializer):
    total_return_percentage = serializers.SerializerMethodField()

    class Meta:
        model = PortfolioPerformance
        fields = [
            'total_deposits', 'total_withdrawals', 'time_weighted_return',
            'total_return_percentage', 'last_updated'
        ]
        read_only_fields = ['last_updated']

    def get_total_return_percentage(self, obj):
        if obj.total_deposits and obj.total_deposits > 0:
            pct = (obj.time_weighted_return / obj.total_deposits) * Decimal('100')
            return pct.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return Decimal('0.00')


class PortfolioSerializer(serializers.ModelSerializer):
    total_value = serializers.SerializerMethodField()
    cash_balance = serializers.SerializerMethodField()
    current_investment_value = serializers.SerializerMethodField()
    holdings_count = serializers.SerializerMethodField()
    performance = PortfolioPerformanceSerializer(read_only=True)
    cash_balance_pen = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True, source='cash_balance')
    cash_balance_usd = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)

    class Meta:
        model = Portfolio
        fields = [
            'id', 'name', 'description', 'is_default', 'base_currency', 'reporting_currency',
            'cash_balance', 'cash_balance_pen', 'cash_balance_usd',
            'total_value', 'current_investment_value', 'holdings_count',
            'performance', 'created_at', 'updated_at'
        ]
        # Prevent direct cash manipulation; use transactions instead
        read_only_fields = ['created_at', 'updated_at', 'is_default', 'cash_balance', 'cash_balance_pen', 'cash_balance_usd']

    def _get_display_currency(self, obj):
        request = self.context.get('request')
        requested = request.query_params.get('currency') if request else None
        return get_portfolio_reporting_currency(obj, requested=requested)

    def get_cash_balance(self, obj):
        display_currency = self._get_display_currency(obj)
        return obj.get_total_cash_balance(display_currency)

    def get_total_value(self, obj):
        display_currency = self._get_display_currency(obj)
        if display_currency == obj.base_currency:
            return obj.total_value
        return convert_amount(obj.total_value, obj.base_currency, display_currency)

    def get_current_investment_value(self, obj):
        display_currency = self._get_display_currency(obj)
        if display_currency == obj.base_currency:
            return obj.current_investment_value
        return convert_amount(obj.current_investment_value, obj.base_currency, display_currency)

    def get_holdings_count(self, obj):
        return obj.holdings.filter(is_active=True).count()

    def validate_base_currency(self, value):
        return normalize_currency(value)

    def validate_reporting_currency(self, value):
        return normalize_currency(value)


class PortfolioDetailSerializer(PortfolioSerializer):
    holdings = HoldingSerializer(many=True, read_only=True)

    class Meta(PortfolioSerializer.Meta):
        fields = PortfolioSerializer.Meta.fields + ['holdings']
