"""
Django settings for IlèTô (core project).

Environment-driven configuration with django-environ, PostGIS, and GeoDjango.
"""

import os
from pathlib import Path

import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# -----------------------------------------------------------------------------
# Environment (.env at project root)
# -----------------------------------------------------------------------------
env = environ.Env(
    DEBUG=(bool, False),
)

environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

SECRET_KEY = env("SECRET_KEY", default="django-insecure-change-me-in-production")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# API geo : inclure les communes seed (is_placeholder=True). Par défaut = DEBUG (dev oui, prod non).
ILLETO_GEO_INCLUDE_PLACEHOLDER_COMMUNES = env.bool(
    "ILLETO_GEO_INCLUDE_PLACEHOLDER_COMMUNES",
    default=DEBUG,
)

# Atlas : surcouches Mapbox (trafic, fonds raster Mapbox). Laisser vide = replis OSM/Carto.
ILLETO_MAPBOX_ACCESS_TOKEN = env("ILLETO_MAPBOX_ACCESS_TOKEN", default="")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "illeto-default",
    }
}


# Application definition

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "apps.accounts",
    "django.contrib.auth",
    "django.contrib.admin",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
    "apps.geo_data",
    "apps.website",
]

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "apps.accounts.backends.EmailOrUsernameBackend",
    "django.contrib.auth.backends.ModelBackend",
]
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "/auth/dashboard/client/"
LOGOUT_REDIRECT_URL = "/"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"


# Database — PostGIS (GeoDjango)
# https://docs.djangoproject.com/en/stable/ref/contrib/gis/tutorial/#setting-up
# DATABASE_URL examples: postgis://user:pass@host:5432/dbname
# Engine is forced to PostGIS regardless of URL scheme (postgresql/postgis).

DATABASES = {
    "default": env.db_url(
        "DATABASE_URL",
        default="postgis://postgres:postgres@127.0.0.1:5432/ileto_db",
    )
}
DATABASES["default"]["ENGINE"] = "django.contrib.gis.db.backends.postgis"


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static & media files
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = "static/"
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

MEDIA_URL = "media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")


# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Catalogue boutique (prix & métadonnées — source unique dashboard + entreprise)
ILLETO_STORE_ITEMS = [
    {
        "slug": "routes-parakou",
        "department": "Borgou",
        "locality": "Parakou",
        "title": "Réseau routes (Parakou)",
        "layer_type": "Routes",
        "price_fcf": 12000,
        "formats": ["GeoJSON", "PDF", "PNG"],
    },
    {
        "slug": "elec-littoral",
        "department": "Littoral",
        "locality": "Cotonou",
        "title": "Réseau électricité (Littoral)",
        "layer_type": "Electricite",
        "price_fcf": 18000,
        "formats": ["GeoJSON", "PDF", "PNG"],
    },
    {
        "slug": "routes-atlantique",
        "department": "Atlantique",
        "locality": "Ouidah",
        "title": "Réseau routes (Atlantique)",
        "layer_type": "Routes",
        "price_fcf": 10500,
        "formats": ["GeoJSON", "PDF"],
    },
    {
        "slug": "eaux-oueme",
        "department": "Ouémé",
        "locality": "Porto-Novo",
        "title": "Zones hydrologiques (Ouémé)",
        "layer_type": "Eaux",
        "price_fcf": 14000,
        "formats": ["GeoJSON", "PDF", "PNG"],
    },
]

# Libellés limites d’export par type de compte (affichage boutique / facturation)
ILLETO_PLAN_EXPORT_LIMITS = {
    "STUDENT": "3 exports légers / mois (pas de Shapefile serveur)",
    "PROFESSIONAL": "Shapefile serveur + exports métier (fair use)",
    "INSTITUTION": "Volume conventionné multi-utilisateurs",
}


# Chemins vers les librairies système pour PostGIS/GDAL
GDAL_LIBRARY_PATH = '/usr/lib/x86_64-linux-gnu/libgdal.so'
GEOS_LIBRARY_PATH = '/usr/lib/x86_64-linux-gnu/libgeos_c.so'