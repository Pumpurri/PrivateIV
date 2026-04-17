from rest_framework import serializers
from portfolio.models import Transaction
from portfolio.services.currency_service import get_transaction_amount_in_currency, get_transaction_original_currency
from stocks.models import Stock
from portfolio.services.currency_service import normalize_currency

class TransactionSerializer(serializers.ModelSerializer):
    portfolio_id = serializers.IntegerField(source='portfolio.id', read_only=True)
    idempotency_key = serializers.UUIDField(required=False)
    transaction_type_display = serializers.SerializerMethodField()
    stock_symbol = serializers.CharField(source='stock.symbol', read_only=True)
    stock_name = serializers.CharField(source='stock.name', read_only=True)
    original_currency = serializers.SerializerMethodField()
    display_amount = serializers.SerializerMethodField()
    display_currency = serializers.SerializerMethodField()
    counter_amount_display = serializers.SerializerMethodField()
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
            'cash_currency',
            'counter_currency',
            'counter_amount',
            'counter_amount_display',
            'original_currency',
            'display_amount',
            'display_currency',
            'fx_rate',
            'fx_rate_type',
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
            'original_currency',
            'fx_rate',
            'fx_rate_type',
            'timestamp',
            'portfolio_id',
            'counter_amount',
        ]
        # 'transaction_type' is readable so clients can filter on it

    def get_transaction_type_display(self, obj):
        # Localize transaction type to Spanish labels
        mapping = {
            Transaction.TransactionType.BUY: 'Compra',
            Transaction.TransactionType.SELL: 'Venta',
            Transaction.TransactionType.DEPOSIT: 'Depósito',
            Transaction.TransactionType.WITHDRAWAL: 'Retiro',
            Transaction.TransactionType.CONVERT: 'Conversión FX',
        }
        return mapping.get(obj.transaction_type, obj.get_transaction_type_display())

    def get_original_currency(self, obj):
        return get_transaction_original_currency(obj)

    def get_display_currency(self, obj):
        requested = self.context.get('display_currency')
        if requested:
            return normalize_currency(requested)
        return self.get_original_currency(obj)

    def get_display_amount(self, obj):
        return get_transaction_amount_in_currency(
            obj,
            self.get_display_currency(obj),
            snapshot_date=obj.timestamp.date(),
        )

    def get_counter_amount_display(self, obj):
        if obj.counter_amount is None or not obj.counter_currency:
            return None
        return get_transaction_amount_in_currency(
            obj,
            self.get_display_currency(obj),
            use_counter_amount=True,
            snapshot_date=obj.timestamp.date(),
        )

    def validate(self, data):
        """Enterprise-grade validation for transaction integrity"""
        trade_types = [Transaction.TransactionType.BUY, Transaction.TransactionType.SELL]
        transaction_type = data.get('transaction_type')

        if transaction_type in trade_types:
            if not data.get('stock'):
                raise serializers.ValidationError("Stock is required for trade transactions")
            if not data.get('quantity'):
                raise serializers.ValidationError("Quantity is required for trade transactions")
            cash_currency = data.get('cash_currency')
            if cash_currency:
                data['cash_currency'] = normalize_currency(cash_currency)
        elif transaction_type == Transaction.TransactionType.CONVERT:
            if not data.get('amount'):
                raise serializers.ValidationError("Amount is required for FX conversion transactions")
            if not data.get('cash_currency'):
                raise serializers.ValidationError("cash_currency is required for FX conversion transactions")
            if not data.get('counter_currency'):
                raise serializers.ValidationError("counter_currency is required for FX conversion transactions")
            data['cash_currency'] = normalize_currency(data.get('cash_currency'))
            data['counter_currency'] = normalize_currency(data.get('counter_currency'))
            if data['cash_currency'] == data['counter_currency']:
                raise serializers.ValidationError("cash_currency and counter_currency must differ")
        else:
            if not data.get('amount'):
                raise serializers.ValidationError("Amount is required for cash transactions")
            if data.get('cash_currency'):
                data['cash_currency'] = normalize_currency(data.get('cash_currency'))
            else:
                data['cash_currency'] = 'PEN'

        return data
