"""Fail-closed validation for production settings (CLAUDE.md rule 2).

Kept free of Django settings imports so it can be unit-tested directly.
Error messages name the setting, never its value.
"""

from urllib.parse import parse_qs, urlparse

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
MAX_TRUSTED_PROXY_COUNT = 5
_SSL_MODES = {"require", "verify-ca", "verify-full"}
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
    email_host: str,
    email_host_user: str,
    email_host_password: str,
    email_use_tls: bool,
    email_use_ssl: bool,
    turnstile_secret: str,
    trusted_proxy_count: str,
    private_bucket: str,
    media_bucket: str,
    media_url: str,
    storage_access_key_id: str,
    storage_secret_access_key: str,
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
    elif not set(parse_qs(urlparse(database_url).query).get("sslmode", [])) & _SSL_MODES:
        errors.append("DATABASE_URL must set sslmode=require (or verify-ca / verify-full).")

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
        errors.append("EMAIL_BACKEND must be SMTP in production (invites, password reset).")
    for name, value in (
        ("EMAIL_HOST", email_host),
        ("EMAIL_HOST_USER", email_host_user),
        ("EMAIL_HOST_PASSWORD", email_host_password),
    ):
        if not value:
            errors.append(f"{name} is missing.")
    if email_use_tls == email_use_ssl:
        errors.append("Set exactly one of EMAIL_USE_TLS / EMAIL_USE_SSL (never plaintext SMTP).")

    if not turnstile_secret:
        errors.append("TURNSTILE_SECRET_KEY is missing.")
    elif turnstile_secret.startswith(_TURNSTILE_TEST_PREFIXES):
        errors.append("TURNSTILE_SECRET_KEY is a Cloudflare test key.")

    if not trusted_proxy_count.isdigit() or int(trusted_proxy_count) > MAX_TRUSTED_PROXY_COUNT:
        errors.append(
            f"TRUSTED_PROXY_COUNT must be set explicitly (0-{MAX_TRUSTED_PROXY_COUNT}); "
            "Render is 1."
        )

    for name, value in (
        ("PRIVATE_BUCKET", private_bucket),
        ("MEDIA_BUCKET", media_bucket),
        ("STORAGE_ACCESS_KEY_ID", storage_access_key_id),
        ("STORAGE_SECRET_ACCESS_KEY", storage_secret_access_key),
    ):
        if not value:
            errors.append(f"{name} is missing (uploads must not live on the container disk).")
    if private_bucket and private_bucket == media_bucket:
        errors.append("PRIVATE_BUCKET must differ from the public MEDIA_BUCKET.")
    if not media_url.startswith("https://"):
        errors.append("MEDIA_URL must be the https:// public origin of MEDIA_BUCKET.")

    if errors:
        raise ImproperlyConfigured("Refusing to start in production:\n- " + "\n- ".join(errors))
