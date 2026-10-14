import os

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
    MEDIA_URL,
    PRIVATE_URL_EXPIRE,
    SECRET_KEY,
    TRUSTED_PROXY_COUNT_RAW,
    TURNSTILE_SECRET_KEY,
)
from .validation import validate_production_settings

DEBUG = False

# Render/Railway terminate TLS and set X-Forwarded-Proto; they strip any
# client-supplied copy, so it is safe to trust here and only here.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Uploads live in S3-compatible buckets (Cloudflare R2 or AWS S3), never on the
# container disk, which Render wipes on every deploy. Credentials are read raw (a
# leading "$" would otherwise be treated as an env reference by django-environ).
STORAGE_ACCESS_KEY_ID = os.environ.get("STORAGE_ACCESS_KEY_ID", "")
STORAGE_SECRET_ACCESS_KEY = os.environ.get("STORAGE_SECRET_ACCESS_KEY", "")
PRIVATE_BUCKET = os.environ.get("PRIVATE_BUCKET", "")
MEDIA_BUCKET = os.environ.get("MEDIA_BUCKET", "")
_S3_COMMON = {
    "access_key": STORAGE_ACCESS_KEY_ID,
    "secret_key": STORAGE_SECRET_ACCESS_KEY,
    "endpoint_url": os.environ.get("STORAGE_ENDPOINT_URL") or None,  # R2; empty for AWS
    "region_name": os.environ.get("STORAGE_REGION") or None,  # "auto" for R2
    "signature_version": "s3v4",
    "file_overwrite": False,  # names are UUIDs anyway; never replace an object
}
STORAGES = {
    # Public media (re-encoded images): served from the bucket's public custom domain.
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            **_S3_COMMON,
            "bucket_name": MEDIA_BUCKET,
            "querystring_auth": False,
            "custom_domain": MEDIA_URL.split("://", 1)[-1].rstrip("/"),
        },
    },
    # Client files and invoices: a PRIVATE bucket. No public URL exists; the signed
    # download view redirects to a presigned URL valid for PRIVATE_URL_EXPIRE seconds.
    "private": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            **_S3_COMMON,
            "bucket_name": PRIVATE_BUCKET,
            "default_acl": "private",
            "querystring_auth": True,
            "querystring_expire": PRIVATE_URL_EXPIRE,
            "custom_domain": None,
        },
    },
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
    trusted_proxy_count=TRUSTED_PROXY_COUNT_RAW,
    private_bucket=PRIVATE_BUCKET,
    media_bucket=MEDIA_BUCKET,
    media_url=MEDIA_URL,
    storage_access_key_id=STORAGE_ACCESS_KEY_ID,
    storage_secret_access_key=STORAGE_SECRET_ACCESS_KEY,
)

# Error monitoring (off unless SENTRY_DSN is set; scrubbed, see apps/core/monitoring.py).
# Imported here, not at the top, so a missing package can never mask a config error above.
from apps.core.monitoring import init_sentry  # noqa: E402

init_sentry(
    os.environ.get("SENTRY_DSN", ""),
    environment="production",
    release=os.environ.get("RENDER_GIT_COMMIT", ""),
)
