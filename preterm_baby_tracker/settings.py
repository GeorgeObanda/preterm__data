from pathlib import Path
import os
import dj_database_url
from dotenv import load_dotenv

# -------------------------------
# Base Directory & Environment
# -------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# -------------------------------
# Security
# -------------------------------
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "replace-me-in-production")
DEBUG = os.environ.get("DJANGO_DEBUG", "False") == "True"
ALLOWED_HOSTS = ["localhost","127.0.0.1","10.30.166.34","pretermafricastudy.ea.aku.edu"]
CSRF_TRUSTED_ORIGINS=["http://10.30.166.34:8000"]
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
# -------------------------------
# Installed Apps
# -------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'widget_tweaks',
    'django_crontab',
    'axes',

    # Local apps
    'tracking',
]

AUTH_USER_MODEL = 'tracking.CustomUser'

# -------------------------------
# Middleware
# -------------------------------
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',

    # Axes middleware (must follow AuthenticationMiddleware)
    'axes.middleware.AxesMiddleware',

    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'preterm_baby_tracker.urls'

# -------------------------------
# Templates
# -------------------------------
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'preterm_baby_tracker.wsgi.application'

# -------------------------------
# Database
# -------------------------------
DATABASES = {
    "default": {
        'ENGINE':'django.db.backends.postgresql',
        'NAME':os.environ.get('DB_NAME'),
        'USER':os.environ.get('DB_USER'),
        'PASSWORD':os.environ.get('DB_PASSWORD'),
        'HOST':os.environ.get('DB_HOST','localhost'),
        'PORT':os.environ.get('DB_PORT','5432'),
    }
}

# -------------------------------
# Authentication Backends
# -------------------------------
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesBackend',                 # Axes first
    'django.contrib.auth.backends.ModelBackend', # Default
]

# Django Axes Configuration
AXES_ENABLED = True
AXES_USE_DATABASE = True   # <--- ADD THIS
AXES_FAILURE_LIMIT = 3
AXES_LOCK_OUT_AT_FAILURE = True
AXES_COOLOFF_TIME = 0.5  # 30 minutes
AXES_RESET_ON_SUCCESS = True

AXES_LOCKOUT_PARAMETERS = ['username', 'ip_address']
AXES_USERNAME_FORM_FIELD = 'username'
AXES_LOCKOUT_CALLABLE = 'tracking.views.custom_lockout_view'

# -------------------------------
# Password Validators
# -------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# -------------------------------
# Internationalization
# -------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True

# -------------------------------
# Static & Media Files
# -------------------------------
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# -------------------------------
# Sessions (Auto Logout after 10 min)
# -------------------------------
SESSION_COOKIE_AGE = 600
SESSION_SAVE_EVERY_REQUEST = True

# -------------------------------
# Security Headers
# -------------------------------
#SESSION_COOKIE_SECURE = True
#CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# -------------------------------
# Email (Gmail SMTP)
# -------------------------------
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_USE_TLS = True
EMAIL_PORT = 587
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL", "Preterm Data Tracking System <noreply@pretermafricastudy.org>"
)

# -------------------------------
# Cron Jobs
# -------------------------------
CRONJOBS = [
    ('0 9 * * *', 'django.core.management.call_command', ['send_reminders']),
]

# -------------------------------
# Logging (Axes + Django)
# -------------------------------
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": LOG_DIR / "django.log",
        },
        "console": {"class": "logging.StreamHandler"},
    },
    "loggers": {
        "django": {"handlers": ["file", "console"], "level": "INFO", "propagate": True},
        "security": {"handlers": ["file", "console"], "level": "WARNING", "propagate": True},
        "axes.watch_login": {"handlers": ["file", "console"], "level": "INFO", "propagate": False},
        "axes.watch_login_failure": {"handlers": ["file", "console"], "level": "INFO", "propagate": False},
        "axes.watch_login_success": {"handlers": ["file", "console"], "level": "INFO", "propagate": False},
    },
}

# -------------------------------
# Custom Settings
# -------------------------------
SITE_URL = os.environ.get("SITE_URL", "https://www.pretermafricastudy.org")
CSRF_FAILURE_VIEW = 'tracking.views.csrf_failure'
