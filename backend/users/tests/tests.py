import pytest
from datetime import date, timedelta
from django.urls import reverse
from rest_framework.test import APIClient
from users.models import CustomUser
from users.serializers import UserCreateSerializer, CustomUserSerializer
from rest_framework.exceptions import ValidationError
from users.tests.factories import UserFactory

# Constants -------------------------------------------------------------------
VALID_DOB = date(2008, 1, 1)
INVALID_YOUNG_DOB = date(2015, 1, 1)
FUTURE_DOB = date.today() + timedelta(days=365)

# Fixtures --------------------------------------------------------------------
@pytest.fixture
def client():
    return APIClient()

@pytest.fixture
def factory_user():
    """User created via factory"""
    return UserFactory()

@pytest.fixture
def factory_admin():
    """Admin user created via factory"""
    return UserFactory(is_superuser=True, is_staff=True)

@pytest.fixture
def user_data():
    return {
        'email': 'testuser@example.com',
        'password': 'ValidPass123!',
        'full_name': 'Test User',
        'dob': VALID_DOB.isoformat()
    }

# Model Tests -----------------------------------------------------------------
@pytest.mark.django_db
class TestCustomUserModel:
    def test_user_creation(self):
        user = CustomUser.objects.create_user(
            email='test@example.com',
            password='testpass123!',
            full_name='Test User',
            dob=VALID_DOB
        )
        assert user.email == 'test@example.com'
        assert user.check_password('testpass123!')
        assert user.full_name == 'Test User'
        assert user.dob == VALID_DOB

    def test_string_representation(self):
        user = UserFactory(full_name='Test User', email='test@example.com')
        assert str(user) == 'Test User (test@example.com)'

    def test_short_name_property(self):
        user = UserFactory(full_name='John Doe')
        assert user.short_name == 'John'

    def test_email_normalization(self):
        user = CustomUser.objects.create_user(
            email='Test@Example.COM',
            password='testpass123!',
            full_name='Test User',
            dob=VALID_DOB
        )
        assert user.email == 'test@example.com'

    def test_missing_required_fields(self):
        with pytest.raises(ValueError):
            CustomUser.objects.create_user(
                email='invalid@example.com',
                password='testpass'
            )

# Serializer Tests -----------------------------------------------------------
@pytest.mark.django_db
class TestUserCreateSerializer:
    def test_valid_data(self, user_data):
        serializer = UserCreateSerializer(data=user_data)
        assert serializer.is_valid()

    def test_invalid_password(self, user_data):
        user_data['password'] = 'simple'
        serializer = UserCreateSerializer(data=user_data)
        assert not serializer.is_valid()
        assert 'password' in serializer.errors

    def test_duplicate_email(self, factory_user):
        serializer = UserCreateSerializer(data={
            'email': factory_user.email,
            'password': 'testpass123!',
            'full_name': 'New User',
            'dob': factory_user.dob.isoformat()
        })
        assert not serializer.is_valid()
        assert 'email' in serializer.errors

    def test_case_insensitive_email_validation(self, user_data):
        user_data['email'] = 'TEST@EXAMPLE.COM'
        serializer = UserCreateSerializer(data=user_data)
        assert serializer.is_valid()
        assert serializer.validated_data['email'] == 'test@example.com'

@pytest.mark.django_db
class TestCustomUserSerializer:
    def test_serialized_data(self, factory_user):
        serializer = CustomUserSerializer(factory_user)
        data = serializer.data
        assert data['email'] == factory_user.email
        assert data['full_name'] == factory_user.full_name
        assert data['age'] >= 15

    def test_read_only_fields(self, factory_user):
        initial_email = factory_user.email
        serializer = CustomUserSerializer(
            instance=factory_user,
            data={'email': 'new@example.com', 'full_name': 'Updated Name'},
            partial=True
        )
        assert serializer.is_valid()
        serializer.save()
        factory_user.refresh_from_db()
        assert factory_user.email == initial_email
        assert factory_user.full_name == 'Updated Name'
