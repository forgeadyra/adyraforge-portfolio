"""pytest settings (DJANGO_ENV=test). Production-like; still needs real PostgreSQL."""

import os
import tempfile

from django.core.management.utils import get_random_secret_key

# A fresh random key per run; nothing is hard-coded.
os.environ.setdefault("SECRET_KEY", get_random_secret_key())

from .base import *  # noqa: F403

ALLOWED_HOSTS = ["testserver", "localhost"]
ADMIN_URL = "test-admin-path-0123456789/"
CORS_ALLOWED_ORIGINS = ["https://adyraforge.test"]
CSRF_TRUSTED_ORIGINS = ["https://adyraforge.test"]

# The test client speaks HTTP; the redirect itself is covered by a dedicated test.
SECURE_SSL_REDIRECT = False

# Uploads in tests go to throwaway directories.
MEDIA_ROOT = tempfile.mkdtemp(prefix="af-media-")
PRIVATE_MEDIA_ROOT = tempfile.mkdtemp(prefix="af-private-")

FRONTEND_URL = "https://adyraforge.test"
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
EMAIL_SEND_ASYNC = False
TURNSTILE_SECRET_KEY = "test-secret-verification-is-mocked"  # noqa: S105

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
