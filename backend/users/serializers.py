from rest_framework import serializers
from .models import CustomUser  
from dj_rest_auth.serializers import JWTSerializer
from django.contrib.auth.password_validation import validate_password


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, 
        required=True,
        validators=[validate_password]  
    )

    class Meta:
        model = CustomUser
        fields = ('username', 'password')  # Implement further logic after testing

    def create(self, validated_data):
        user = CustomUser(username=validated_data["username"])
        user.set_password(validated_data["password"])  # Hash password
        user.save()
        return user

class CustomJWTSerializer(JWTSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = self.user
        return data