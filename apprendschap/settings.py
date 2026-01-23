from pathlib import Path
import os
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-)%m(dc&tyxo6_57wna1gx=0crakl4-g7*1)0)gwqk!(a4z2jm4')

DEBUG = os.getenv('DEBUG', 'True') == 'True'  # True en local, False sur Render

ALLOWED_HOSTS = ['*']  # À restreindre en production réelle (ex: ['apprendschap-back.onrender.com'])

# Applications installées
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_filters',
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'drf_spectacular',

    # Tes apps
    'utilisateurs',
    'academic_structure',
    'cours',
    'quiz',
    'examens',
    'abonnements',
    'progression',
    'ia',
    'gamification',
    'analytics',
]

# Modèle utilisateur personnalisé
AUTH_USER_MODEL = 'utilisateurs.Utilisateur'

# Authentification (vide = pas d'auth obligatoire)
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # ← Ici pour servir statics (admin CSS inclus)
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'apprendschap.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'apprendschap.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Pour Render → utilise Postgres quand tu passeras à dj-database-url
# DATABASES['default'] = dj_database_url.config(default=os.getenv('DATABASE_URL'))

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JS, Images) → pour Whitenoise
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
# STATICFILES_DIRS = [
#     BASE_DIR / 'static',
#     BASE_DIR.parent / 'apprendschap_frontend' / 'assets',
# ]
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []


STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'  # ← Pour compression + manifest

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "gpt-4o-mini"

# Email
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [],  # ← Plus d'auth obligatoire → tout public
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend'],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# CORS
CORS_ALLOW_ALL_ORIGINS = True  # À restreindre en prod

# Configuration Wave
WAVE_API_KEY = os.getenv('WAVE_API_KEY', 'your_wave_api_key')
WAVE_BUSINESS_ID = os.getenv('WAVE_BUSINESS_ID', 'your_business_id')
WAVE_CALLBACK_URL = os.getenv('WAVE_CALLBACK_URL', 'https://apprendschap-back.onrender.com/api/abonnements/wave-callback/')
WAVE_ENVIRONMENT = os.getenv('WAVE_ENVIRONMENT', 'sandbox')

# Swagger / drf-spectacular
SPECTACULAR_SETTINGS = {
    'TITLE': 'Apprendschap API',
    'DESCRIPTION': 'API pour l\'application Apprendschap',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': True,

    # Supprime les cadenas et le bouton Authorize dans Swagger
    'SECURITY': [],
    'SERVE_AUTHENTICATION': [],
    'SERVE_PERMISSIONS': ['rest_framework.permissions.AllowAny'],

    # Optionnel : enlève les warnings inutiles
    'DISABLE_ERRORS_AND_WARNINGS': False,
}