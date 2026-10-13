from .base import *  # noqa: F403
from .base import (
    ADMIN_URL,
    ALLOWED_HOSTS,
    CORS_ALLOWED_ORIGINS,
    CSRF_TRUSTED_ORIGINS,
    DATABASE_URL,
    EMAIL_BACKEND,
    EMAIL_HOST,
    EMAIL_HOST_PASSWORD,
    EMAIL_HOST_USER,
    EMAIL_USE_SSL,
    EMAIL_USE_TLS,
    FRONTEND_URL,
    SECRET_KEY,
    TURNSTILE_SECRET_KEY,
)
from .validation import validate_production_settings

DEBUG = False

# Render/Railway terminate TLS and set X-Forwarded-Proto; they strip any
# client-supplied copy, so it is safe to trust here and only here.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

validate_production_settings(
    secret_key=SECRET_KEY,
    allowed_hosts=ALLOWED_HOSTS,
    database_url=DATABASE_URL,
    debug=DEBUG,
    admin_url=ADMIN_URL,
    cors_allowed_origins=CORS_ALLOWED_ORIGINS,
    csrf_trusted_origins=CSRF_TRUSTED_ORIGINS,
    frontend_url=FRONTEND_URL,
    email_backend=EMAIL_BACKEND,
    email_host=EMAIL_HOST,
    email_host_user=EMAIL_HOST_USER,
    email_host_password=EMAIL_HOST_PASSWORD,
    email_use_tls=EMAIL_USE_TLS,
    email_use_ssl=EMAIL_USE_SSL,
    turnstile_secret=TURNSTILE_SECRET_KEY,
)
