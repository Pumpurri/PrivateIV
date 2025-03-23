from rest_framework import serializers
from .models import Stock

class StockSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stock
        fields = '__all__'
        read_only_fields = ('last_updated',)

    def validate_current_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Price cannot be negative")
        return round(value, 2)
