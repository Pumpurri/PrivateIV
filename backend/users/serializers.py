from rest_framework import serializers
from .models import CustomUser  

class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = CustomUser
        fields = ('username', 'password')  # Removed username if not needed and DOB

    def create(self, validated_data):
        user = CustomUser(username=validated_data["username"])
        user.set_password(validated_data["password"])  # Hash password
        user.save()
        return user
