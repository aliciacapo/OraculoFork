import os
from pathlib import Path

# Load environment variables from .env file only if not in Docker
# Docker containers should use environment variables passed by Docker Compose
if not os.getenv('DOCKER_CONTAINER'):
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        # dotenv not available, skip loading
        pass

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-change-me-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'django-auth', '0.0.0.0']

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'django_auth.apps.auth_app',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'django_auth.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'src' / 'django_auth' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'django_auth.wsgi.application'


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'databasex'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASSWORD', 'postgres'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

# Password validation
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

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# JWT Configuration
from datetime import timedelta

JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')

if not JWT_SECRET_KEY or JWT_SECRET_KEY.strip() == '':
    import sys
    print("CRITICAL ERROR: JWT_SECRET_KEY environment variable is not set or empty!")
    print("This is required for JWT token generation and validation.")
    print("Available environment variables:")
    for key in sorted(os.environ.keys()):
        if 'JWT' in key or 'SECRET' in key or 'TOKEN' in key:
            print(f"  {key}={os.environ[key][:20]}..." if len(os.environ[key]) > 20 else f"  {key}={os.environ[key]}")
    print("Please ensure JWT_SECRET_KEY is set in Docker Compose environment.")
    sys.exit(1)

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'SIGNING_KEY': JWT_SECRET_KEY,
    'ALGORITHM': 'HS256',
}

FERNET_KEY = os.getenv('FERNET_KEY')
if not FERNET_KEY:
    from cryptography.fernet import Fernet
    FERNET_KEY = Fernet.generate_key().decode()
    print(f"Generated FERNET_KEY for development: {FERNET_KEY}")

INTERNAL_AUTH_TOKEN = os.getenv('INTERNAL_AUTH_TOKEN')
if not INTERNAL_AUTH_TOKEN:
    import sys
    print("CRITICAL ERROR: INTERNAL_AUTH_TOKEN environment variable is not set!")
    print("This is required for backend-to-backend authentication.")
    print("Please ensure INTERNAL_AUTH_TOKEN is set in Docker Compose environment.")
    sys.exit(1)

# Login/Logout URLs
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/tokens/'
LOGOUT_REDIRECT_URL = '/login/'