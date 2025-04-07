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
