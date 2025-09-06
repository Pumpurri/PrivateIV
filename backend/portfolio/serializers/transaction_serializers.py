from rest_framework import serializers
from portfolio.models import Transaction
from stocks.models import Stock

class TransactionSerializer(serializers.ModelSerializer):
    portfolio_id = serializers.UUIDField(source='portfolio.id', read_only=True)
    idempotency_key = serializers.UUIDField(required=True)
    transaction_type_display = serializers.SerializerMethodField()
    stock_symbol = serializers.CharField(source='stock.symbol', read_only=True)
    stock_name = serializers.CharField(source='stock.name', read_only=True)
    stock = serializers.PrimaryKeyRelatedField(
        queryset=Stock.objects.all(),
        write_only=True,
        required=False
    )

    class Meta:
        model = Transaction
        fields = [
            'id',
            'transaction_type',
            'transaction_type_display',
            'stock',
            'stock_symbol',
            'stock_name',
            'quantity',
            'executed_price',
            'amount',
            'timestamp',
            'portfolio_id',
            'idempotency_key',
        ]
        read_only_fields = [
            'id',
            'transaction_type_display',
            'stock_symbol',
            'stock_name',
            'executed_price',
            'timestamp',
            'portfolio_id',
        ]
        extra_kwargs = {
            'transaction_type': {'write_only': True},
            'amount': {'write_only': True}
        }

    def get_transaction_type_display(self, obj):
        return obj.get_transaction_type_display()

    def validate(self, data):
        """Enterprise-grade validation for transaction integrity"""
        trade_types = [Transaction.TransactionType.BUY, Transaction.TransactionType.SELL]
        
        if data.get('transaction_type') in trade_types:
            if not data.get('stock'):
                raise serializers.ValidationError("Stock is required for trade transactions")
            if not data.get('quantity'):
                raise serializers.ValidationError("Quantity is required for trade transactions")
        else:
            if not data.get('amount'):
                raise serializers.ValidationError("Amount is required for cash transactions")
        
        return data