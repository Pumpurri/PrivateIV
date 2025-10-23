from rest_framework import serializers
from portfolio.models import Portfolio, Holding, PortfolioPerformance
from stocks.serializers import StockSerializer
from decimal import Decimal, ROUND_HALF_UP


class HoldingSerializer(serializers.ModelSerializer):
    stock = StockSerializer(read_only=True)
    current_value = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    gain_loss = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    gain_loss_percentage = serializers.SerializerMethodField()
    cost_basis = serializers.SerializerMethodField()

    class Meta:
        model = Holding
        fields = [
            'id', 'stock', 'quantity', 'average_purchase_price',
            'current_value', 'gain_loss', 'gain_loss_percentage',
            'cost_basis', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_cost_basis(self, obj):
        """Total cost in portfolio base currency (already in PEN)

        The holding's average_purchase_price is already in the portfolio's base currency
        (PEN), having been converted using historical FX rates during purchase.
        """
        cost_basis = obj.average_purchase_price * Decimal(obj.quantity)
        return cost_basis.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def get_gain_loss_percentage(self, obj):
        if obj.average_purchase_price > 0 and obj.quantity:
            base = (obj.average_purchase_price * Decimal(obj.quantity))
            if base != 0:
                pct = (obj.gain_loss / base) * Decimal('100')
                return pct.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return Decimal('0.00')


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
    total_value = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    current_investment_value = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    holdings_count = serializers.SerializerMethodField()
    performance = PortfolioPerformanceSerializer(read_only=True)

    class Meta:
        model = Portfolio
        fields = [
            'id', 'name', 'description', 'is_default', 'cash_balance',
            'total_value', 'current_investment_value', 'holdings_count',
            'performance', 'created_at', 'updated_at'
        ]
        # Prevent direct cash manipulation; use transactions instead
        read_only_fields = ['created_at', 'updated_at', 'is_default', 'cash_balance']

    def get_holdings_count(self, obj):
        return obj.holdings.filter(is_active=True).count()


class PortfolioDetailSerializer(PortfolioSerializer):
    holdings = HoldingSerializer(many=True, read_only=True)

    class Meta(PortfolioSerializer.Meta):
        fields = PortfolioSerializer.Meta.fields + ['holdings']
