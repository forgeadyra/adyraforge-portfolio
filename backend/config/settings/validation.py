"""Fail-closed validation for production settings (CLAUDE.md rule 2).

Kept free of Django settings imports so it can be unit-tested directly.
Error messages name the setting, never its value.
"""

from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured

_PLACEHOLDER_MARKERS = ("django-insecure", "change-me", "changeme", "placeholder", "example")
_GUESSABLE_ADMIN_PATHS = {
    "admin",
    "django-admin",
    "administrator",
    "manage",
    "backend",
    "dashboard",
}
_POSTGRES_SCHEMES = {"postgres", "postgresql", "pgsql", "postgis"}
MIN_SECRET_KEY_LENGTH = 50
MIN_SECRET_KEY_UNIQUE_CHARS = 5
MIN_ADMIN_URL_LENGTH = 16
_DEV_EMAIL_BACKENDS = ("console", "locmem", "dummy", "filebased")
# Cloudflare's published always-pass / always-fail / spent test secrets.
_TURNSTILE_TEST_PREFIXES = ("1x0000000000", "2x0000000000", "3x0000000000")


def secret_key_problem(secret_key: str) -> str | None:
    if not secret_key:
        return "SECRET_KEY is missing."
    lowered = secret_key.lower()
    if any(marker in lowered for marker in _PLACEHOLDER_MARKERS):
        return "SECRET_KEY is a default or placeholder value."
    if len(secret_key) < MIN_SECRET_KEY_LENGTH:
        return f"SECRET_KEY must be at least {MIN_SECRET_KEY_LENGTH} characters."
    if len(set(secret_key)) < MIN_SECRET_KEY_UNIQUE_CHARS:
        return "SECRET_KEY has too few unique characters."
    return None


def validate_production_settings(
    *,
    secret_key: str,
    allowed_hosts: list[str],
    database_url: str,
    debug: bool,
    admin_url: str,
    cors_allowed_origins: list[str],
    csrf_trusted_origins: list[str],
    frontend_url: str,
    email_backend: str,
    turnstile_secret: str,
) -> None:
    """Raise ImproperlyConfigured listing every problem found."""
    errors: list[str] = []

    if problem := secret_key_problem(secret_key):
        errors.append(problem)

    hosts = [h.strip() for h in allowed_hosts if h.strip()]
    if not hosts:
        errors.append("ALLOWED_HOSTS is missing.")
    elif any(h in {"*", "."} for h in hosts):
        errors.append("ALLOWED_HOSTS must not contain wildcards.")

    if not database_url:
        errors.append("DATABASE_URL is missing.")
    elif urlparse(database_url).scheme not in _POSTGRES_SCHEMES:
        errors.append("DATABASE_URL must be a PostgreSQL URL.")

    if debug:
        errors.append("DEBUG must be False in production.")

    admin_path = admin_url.strip("/")
    if not admin_path:
        errors.append("ADMIN_URL is missing.")
    elif admin_path.lower() in _GUESSABLE_ADMIN_PATHS or len(admin_path) < MIN_ADMIN_URL_LENGTH:
        errors.append(f"ADMIN_URL must be an unguessable path of {MIN_ADMIN_URL_LENGTH}+ chars.")

    for name, origins in (
        ("CORS_ALLOWED_ORIGINS", cors_allowed_origins),
        ("CSRF_TRUSTED_ORIGINS", csrf_trusted_origins),
    ):
        if not origins:
            errors.append(f"{name} is missing.")
        elif any(not o.startswith("https://") or "*" in o for o in origins):
            errors.append(f"{name} must list explicit https:// origins only.")

    if not frontend_url.startswith("https://"):
        errors.append("FRONTEND_URL must be an https:// URL (used in emailed links).")

    if any(dev in email_backend for dev in _DEV_EMAIL_BACKENDS):
        errors.append("EMAIL_URL must point at a real mail server (invites, password reset).")

    if not turnstile_secret:
        errors.append("TURNSTILE_SECRET_KEY is missing.")
    elif turnstile_secret.startswith(_TURNSTILE_TEST_PREFIXES):
        errors.append("TURNSTILE_SECRET_KEY is a Cloudflare test key.")

    if errors:
        raise ImproperlyConfigured("Refusing to start in production:\n- " + "\n- ".join(errors))
