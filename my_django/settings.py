"""
Django settings for my_django project.
"""

from pathlib import Path
from my_django.env_config import EnvConfig
from datetime import timedelta

#==========================================================
# Celery Beat Schedule
#==========================================================
from .configs.celery_schedules import CELERY_BEAT_SCHEDULE



# =========================================
# Default User Model & Authentication Backends
# =========================================
AUTH_USER_MODEL = 'authentication.User'
AUTHENTICATION_BACKENDS = [
    'authentication.backends.RolePermissionBackend',
]


# =========================================
# load CONFIG
# =========================================
CONFIG = EnvConfig()


# =========================================
# Security
# =========================================
# Basic
SECRET_KEY = CONFIG.SECRET_KEY
DEBUG = CONFIG.DEBUG
ALLOWED_HOSTS = CONFIG.ALLOWED_HOSTS if not DEBUG else ['*']

import sys
TESTING = "test" in sys.argv or any("pytest" in arg for arg in sys.argv)
NUM_PROXIES = CONFIG.NUM_PROXIES

# Production SSL & Cookie Security
if not DEBUG and not TESTING:
    SECURE_SSL_REDIRECT = CONFIG.SECURE_SSL_REDIRECT
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_SECURE = True
    CSRF_COOKIE_HTTPONLY = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"




# =========
# CORS
# =========
CORS_ALLOW_CREDENTIALS = CONFIG.CORS_ALLOW_CREDENTIALS
CORS_ALLOW_ALL_ORIGINS  = CONFIG.CORS_ALLOW_ALL_ORIGINS
if not CORS_ALLOW_ALL_ORIGINS:
    CORS_ALLOWED_ORIGINS = CONFIG.CORS_ALLOWED_ORIGINS
    CORS_ALLOWED_ORIGIN_REGEXES = CONFIG.CORS_ALLOWED_ORIGIN_REGEXES
CSRF_TRUSTED_ORIGINS = CONFIG.CSRF_TRUSTED_ORIGINS
CORS_ALLOWED_METHODS = CONFIG.CORS_ALLOWED_METHODS
# CORS_ALLOW_HEADERS = config('CORS_ALLOWED_ORIGINS', default='', cast=str).split(",")
# if not CORS_ALLOW_HEADERS:
#     CORS_ALLOW_HEADERS = [
#         "authorization",
#         "content-type",
#     ]


# =========================================
# Base Config
# =========================================
BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_URLCONF = 'my_django.urls'
WSGI_APPLICATION = 'my_django.wsgi.application'


# =========================================
# Internationalization
# =========================================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Dhaka'
USE_I18N = True
USE_TZ = True


# =========================================
# Static files (CSS, JavaScript, Images)
# =========================================
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# =========================================
# Application definition
# =========================================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party apps
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",

    # Self Define
    'authentication',
    'core',
    'emails',
    'otp',
    'logs',
    'activity',
    'notifications',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    "corsheaders.middleware.CorsMiddleware",
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'logs.middleware.LoggingContextMiddleware',
    'activity.middleware.ActivityTrackingMiddleware',  # AFTER logs middleware — reads request.request_id
]

# =========================================
# Activity Tracking
# =========================================
ACTIVITY_SKIP_PATHS = ("/admin/", "/static/", "/media/", "/favicon.ico")


