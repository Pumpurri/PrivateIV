from pathlib import Path
import os
from TradeSimulator.env import env_flag, load_optional_dotenv

# Local dotenv loading is explicit opt-in to avoid accidentally pulling dev secrets into
# release or hosted environments. Use DJANGO_LOAD_DOTENV=true for local-only workflows.
load_optional_dotenv()

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Security
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY environment variable is not set. "
        "Set it in your host environment or in a local .env file (never commit .env)."
    )

DEBUG = env_flag('DEBUG', default=False)
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_extensions',
    'corsheaders',
    'rest_framework',
    'users',
    'portfolio',
    'stocks',
    'django_celery_results',
    'django_celery_beat',
    'django_filters',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Must be after SecurityMiddleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'TradeSimulator.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.csrf',
            ],
        },
    },
]

WSGI_APPLICATION = 'TradeSimulator.wsgi.application'

# Database configuration
# Railway provides DATABASE_URL, parse it with dj-database-url
import dj_database_url

database_url = os.getenv('DATABASE_URL') or os.getenv('DATABASE_PUBLIC_URL')

if database_url:
    DATABASES = {
        'default': dj_database_url.parse(
            database_url,
            conn_max_age=600,
            ssl_require=False,
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME', 'privateiv'),
            'USER': os.getenv('DB_USER', os.getenv('USER', 'postgres')),
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '5432'),
            'CONN_MAX_AGE': 600,
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
FX_MARKET_TIME_ZONE = os.getenv('FX_MARKET_TIME_ZONE', 'America/Lima')
LOCAL_MARKET_TIME_ZONE = os.getenv('LOCAL_MARKET_TIME_ZONE', FX_MARKET_TIME_ZONE)
US_MARKET_TIME_ZONE = os.getenv('US_MARKET_TIME_ZONE', 'America/New_York')
LOCAL_MARKET_CLOSE_TIME = os.getenv('LOCAL_MARKET_CLOSE_TIME', '16:00')
US_MARKET_CLOSE_TIME = os.getenv('US_MARKET_CLOSE_TIME', '16:00')
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# WhiteNoise configuration for serving static files in production
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Authentication
AUTH_USER_MODEL = 'users.CustomUser'

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_THROTTLE_RATES': {
        'user': os.getenv('DRF_USER_THROTTLE_RATE', '60/min'),
        'auth_login': os.getenv('DRF_AUTH_LOGIN_THROTTLE_RATE', '10/min'),
        'auth_register': os.getenv('DRF_AUTH_REGISTER_THROTTLE_RATE', '5/hour'),
        'auth_password_reset_request': os.getenv('DRF_AUTH_PASSWORD_RESET_REQUEST_THROTTLE_RATE', '5/hour'),
        'auth_password_reset_confirm': os.getenv('DRF_AUTH_PASSWORD_RESET_CONFIRM_THROTTLE_RATE', '10/hour'),
    },
}

# HTTPS / HSTS (only in production)
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# CSRF Protection
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = 'None' if not DEBUG else 'Lax'  # None required for cross-domain
CSRF_TRUSTED_ORIGINS = os.getenv(
    'CSRF_TRUSTED_ORIGINS',
    'http://localhost:5173,http://localhost:8000'
).split(',')

SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = 'None' if not DEBUG else 'Lax'  # None required for cross-domain

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = os.getenv(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:5173,http://localhost:8000'
).split(',')

CORS_EXPOSE_HEADERS = ['Content-Type', 'X-CSRFToken']

DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'no-reply@tradesimulator.local')
SUPPORT_EMAIL = os.getenv('SUPPORT_EMAIL', DEFAULT_FROM_EMAIL)
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:5173')
PASSWORD_RESET_URL_TEMPLATE = os.getenv(
    'PASSWORD_RESET_URL_TEMPLATE',
    f"{FRONTEND_URL.rstrip('/')}/reset-password?uid={{uid}}&token={{token}}"
)

CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL')
CELERY_RESULT_BACKEND = 'django-db'
CELERY_CACHE_BACKEND = 'django-cache'
CELERY_TIMEZONE = 'America/New_York'
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
