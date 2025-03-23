from rest_framework import serializers
from .models import Stock

class StockSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stock
        fields = ['id', 'symbol', 'name', 'current_price', 'last_updated']

    def validate_current_price(self, value):
        """Prevent negative prices"""
        if value < 0:
            raise serializers.ValidationError("Price cannot be negative")
        return value