# =========================================
# Django Rest Framework
# =========================================
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],

    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],

    "DEFAULT_THROTTLE_RATES": {
        "anon": f"{CONFIG.ANON_THROTTLE_RATE_PER_MINUTE}/min",
        "user": f"{CONFIG.USER_THROTTLE_RATE_PER_MINUTE}/min",
        "login": f"{CONFIG.LOGIN_THROTTLE_RATE_PER_MINUTE}/min",
        "login_target": f"{CONFIG.LOGIN_TARGET_THROTTLE_RATE_PER_MINUTE}/min",
        "register": f"{CONFIG.REGISTER_THROTTLE_RATE_PER_MINUTE}/min",
        "change_password": f"{CONFIG.CHANGE_PASSWORD_THROTTLE_RATE_PER_MINUTE}/min",
        "reset_password": f"{CONFIG.RESET_PASSWORD_THROTTLE_RATE_PER_MINUTE}/min",
        "reset_password_target": f"{CONFIG.RESET_PASSWORD_TARGET_THROTTLE_RATE_PER_MINUTE}/min",
        "get_otp": f"{CONFIG.GET_OTP_THROTTLE_RATE_PER_DAY}/day",
        "otp_anon": f"{CONFIG.OTP_ANON_THROTTLE_RATE_PER_MINUTE}/min",
        "otp_user": f"{CONFIG.GET_OTP_THROTTLE_RATE_PER_DAY}/day",
        "otp_target": f"{CONFIG.OTP_TARGET_THROTTLE_RATE_PER_HOUR}/hour",
        "target_identifier": "60/min",
        "health": f"{CONFIG.HEALTH_THROTTLE_RATE_PER_MINUTE}/min",
    },
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "NUM_PROXIES": NUM_PROXIES,
    "EXCEPTION_HANDLER": "core.utils.exception_handler.custom_exception_handler",
}



# =========================================
# Template
# =========================================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


# =========================================
# Database
# =========================================
DB_ENGINE = CONFIG.DB_ENGINE
if (DB_ENGINE == 'django.db.backends.sqlite3'):
    DATABASES = {
        'default': {
            'ENGINE': DB_ENGINE,
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': DB_ENGINE,
            'NAME': CONFIG.DB_NAME,
            'USER': CONFIG.DB_USER,
            'PASSWORD': CONFIG.DB_PASSWORD,
            'HOST': CONFIG.DB_HOST,
            'PORT': CONFIG.DB_PORT,
        }
    }


# =========================================
# Password validation
# =========================================
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


# =========================================
# Redis
# =========================================
REDIS_URL = CONFIG.REDIS_URL


# =========================================
# Cache
# =========================================
if not TESTING and REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': REDIS_URL,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            }
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }


# =========================================
# Celery
from kombu import Queue

if TESTING:
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_BROKER_URL = "memory://"
    CELERY_RESULT_BACKEND = "cache+memory://"
else:
    CELERY_BROKER_URL = CONFIG.CELERY_BROKER_URL
    CELERY_RESULT_BACKEND = CONFIG.CELERY_RESULT_BACKEND
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Dhaka'
CELERY_TASK_IGNORE_RESULT = True

# Isolated from "default" so high-volume, non-critical activity writes can
# never starve time-sensitive tasks (emails, OTP dispatch).
# Worker: celery -A my_django worker -Q activity,default -c 4
CELERY_TASK_QUEUES = (
    Queue('default'),
    Queue('activity'),
)


# =========================================
# Email
# =========================================
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = CONFIG.EMAIL_HOST
EMAIL_PORT = CONFIG.EMAIL_PORT
EMAIL_HOST_USER = CONFIG.EMAIL_HOST_USER
EMAIL_HOST_PASSWORD = CONFIG.EMAIL_HOST_PASSWORD
EMAIL_USE_TLS = CONFIG.EMAIL_USE_TLS
DEFAULT_FROM_EMAIL = CONFIG.EMAIL_HOST_USER or 'webmaster@localhost'


# =========================================
# Simple JWT
# =========================================
SIMPLE_JWT = {
    # Basic
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "AUTH_HEADER_TYPES": ("Bearer",),
    # Lifetime
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=CONFIG.ACCESS_TOKEN_LIFETIME_MINUTES),
    "REFRESH_TOKEN_LIFETIME": timedelta(hours=CONFIG.REFRESH_TOKEN_LIFETIME_HOURS),
    # Properties
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    # Security
    "SIGNING_KEY": SECRET_KEY,
    "ALGORITHM": "HS256",
}


from logs.logging_config import get_logging_config
LOGGING = get_logging_config(service_name="my_backend")
