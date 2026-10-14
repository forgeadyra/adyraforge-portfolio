"""Management commands only (DJANGO_ENV=maintenance): migrate, createcachetable,
clearsessions from GitHub Actions.

Render's free instance has no pre-deploy command or cron, so these run in CI with
just a database URL (and a throwaway SECRET_KEY); none of the web app's secrets are
needed or present. This module can never serve the site: it allows no hosts and
routes no URLs, so DJANGO_ENV=maintenance set by mistake on a server answers 400 to
everything instead of running without production's validation.
"""

from .base import *  # noqa: F403
from .base import DATABASE_URL, SECRET_KEY
from .validation import database_url_problem, secret_key_problem

DEBUG = False
ALLOWED_HOSTS: list[str] = []
ROOT_URLCONF = "config.urls_maintenance"
EMAIL_BACKEND = "django.core.mail.backends.dummy.EmailBackend"

_problems = [p for p in (secret_key_problem(SECRET_KEY), database_url_problem(DATABASE_URL)) if p]
if _problems:
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured("Refusing to run maintenance:\n- " + "\n- ".join(_problems))
