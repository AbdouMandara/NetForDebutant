import environ
from pathlib import Path

# Initialisation
env = environ.Env(
    DEBUG=(bool, False)
)

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = environ.Path(__file__) - 2

environ.Env.read_env(BASE_DIR('.env'))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env('DEBUG')

# Lien avec Google pour l'authentification via Google OAuth2.0 pour le web et android
GOOGLE_ID_CLIENT_FOR_WEB = env('GOOGLE_ID_CLIENT_FOR_WEB')
ALLOWED_HOSTS = env.list(
    'ALLOWED_HOSTS'
)

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party apps
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist', #Pour black-lister les tokens de rafraîchissement deja utilisés
    'drf_spectacular',
    'drf_spectacular_sidecar',  # sert les assets Swagger/ReDoc localement (pas de CDN)

    # Local apps
    'network'
]
# permet de remplacer le modèle par défaut par le tien.
AUTH_USER_MODEL = "network.Utilisateur"

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    "corsheaders.middleware.CorsMiddleware",
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

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

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.1/ref/settings/#databases

DATABASES = {
    'default': env.db()
}


# Password validation
# https://docs.djangoproject.com/en/6.1/ref/settings/#auth-password-validators

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

# Config qui va permettre de gérer l'authentification par JWT (JSON Web Token) pour notre API Django REST Framework donc DRF vérifie automatiquement le JWT lorsqu'une requête arrive sur un endpoint protégé.
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'network.api.pagination.StandardResultsSetPagination',
    'PAGE_SIZE': 10,
    "DEFAULT_THROTTLE_RATES": {
        "auth_login": "5/minute",
        "auth_register": "3/hour",
        "auth_google": "10/minute",
    },
}

from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=10),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}

# Documentation de l'API (OpenAPI 3.1 via drf-spectacular)
# Schéma : /api/v1/schema/ — Swagger UI : /api/v1/schema/swagger-ui/ — ReDoc : /api/v1/schema/redoc/
# Régénérer le fichier commité : python manage.py spectacular --file schema.yml --validate
SPECTACULAR_SETTINGS = {
    'TITLE': 'NetForDebutant API',
    'DESCRIPTION': (
        "API du quiz réseau pédagogique NetForDebutant.\n\n"
        "## Consommer l'API depuis cette page (Swagger UI)\n\n"
        "**1. Se connecter** — `POST /api/v1/auth/login/` :\n"
        "- corps `{\"email\": \"...\", \"password\": \"...\"}`\n"
        "- ajoutez l'en-tête `X-Client-Type: mobile` (le plus simple ici : "
        "aucun CSRF, tokens renvoyés dans le corps)\n"
        "- copiez la valeur de `access` dans la réponse\n\n"
        "**2. S'authoriser** — bouton **Authorize** en haut à droite → "
        "collez le token (le préfixe `Bearer ` est ajouté automatiquement) → "
        "cliquez **Authorize** puis **Close**.\n\n"
        "**3. Consommer les endpoints protégés** — par ex. "
        "`GET /api/v1/categories/`, `GET /api/v1/questions/`, "
        "`POST /api/v1/tentatives/` : **Try it out** → **Execute** → 200. "
        "Sans le token : 401.\n\n"
        "### Flux web (sans `X-Client-Type`)\n\n"
        "1. `GET /api/v1/auth/csrf_token/` → renvoie `csrfToken` et pose le "
        "cookie CSRF\n"
        "2. `POST /api/v1/auth/login/` avec l'en-tête `X-CSRFToken: <valeur>`\n"
        "3. l'access token est dans le corps, le refresh token dans le cookie "
        "`refresh_token` (chemin `/api/v1/auth/`)\n"
        "4. `POST /api/v1/auth/refresh/` renouvelle l'access token\n\n"
        "### Limites de débit (throttle)\n\n"
        "- login : **5/min** — register : **3/h** — google_oauth : **10/min**\n"
        "- un 429 signifie trop de tentatives : attendez avant de réessayer\n\n"
        "Toutes les routes protégées attendent `Authorization: Bearer <access>`."
    ),
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SCHEMA_PATH_PREFIX': r'/api/v1',
    # Auth documentée automatiquement (extension simplejwt -> securityScheme "jwtAuth")
    # Assets servis localement par drf-spectacular-sidecar
    'SWAGGER_UI_DIST': 'SIDECAR',
    'SWAGGER_UI_FAVICON_HREF': 'SIDECAR',
    'REDOC_DIST': 'SIDECAR',
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        # Le token Authorize survit à un rechargement de la page
        'persistAuthorization': True,
        # Try it out envoie les cookies (nécessaire au flux CSRF web)
        'withCredentials': True,
    },
}

# Internationalization
# https://docs.djangoproject.com/en/6.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.1/howto/static-files/

STATIC_URL = 'static/'

# Fichiers médias (uploads ImageField : avatars, photos de notions)
MEDIA_URL = '/media/'
MEDIA_ROOT = str(BASE_DIR) + '/media'


# Email
# https://docs.djangoproject.com/en/6.1/topics/email/#topic-email-configuration

MAILERS = {
    'default': {
        'BACKEND': 'django.core.mail.backends.console.EmailBackend',
    },
}

CORS_ALLOWED_ORIGINS = [
    "https://netfordebutant.com",
    "http://localhost:5173",
]

CORS_ALLOW_CREDENTIALS = True #autorise les requêtes avec cookies.

CSRF_TRUSTED_ORIGINS = [
    "https://netfordebutant.com",
    "http://localhost:5173",
]

# Config de mon cookie
CSRF_COOKIE_SECURE = not DEBUG #Car nous sommes encore en local
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True