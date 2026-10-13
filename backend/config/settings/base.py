"""Base settings shared by every environment.

Everything here is production-safe by default (DEBUG off, secure cookies, HTTPS
redirect, strict headers). ``development`` relaxes only what plain-HTTP localhost
needs; ``production`` adds fail-closed validation. All secrets and hosts come
from the environment (CLAUDE.md rules 1, 2, 11, 12).
"""

import os
from datetime import timedelta
from pathlib import Path

import environ
from csp.constants import NONE, SELF
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Settings read only the process environment. A local backend/.env is loaded by
# manage.py for convenience; the WSGI/ASGI entry points used in production never
# read files, so a stray .env on a server cannot change production config.
env = environ.Env()

DJANGO_ENV = env("DJANGO_ENV", default="production").strip().lower()

# --- Core ---------------------------------------------------------------------
DEBUG = False
# Read raw: django-environ treats values starting with "$" as a reference to
# another variable, and Django's key alphabet includes "$".
SECRET_KEY = os.environ.get("SECRET_KEY", "")
ALLOWED_HOSTS: list[str] = env.list("ALLOWED_HOSTS", default=[])
ADMIN_URL = env("ADMIN_URL", default="")

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
AUTH_USER_MODEL = "accounts.User"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third party
    "rest_framework",
    "corsheaders",
    "csp",
    "axes",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "django_otp.plugins.otp_static",
    # local
    "apps.core",
    "apps.accounts",
    "apps.portfolio",
    "apps.leads",
    "apps.clients",
    "apps.recommender",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "csp.middleware.CSPMiddleware",
    "apps.core.middleware.PermissionsPolicyMiddleware",
    # Must be last so it sees the final authentication outcome.
    "axes.middleware.AxesMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

# --- Database (PostgreSQL only; SQLite is forbidden in every environment) -----
DATABASE_URL = env("DATABASE_URL", default="")
if not DATABASE_URL:
    raise ImproperlyConfigured("DATABASE_URL is required (PostgreSQL).")
DATABASES = {"default": env.db_url_config(DATABASE_URL)}
if DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
    raise ImproperlyConfigured("DATABASE_URL must point at PostgreSQL.")
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

# Throttle counters must be shared across workers, so the default is the DB cache
# (run `manage.py createcachetable`). Override with CACHE_URL if Redis is added.
CACHES = {"default": env.cache("CACHE_URL", default="dbcache://django_cache")}

# --- Auth & passwords ---------------------------------------------------------
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# django-axes: lock a username+IP pair after repeated failures.
AXES_FAILURE_LIMIT = env.int("AXES_FAILURE_LIMIT", default=5)
AXES_COOLOFF_TIME = timedelta(minutes=30)
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True
# Django's authenticate() and the admin form both use "username" (axes would
# default to USERNAME_FIELD, "email", and silently key lockouts on nothing).
AXES_USERNAME_FORM_FIELD = "username"
AXES_USERNAME_CALLABLE = "apps.accounts.axes.lockout_username"
# Our own 429 JSON: axes' default sets Access-Control-Allow-Origin "*".
AXES_LOCKOUT_CALLABLE = "apps.accounts.lockout.lockout_response"
AXES_SENSITIVE_PARAMETERS = ["password", "otp_token"]

# --- Sessions, CSRF, cookies (rule 4) -----------------------------------------
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_DOMAIN = env("SESSION_COOKIE_DOMAIN", default=None)
# Absolute 2-week lifetime from login (not extended by activity).
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
SESSION_SAVE_EVERY_REQUEST = False

# Password reset links: 1 hour, single-use (Django's token generator).
PASSWORD_RESET_TIMEOUT = 60 * 60
# Client invite links: 72 hours, single-use (apps.accounts.tokens).
INVITE_MAX_AGE = 60 * 60 * 72
# Signed private-file download links.
DOWNLOAD_URL_MAX_AGE = 60 * 5

# The frontend gets the CSRF token from /api/auth/csrf/ (JSON body), never by
# reading the cookie, so the cookie can stay HttpOnly.
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_DOMAIN = env("CSRF_COOKIE_DOMAIN", default=None)
CSRF_TRUSTED_ORIGINS: list[str] = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# --- CORS (rule 12): explicit allowlist only -----------------------------------
CORS_ALLOWED_ORIGINS: list[str] = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = False

# --- Security headers (rule 11) -----------------------------------------------
SECURE_SSL_REDIRECT = True
SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# The API serves JSON; the only HTML is the Django admin, which needs nothing
# beyond its own static files.
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": [NONE],
        "script-src": [SELF],
        "style-src": [SELF],
        "img-src": [SELF, "data:"],
        "font-src": [SELF],
        "connect-src": [SELF],
        "form-action": [SELF],
        "base-uri": [NONE],
        "frame-ancestors": [NONE],
        "object-src": [NONE],
    },
}

PERMISSIONS_POLICY = (
    "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), "
    "microphone=(), payment=(), usb=(), interest-cohort=()"
)

# --- DRF (rules 5, 8) ---------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": env("THROTTLE_ANON", default="60/min"),
        "user": env("THROTTLE_USER", default="240/min"),
        # Stricter scopes for sensitive public actions.
        "login": env("THROTTLE_LOGIN", default="5/min"),
        "password_reset": env("THROTTLE_PASSWORD_RESET", default="3/hour"),
        "password_reset_confirm": env("THROTTLE_PASSWORD_RESET_CONFIRM", default="10/hour"),
        "password_change": env("THROTTLE_PASSWORD_CHANGE", default="5/hour"),
        "invite_accept": env("THROTTLE_INVITE_ACCEPT", default="10/hour"),
        "contact": env("THROTTLE_CONTACT", default="5/hour"),
        "planner": env("THROTTLE_PLANNER", default="10/hour"),
        # Public read-only content (the Next server revalidates from one IP).
        "public": env("THROTTLE_PUBLIC", default="300/min"),
    },
}

# --- Email, links, bot protection --------------------------------------------
# Frontend origin used in emailed links (invite, password reset).
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:3000").rstrip("/")
# EMAIL_URL e.g. smtp+tls://user:pass@smtp.example.com:587 (console in dev).
EMAIL_URL = env("EMAIL_URL", default="consolemail://")
vars().update(env.email_url_config(EMAIL_URL))
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="AdyraForge <noreply@adyraforge.com>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL
# Send auth emails off the request thread so timing can't reveal account existence.
EMAIL_SEND_ASYNC = env.bool("EMAIL_SEND_ASYNC", default=True)
# Read raw (may start with "$"). Cloudflare's public test keys work in development.
TURNSTILE_SECRET_KEY = os.environ.get("TURNSTILE_SECRET_KEY", "")

# --- i18n / static ------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# Public media (project covers, gallery). Production: Cloudinary.
# Absolute in deployed setups (Cloudinary/S3, or http://localhost:8000/media/ in dev),
# because the browser and the Next server both consume these URLs.
MEDIA_URL = env("MEDIA_URL", default="/media/")
MEDIA_ROOT = env.path("MEDIA_ROOT", default=str(BASE_DIR / "media"))
# Client files and invoices: never under MEDIA_ROOT, never given a public URL.
PRIVATE_MEDIA_ROOT = env.path("PRIVATE_MEDIA_ROOT", default=str(BASE_DIR / "private_media"))

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# --- Logging (rule 14): no request bodies, cookies or credentials -------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
    "loggers": {
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}
