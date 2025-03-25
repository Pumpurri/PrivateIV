from rest_framework import serializers
from .models import CustomUser  
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from datetime import date

class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, 
        required=True,
        style={'input_type': 'password'},
        validators=[validate_password],
         help_text="Minimum 8 characters with mix of letters and numbers"
    )
    dob = serializers.DateField(
        required=True,
        help_text="Required for regular users. Format: YYYY-MM-DD"
    )

    class Meta:
        model = CustomUser
        fields = ('email', 'password', 'full_name', 'dob')
        extra_kwargs = {
            'email': {
                'help_text': 'Must be unique. Use lowercase letters.'
            }
        }

    def validate_email(self, value):
        value = value.lower().strip()
        if CustomUser.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Email already in use.")
        return value
    
    # TODO: UPDATE_EMAIL

    def validate_dob(self, value):
        today = date.today()
        if value > today:
            raise serializers.ValidationError("Birth date cannot be in the future.")
        
        age = today.year - value.year
        if (today.month, today.day) < (value.month, value.day):
            age -= 1
            
        if age < 15:
            raise serializers.ValidationError("You must be at least 15 years old.")
        return value

    def validate_full_name(self, value):
        stripped = value.strip()
        if len(stripped) < 2 or ' ' not in stripped:
            raise serializers.ValidationError("Enter a valid full name.")
        return stripped

    def create(self, validated_data):
        try:
            user = CustomUser.objects.create_user(
                email=validated_data['email'],
                password=validated_data['password'],
                full_name=validated_data['full_name'],
                dob=validated_data['dob']
            )
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.message_dict)
        return user
    
    def validate(self, attrs):
        """Prevent regular users from creating staff/superusers"""
        if attrs.get('is_staff') or attrs.get('is_superuser'):
            raise serializers.ValidationError(
                "Privileged accounts must be created via admin."
            )
        return attrs

class CustomUserSerializer(serializers.ModelSerializer):
    age = serializers.SerializerMethodField()
    short_name = serializers.ReadOnlyField()

    class Meta:
        model = CustomUser
        fields = (
            'email', 
            'full_name',
            'short_name',
            'dob',
            'age',
            'created_at',
            'updated_at'
        )
        read_only_fields = ('email', 'created_at', 'updated_at')

    def get_age(self, obj):
        if not obj.dob:
            return None
        today = date.today()
        return today.year - obj.dob.year - (
            (today.month, today.day) < (obj.dob.month, obj.dob.day)
        )
