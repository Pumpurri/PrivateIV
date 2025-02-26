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
        fields = ('email', 'password', 'full_name', 'dob')

    def create(self, validated_data):
        user = CustomUser.objects.create_user (
            email=validated_data["email"],
            password=validated_data["password"],
            full_name=validated_data["full_name"],
            dob=validated_data["dob"]
        )
        return user

class CustomUserSerializer(serializers.ModelSerializer):
    short_name = serializers.ReadOnlyField()

    class Meta:
        model = CustomUser
        fields = ('email', 'full_name', 'dob', 'short_name', 'created_at', 'updated_at')
        read_only_fields = ('created_at', 'updated_at') 

class CustomJWTSerializer(JWTSerializer):
    user  = CustomUserSerializer(read_only=True)
    short_name = serializers.CharField(source='user.short_name', read_only=True)
    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = CustomUserSerializer(self.user).data
        return data