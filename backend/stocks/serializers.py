from rest_framework import serializers
from .models import Stock
from decimal import Decimal, ROUND_HALF_UP

class StockSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stock
        fields = '__all__'
        read_only_fields = ('last_updated',)

    def validate_current_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Price cannot be negative")
        if not isinstance(value, Decimal):
            value = Decimal(str(value))
        return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
