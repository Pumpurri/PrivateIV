from rest_framework import serializers
from portfolio.models import Transaction

class TransactionSerializer(serializers.ModelSerializer):
    stock_symbol = serializers.CharField(source='stock.symbol', read_only=True)
    stock_name = serializers.CharField(source='stock.name', read_only=True)
    portfolio_id = serializers.UUIDField(source='portfolio.id', read_only=True)
    transaction_type = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = [
            'id',
            'transaction_type',
            'stock_symbol',
            'stock_name',
            'quantity',
            'executed_price',
            'amount',
            'timestamp',
            'portfolio_id'
        ]
        read_only_fields = fields

    def get_transaction_type(self, obj):
        return obj.get_transaction_type_display()