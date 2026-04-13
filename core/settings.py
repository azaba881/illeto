"""
Django settings for IlèTô (core project).

Environment-driven configuration with django-environ, PostGIS, and GeoDjango.
"""

import os
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import dj_database_url
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
# Ex. https://ton-service.onrender.com (requis pour le POST / login en HTTPS)
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# API geo : inclure les communes seed (is_placeholder=True). Par défaut = DEBUG (dev oui, prod non).
ILLETO_GEO_INCLUDE_PLACEHOLDER_COMMUNES = env.bool(
    "ILLETO_GEO_INCLUDE_PLACEHOLDER_COMMUNES",
    default=DEBUG,
)

# Atlas : surcouches Mapbox (trafic, fonds raster Mapbox). Laisser vide = replis OSM/Carto.
ILLETO_MAPBOX_ACCESS_TOKEN = env("ILLETO_MAPBOX_ACCESS_TOKEN", default="")

# Export Atlas headless (Playwright). False par défaut — activer en prod après `playwright install chromium`.
ILLETO_PLAYWRIGHT_EXPORT_ENABLED = env.bool(
    "ILLETO_PLAYWRIGHT_EXPORT_ENABLED", default=False
)
ILLETO_ATLAS_EXPORT_CACHE_DIR = env(
    "ILLETO_ATLAS_EXPORT_CACHE_DIR", default="var/atlas_export_cache"
)
ILLETO_ATLAS_EXPORT_CACHE_TTL = env.int(
    "ILLETO_ATLAS_EXPORT_CACHE_TTL", default=86400
)
ILLETO_EXPORT_MAX_CONCURRENT = env.int("ILLETO_EXPORT_MAX_CONCURRENT", default=2)
ILLETO_ATLAS_EXPORT_MAX_CLIP = env.int("ILLETO_ATLAS_EXPORT_MAX_CLIP", default=2400)
ILLETO_ATLAS_EXPORT_DEVICE_SCALE = env.float(
    "ILLETO_ATLAS_EXPORT_DEVICE_SCALE", default=2.0
)
ILLETO_ATLAS_EXPORT_TIMEOUT_MS = env.int(
    "ILLETO_ATLAS_EXPORT_TIMEOUT_MS", default=120000
)
ILLETO_ATLAS_EXPORT_POST_IDLE_MS = env.int(
    "ILLETO_ATLAS_EXPORT_POST_IDLE_MS", default=800
)
# Badge PDF (JPG) — placer le fichier sous static/img/ ou renseigner un chemin absolu.
ILLETO_ATLAS_PDF_BADGE_PATH = env(
    "ILLETO_ATLAS_PDF_BADGE_PATH",
    default=str(
        BASE_DIR / "static" / "img" / "Filigrane Badge-Transparent.jpg"
    ),
)

# Imports géographiques (chemins relatifs au BASE_DIR ; laisser vide = pas de défaut)
ILLETO_HDX_ADM1_PATH = env("ILLETO_HDX_ADM1_PATH", default="")
ILLETO_HDX_ADM2_PATH = env("ILLETO_HDX_ADM2_PATH", default="")
ILLETO_HDX_ADM3_PATH = env("ILLETO_HDX_ADM3_PATH", default="")
ILLETO_OVERPASS_API_URL = env(
    "ILLETO_OVERPASS_API_URL",
    default="https://overpass-api.de/api/interpreter",
)
ILLETO_OSM_DISTRICTS_PATH = env("ILLETO_OSM_DISTRICTS_PATH", default="")
ILLETO_POI_GEOJSON_PATH = env("ILLETO_POI_GEOJSON_PATH", default="")
ILLETO_HYDRO_GEOJSON_PATH = env("ILLETO_HYDRO_GEOJSON_PATH", default="")
ILLETO_VECTOR_IMPORT_DEFAULT_PATH = env("ILLETO_VECTOR_IMPORT_DEFAULT_PATH", default="")

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
    "whitenoise.middleware.WhiteNoiseMiddleware",
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
# Vérifie si on est sur Render ou en local

IS_HEROKU_OR_RENDER = "DATABASE_URL" in os.environ

# DATABASES = {
#     'default': dj_database_url.config(
#         # Utilise l'URL de Render si elle existe, sinon ton PostGIS local
#         default=os.environ.get('DATABASE_URL', 'postgis://postgres:postgres@127.0.0.1:5432/ileto_db'),
#         conn_max_age=600,
#         # N'exige le SSL QUE sur le cloud (Render/Heroku/etc.)
#         ssl_require=IS_HEROKU_OR_RENDER
#     )
# }

# 1. On définit la config locale (celle qui marche sur ton PC)
DATABASE_LOCAL = {
    'ENGINE': 'django.contrib.gis.db.backends.postgis',
    'NAME': 'illeto_db',
    'USER': 'root',
    'PASSWORD': 'motdepasse',
    'HOST': '127.0.0.1',
    'PORT': '5432',
}

# 2. On regarde si une URL de base de données est fournie (.env / Render)
DATABASE_URL = os.environ.get("DATABASE_URL")


def _is_local_postgres_url(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
        return host in ("localhost", "127.0.0.1", "::1")
    except Exception:
        return False


def _strip_sslmode_from_database_url(url: str) -> str:
    """Évite ?sslmode=require copié depuis Render alors que le host est local."""
    p = urlparse(url)
    q = [
        (k, v)
        for k, v in parse_qsl(p.query, keep_blank_values=True)
        if k.lower() != "sslmode"
    ]
    return urlunparse(
        (p.scheme, p.netloc, p.path, p.params, urlencode(q), p.fragment)
    )


def _postgres_url_requires_ssl(url: str) -> bool:
    """SSL pour hôtes distants uniquement (Render, etc.)."""
    if _is_local_postgres_url(url):
        return False
    if "ILLETO_DATABASE_SSL_REQUIRE" in os.environ:
        return env.bool("ILLETO_DATABASE_SSL_REQUIRE", default=True)
    return True


if DATABASE_URL:
    _db_url = (
        _strip_sslmode_from_database_url(DATABASE_URL)
        if _is_local_postgres_url(DATABASE_URL)
        else DATABASE_URL
    )
    DATABASES = {
        "default": dj_database_url.config(
            default=_db_url,
            conn_max_age=600,
            ssl_require=_postgres_url_requires_ssl(DATABASE_URL),
        )
    }
    DATABASES["default"]["ENGINE"] = "django.contrib.gis.db.backends.postgis"
    if _is_local_postgres_url(DATABASE_URL):
        _opts = DATABASES["default"].get("OPTIONS")
        if isinstance(_opts, dict):
            _opts.pop("sslmode", None)
else:
    # SI NON : On est sur ton PC, on utilise la config locale
    DATABASES = {
        'default': DATABASE_LOCAL
    }

# Garde bien cette ligne pour le moteur GIS
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
if not DEBUG:
    STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"

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


# PostGIS/GDAL (surcharge .env sur Docker / autres distro si besoin)
GDAL_LIBRARY_PATH = env(
    "GDAL_LIBRARY_PATH", default="/usr/lib/x86_64-linux-gnu/libgdal.so"
)
GEOS_LIBRARY_PATH = env(
    "GEOS_LIBRARY_PATH", default="/usr/lib/x86_64-linux-gnu/libgeos_c.so"
)