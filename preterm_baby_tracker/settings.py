from pathlib import Path
import os
import dj_database_url   # <--- install this (pip install dj-database-url psycopg2-binary)

BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key safe in production
SECRET_KEY = 'django-insecure-s$)!c8vhroeho_n)i*c$19iuml21!=g4!s@3&89g#7^ey7tj5='

DEBUG = True

# Restrict allowed hosts to your deployed Render app
ALLOWED_HOSTS = [
    'preterm-data-tracker-9zcd.onrender.com',
    'localhost',
    '127.0.0.1',
]

# Installed apps
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'widget_tweaks',
    'tracking',
    'django_crontab',
]

# Custom user model
AUTH_USER_MODEL = 'tracking.CustomUser'

# Middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # for serving static files
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'preterm_baby_tracker.urls'

# Templates
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
# Database (SQLite locally, Postgres on Render)
# -------------------------------
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        ssl_require=False
    )
}

# Password validators
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / "static"]           # Your source static files
STATIC_ROOT = BASE_DIR / "staticfiles"             # collectstatic target

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Session management (auto logout after 10 min idle)
SESSION_COOKIE_AGE = 600          # 10 minutes
SESSION_SAVE_EVERY_REQUEST = True  # Sliding expiry

# Email settings (using Gmail SMTP)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_USE_TLS = True
EMAIL_PORT = 587
EMAIL_HOST_USER = 'barnes.okoth@gmail.com'
EMAIL_HOST_PASSWORD = 'ljet xecf wnns wxtk'  # Gmail App Password
DEFAULT_FROM_EMAIL = 'George Obanda <barnes.okoth@gmail.com>'

# Cron jobs for reminders (run every day at 10 AM Nairobi time)
CRONJOBS = [
    ('0 7 * * *', 'django.core.management.call_command', ['send_reminders']),  # 7 AM UTC = 10 AM Nairobi
]

# WhiteNoise for efficient static file handling
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Site URL for login links in reminder emails
SITE_URL = "https://preterm-data-tracker-9zcd.onrender.com"
CSRF_FAILURE_VIEW = 'tracking.views.csrf_failure'
