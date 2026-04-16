import pytest
from datetime import date, timedelta
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
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
        assert data['id'] == factory_user.id
        assert data['email'] == factory_user.email
        assert data['full_name'] == factory_user.full_name
        assert data['is_staff'] == factory_user.is_staff
        assert data['is_superuser'] == factory_user.is_superuser
        assert data['age'] >= 15

    def test_read_only_fields(self, factory_user):
        initial_email = factory_user.email
        serializer = CustomUserSerializer(
            instance=factory_user,
            data={
                'email': 'new@example.com',
                'full_name': 'Updated Name',
                'is_staff': True,
                'is_superuser': True,
            },
            partial=True
        )
        assert serializer.is_valid()
        serializer.save()
        factory_user.refresh_from_db()
        assert factory_user.email == initial_email
        assert factory_user.full_name == 'Updated Name'
        assert factory_user.is_staff is False
        assert factory_user.is_superuser is False

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

    def test_duplicate_email_registration(self, client, user_data, factory_user):
        UserFactory(email=user_data['email'])
        response = client.post(reverse('register'), user_data)
        assert response.status_code == 400
        assert 'email' in response.data

    def test_age_validation(self, client, user_data):
        user_data['dob'] = INVALID_YOUNG_DOB.isoformat()
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
    def test_successful_login(self, client, factory_user):
        response = client.post(reverse('login'), {
            'email': factory_user.email,
            'password': 'testpass123!'
        })
        assert response.status_code == 200
        assert 'email' in response.data

    def test_invalid_credentials(self, client, factory_user):
        response = client.post(reverse('login'), {
            'email': factory_user.email,
            'password': 'wrongpassword'
        })
        assert response.status_code == 401

    def test_case_insensitive_login(self, client, factory_user):
        response = client.post(reverse('login'), {
            'email': factory_user.email.upper(),
            'password': 'testpass123!'
        })
        assert response.status_code == 200

@pytest.mark.django_db
class TestUserProfile:
    def test_profile_retrieval(self, client, factory_user):
        client.force_authenticate(user=factory_user)
        response = client.get(reverse('user-profile'))
        assert response.status_code == 200
        assert response.data['id'] == factory_user.id
        assert response.data['email'] == factory_user.email
        assert response.data['full_name'] == factory_user.full_name
        assert response.data['is_staff'] == factory_user.is_staff
        assert response.data['is_superuser'] == factory_user.is_superuser

    def test_admin_profile_returns_staff_flags(self, client, factory_admin):
        client.force_authenticate(user=factory_admin)
        response = client.get(reverse('user-profile'))
        assert response.status_code == 200
        assert response.data['id'] == factory_admin.id
        assert response.data['email'] == factory_admin.email
        assert response.data['full_name'] == factory_admin.full_name
        assert response.data['is_staff'] is True
        assert response.data['is_superuser'] is True

    def test_profile_update(self, client, factory_user):
        client.force_authenticate(user=factory_user)
        new_name = "Updated Name"
        response = client.patch(reverse('user-profile'), {'full_name': new_name})
        assert response.status_code == 200
        factory_user.refresh_from_db()
        assert factory_user.full_name == new_name

@pytest.mark.django_db
class TestAdminEndpoints:
    def test_admin_user_list(self, client, factory_admin):
        client.force_authenticate(user=factory_admin)
        response = client.get(reverse('user-list'))
        assert response.status_code == 200

    def test_regular_user_access_admin_list(self, client, factory_user):
        client.force_authenticate(user=factory_user)
        response = client.get(reverse('user-list'))
        assert response.status_code == 403

@pytest.mark.django_db
class TestLogout:
    def test_successful_logout(self, client, factory_user):
        client.force_authenticate(user=factory_user)
        response = client.post(reverse('logout'))
        assert response.status_code == 200
        assert not hasattr(client, 'user') 


@pytest.mark.django_db
class TestPasswordReset:
    @pytest.fixture(autouse=True)
    def reset_settings(self, settings):
        settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
        settings.PASSWORD_RESET_URL_TEMPLATE = 'https://app.example/reset-password?uid={uid}&token={token}'
        settings.DEFAULT_FROM_EMAIL = 'support@example.com'
        settings.SUPPORT_EMAIL = 'support@example.com'
        mail.outbox = []

    def test_request_sends_reset_email_for_existing_user(self, client, factory_user):
        response = client.post(reverse('password-reset'), {'email': factory_user.email})

        assert response.status_code == 200
        assert response.data == {
            'detail': 'If an account exists for that email, password reset instructions have been sent.',
            'support_email': 'support@example.com',
        }
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [factory_user.email]
        assert 'https://app.example/reset-password?' in mail.outbox[0].body
        assert 'uid=' in mail.outbox[0].body
        assert 'token=' in mail.outbox[0].body

    def test_request_does_not_reveal_unknown_email(self, client):
        response = client.post(reverse('password-reset'), {'email': 'missing@example.com'})

        assert response.status_code == 200
        assert response.data['support_email'] == 'support@example.com'
        assert len(mail.outbox) == 0

    def test_confirm_resets_password_with_valid_token(self, client, factory_user):
        uid = urlsafe_base64_encode(force_bytes(factory_user.pk))
        token = default_token_generator.make_token(factory_user)

        response = client.post(reverse('password-reset-confirm'), {
            'uid': uid,
            'token': token,
            'new_password': 'NewValidPass123!',
        })

        assert response.status_code == 200
        factory_user.refresh_from_db()
        assert factory_user.check_password('NewValidPass123!')
        assert authenticate(email=factory_user.email, password='NewValidPass123!') == factory_user

    def test_confirm_rejects_invalid_token(self, client, factory_user):
        uid = urlsafe_base64_encode(force_bytes(factory_user.pk))

        response = client.post(reverse('password-reset-confirm'), {
            'uid': uid,
            'token': 'invalid-token',
            'new_password': 'NewValidPass123!',
        })

        assert response.status_code == 400
        factory_user.refresh_from_db()
        assert factory_user.check_password('testpass123!')

    def test_confirm_rejects_weak_password(self, client, factory_user):
        uid = urlsafe_base64_encode(force_bytes(factory_user.pk))
        token = default_token_generator.make_token(factory_user)

        response = client.post(reverse('password-reset-confirm'), {
            'uid': uid,
            'token': token,
            'new_password': 'short',
        })

        assert response.status_code == 400
        factory_user.refresh_from_db()
        assert factory_user.check_password('testpass123!')

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
