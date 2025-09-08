from rest_framework import serializers
from portfolio.models import Portfolio, Holding, PortfolioPerformance
from stocks.serializers import StockSerializer


class HoldingSerializer(serializers.ModelSerializer):
    stock = StockSerializer(read_only=True)
    current_value = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    gain_loss = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    gain_loss_percentage = serializers.SerializerMethodField()

    class Meta:
        model = Holding
        fields = [
            'id', 'stock', 'quantity', 'average_purchase_price', 
            'current_value', 'gain_loss', 'gain_loss_percentage',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_gain_loss_percentage(self, obj):
        if obj.average_purchase_price > 0:
            return round((obj.gain_loss / (obj.average_purchase_price * obj.quantity)) * 100, 2)
        return 0


class PortfolioPerformanceSerializer(serializers.ModelSerializer):
    total_return = serializers.DecimalField(max_digits=10, decimal_places=4, read_only=True)
    total_return_percentage = serializers.SerializerMethodField()

    class Meta:
        model = PortfolioPerformance
        fields = [
            'total_deposits', 'total_withdrawals', 'total_return',
            'total_return_percentage', 'updated_at'
        ]
        read_only_fields = ['updated_at']

    def get_total_return_percentage(self, obj):
        if obj.total_deposits > 0:
            return round((obj.total_return / obj.total_deposits) * 100, 2)
        return 0


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
        read_only_fields = ['created_at', 'updated_at', 'is_default']

    def get_holdings_count(self, obj):
        return obj.holdings.filter(is_active=True).count()


class PortfolioDetailSerializer(PortfolioSerializer):
    holdings = HoldingSerializer(many=True, read_only=True)

    class Meta(PortfolioSerializer.Meta):
        fields = PortfolioSerializer.Meta.fields + ['holdings']