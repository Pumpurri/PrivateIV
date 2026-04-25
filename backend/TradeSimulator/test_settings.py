import os

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-testing-only')

from .settings import *

# Test database configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Simpler apps for testing - remove problematic celery beat
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'users',
    'portfolio',
    'stocks',
    # Remove celery apps for testing to avoid migration conflicts
    # 'django_celery_results',
    # 'django_celery_beat',
    'django_filters',
]

# Disable celery during testing
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Use console email backend for testing
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Disable logging during tests for cleaner output
LOGGING_CONFIG = None

# Test-specific settings
DEBUG = False
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_PROXY_SSL_HEADER = None
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False

# Speed up password hashing in tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]
