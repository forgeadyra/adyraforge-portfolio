"""Local development over plain HTTP. Only active when DJANGO_ENV=development."""

from .base import *  # noqa: F403
from .base import ADMIN_URL, ALLOWED_HOSTS, REST_FRAMEWORK, SECRET_KEY
from .validation import secret_key_problem

DEBUG = True

if problem := secret_key_problem(SECRET_KEY):
    # Even locally, a real random key is required (see backend/.env.example).
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured(problem)

ALLOWED_HOSTS = ALLOWED_HOSTS or ["localhost", "127.0.0.1"]
ADMIN_URL = ADMIN_URL or "admin/"

# Emails print to the backend log in development; never sent.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# localhost is plain HTTP: no HTTPS redirect, no Secure-only cookies, no HSTS.
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}
