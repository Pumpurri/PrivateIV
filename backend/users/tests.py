import pytest
from datetime import date, timedelta
from django.urls import reverse
from rest_framework.test import APIClient
from .models import CustomUser
from .serializers import UserCreateSerializer, CustomUserSerializer
from rest_framework.exceptions import ValidationError

# Constants -------------------------------------------------------------------
VALID_DOB = str(date(2008, 1, 1))
INVALID_YOUNG_DOB = str(date(2015, 1, 1))
FUTURE_DOB = str(date.today() + timedelta(days=365))

# Fixtures --------------------------------------------------------------------
@pytest.fixture
def client():
    return APIClient()

@pytest.fixture
def user_data():
    return {
        'email': 'test@example.com',
        'password': 'SecurePass123!',
        'full_name': 'Test User',
        'dob': VALID_DOB
    }

@pytest.fixture
def admin_user():
    return CustomUser.objects.create_superuser(
        email='admin@example.com',
        password='adminpass',
        full_name='Admin User'
    )

@pytest.fixture
def regular_user(user_data):
    return CustomUser.objects.create_user(**user_data)

# Model Tests -----------------------------------------------------------------
@pytest.mark.django_db
class TestCustomUserModel:
    def test_user_creation(self, regular_user):
        assert regular_user.email == 'test@example.com'
        assert regular_user.check_password('SecurePass123!')
        assert regular_user.full_name == 'Test User'
        assert regular_user.dob == date.fromisoformat(VALID_DOB)

    def test_string_representation(self, regular_user):
        assert str(regular_user) == 'Test User (test@example.com)'

    def test_short_name_property(self, regular_user):
        regular_user.full_name = 'John Doe'
        assert regular_user.short_name == 'John'

    def test_email_normalization(self):
        user = CustomUser.objects.create_user(
            email='Test@Example.COM',
            password='testpass',
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

    def test_duplicate_email(self, user_data, regular_user):
        serializer = UserCreateSerializer(data=user_data)
        assert not serializer.is_valid()
        assert 'email' in serializer.errors

    def test_case_insensitive_email_validation(self, user_data):
        user_data['email'] = 'TEST@EXAMPLE.COM'
        serializer = UserCreateSerializer(data=user_data)
        assert serializer.is_valid()
        assert serializer.validated_data['email'] == 'test@example.com'

@pytest.mark.django_db
class TestCustomUserSerializer:
    def test_serialized_data(self, regular_user):
        serializer = CustomUserSerializer(regular_user)
        data = serializer.data
        assert data['email'] == regular_user.email
        assert data['full_name'] == regular_user.full_name
        assert data['age'] >= 16

    def test_read_only_fields(self, regular_user, client):
        client.force_authenticate(user=regular_user)
        response = client.patch(
            reverse('user-profile'),
            {'email': 'new@example.com'}
        )
        assert response.status_code == 200
        assert response.data['email'] == 'test@example.com'  # Email remains unchanged

# View Tests ------------------------------------------------------------------
@pytest.mark.django_db
class TestUserRegistration:
    def test_successful_registration(self, client, user_data):
        url = reverse('register')
        response = client.post(url, user_data)
        assert response.status_code == 201
        assert response.data['email'] == user_data['email'].lower()
        assert CustomUser.objects.count() == 1

    def test_registration_missing_fields(self, client):
        response = client.post(reverse('register'), {'email': 'test@example.com'})
        assert response.status_code == 400
        assert 'password' in response.data
        assert 'full_name' in response.data
        assert 'dob' in response.data

    def test_duplicate_email_registration(self, client, user_data):
        CustomUser.objects.create_user(**user_data)
        response = client.post(reverse('register'), user_data)
        assert response.status_code == 400
        assert 'email' in response.data

    def test_age_validation(self, client, user_data):
        user_data['dob'] = INVALID_YOUNG_DOB
        response = client.post(reverse('register'), user_data)
        assert response.status_code == 400
        assert 'dob' in response.data

    def test_future_dob_validation(self, client, user_data):
        user_data['dob'] = FUTURE_DOB
        response = client.post(reverse('register'), user_data)
        assert response.status_code == 400
        assert 'dob' in response.data
        assert 'Birth date cannot be in the future.' in response.data['dob']

@pytest.mark.django_db
class TestUserLogin:
    def test_successful_login(self, client, regular_user):
        response = client.post(reverse('login'), {
            'email': regular_user.email,
            'password': 'SecurePass123!'
        })
        assert response.status_code == 200
        assert 'email' in response.data

    def test_invalid_credentials(self, client, regular_user):
        response = client.post(reverse('login'), {
            'email': regular_user.email,
            'password': 'wrongpassword'
        })
        assert response.status_code == 401

    def test_case_insensitive_login(self, client, regular_user):
        response = client.post(reverse('login'), {
            'email': regular_user.email.upper(),
            'password': 'SecurePass123!'
        })
        assert response.status_code == 200

@pytest.mark.django_db
class TestUserProfile:
    def test_profile_retrieval(self, client, regular_user):
        client.force_authenticate(user=regular_user)
        response = client.get(reverse('user-profile'))
        assert response.status_code == 200
        assert response.data['email'] == regular_user.email

    def test_profile_update(self, client, regular_user):
        client.force_authenticate(user=regular_user)
        new_name = "Updated Name"
        response = client.patch(reverse('user-profile'), {'full_name': new_name})
        assert response.status_code == 200
        regular_user.refresh_from_db()
        assert regular_user.full_name == new_name

@pytest.mark.django_db
class TestAdminEndpoints:
    def test_admin_user_list(self, client, admin_user):
        client.force_authenticate(user=admin_user)
        response = client.get(reverse('user-list'))
        assert response.status_code == 200

    def test_regular_user_access_admin_list(self, client, regular_user):
        client.force_authenticate(user=regular_user)
        response = client.get(reverse('user-list'))
        assert response.status_code == 403

@pytest.mark.django_db
class TestLogout:
    def test_successful_logout(self, client, regular_user):
        client.force_authenticate(user=regular_user)
        response = client.post(reverse('logout'))
        assert response.status_code == 200
        assert not hasattr(client, 'user') 

@pytest.mark.django_db
def test_csrf_endpoint(client):
    response = client.get(reverse('csrf'))
    assert response.status_code == 200
    data = response.json()
    assert 'detail' in data
    assert 'csrftoken' in response.cookies

# Helper Tests ----------------------------------------------------------------
@pytest.mark.django_db
def test_user_manager_create_superuser():
    admin = CustomUser.objects.create_superuser(
        email='admin@test.com',
        password='adminpass',
        full_name='Admin'
    )
    assert admin.is_superuser
    assert admin.is_staff
    assert admin.dob is None

@pytest.mark.django_db
def test_user_manager_create_user_missing_dob():
    with pytest.raises(ValueError):
        CustomUser.objects.create_user(
            email='test@example.com',
            password='testpass',
            full_name='Test User'
        )

# Validation Tests ------------------------------------------------------------
@pytest.mark.django_db
def test_future_dob_validation():
    with pytest.raises(Exception) as e:
        CustomUser.objects.create_user(
            email='future@example.com',
            password='testpass',
            full_name='Future User',
            dob=date.today() + timedelta(days=365)
        )
    assert 'User must be at least 15 years old.' in str(e.value)

@pytest.mark.django_db
def test_invalid_full_name_validation():
    serializer = UserCreateSerializer(data={
        'email': 'invalid@example.com',
        'password': 'Testpass123.',
        'full_name': 'A',
        'dob': VALID_DOB
    })
    with pytest.raises(ValidationError):
        serializer.is_valid(raise_exception=True)