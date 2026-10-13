import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management.utils import get_random_secret_key

from config.settings.validation import validate_production_settings

BACKEND_DIR = Path(__file__).resolve().parent.parent
GOOD_KEY = get_random_secret_key()


def good_settings(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "secret_key": GOOD_KEY,
        "allowed_hosts": ["api.adyraforge.com"],
        "database_url": "postgres://u:p@db.example:5432/app",
        "debug": False,
        "admin_url": "forge-console-7f3a9c2e1b/",
        "cors_allowed_origins": ["https://adyraforge.com"],
        "csrf_trusted_origins": ["https://adyraforge.com"],
        "frontend_url": "https://adyraforge.com",
        "email_backend": "django.core.mail.backends.smtp.EmailBackend",
        "email_host": "smtp.example.com",
        "email_host_user": "mailer@example.com",
        "email_host_password": "placeholder-not-real",
        "email_use_tls": True,
        "email_use_ssl": False,
        "turnstile_secret": "0x4AAAAAAA" + "realistic-secret-value",
    }
    values.update(overrides)
    return values


def test_valid_production_settings_pass() -> None:
    validate_production_settings(**good_settings())


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"secret_key": ""}, "SECRET_KEY is missing"),
        ({"secret_key": "django-insecure-" + "x" * 60}, "default or placeholder"),
        ({"secret_key": "change-me-" + "a1b2c3d4e5" * 5}, "default or placeholder"),
        ({"secret_key": "tooshort" * 3}, "at least 50"),
        ({"secret_key": "ab" * 30}, "too few unique"),
        ({"allowed_hosts": []}, "ALLOWED_HOSTS is missing"),
        ({"allowed_hosts": ["*"]}, "wildcards"),
        ({"database_url": ""}, "DATABASE_URL is missing"),
        ({"database_url": "sqlite:///db.sqlite3"}, "PostgreSQL"),
        ({"debug": True}, "DEBUG must be False"),
        ({"admin_url": ""}, "ADMIN_URL is missing"),
        ({"admin_url": "admin/"}, "unguessable"),
        ({"admin_url": "short/"}, "unguessable"),
        ({"cors_allowed_origins": []}, "CORS_ALLOWED_ORIGINS is missing"),
        ({"cors_allowed_origins": ["http://adyraforge.com"]}, "https:// origins only"),
        ({"csrf_trusted_origins": ["https://*.adyraforge.com"]}, "https:// origins only"),
        ({"frontend_url": "http://adyraforge.com"}, "FRONTEND_URL"),
        ({"email_backend": "django.core.mail.backends.console.EmailBackend"}, "EMAIL_BACKEND"),
        ({"email_host": ""}, "EMAIL_HOST is missing"),
        ({"email_host_user": ""}, "EMAIL_HOST_USER is missing"),
        ({"email_host_password": ""}, "EMAIL_HOST_PASSWORD is missing"),
        ({"email_use_tls": False}, "never plaintext SMTP"),
        ({"email_use_ssl": True}, "never plaintext SMTP"),
        ({"turnstile_secret": ""}, "TURNSTILE_SECRET_KEY is missing"),
        ({"turnstile_secret": "1x0000000000" + "000000000000000000000AA"}, "Cloudflare test key"),
    ],
)
def test_insecure_production_settings_are_rejected(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(ImproperlyConfigured, match=message):
        validate_production_settings(**good_settings(**overrides))


def test_error_message_never_contains_the_secret() -> None:
    weak = "django-insecure-very-secret-value-" + "q" * 40
    with pytest.raises(ImproperlyConfigured) as exc:
        validate_production_settings(**good_settings(secret_key=weak))
    assert weak not in str(exc.value)


def _boot(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Import production settings in a clean interpreter, as a real deploy would."""
    clean_env = {k: v for k, v in os.environ.items() if k in {"PATH", "SYSTEMROOT", "HOME"}}
    clean_env.update(env)
    return subprocess.run(
        [sys.executable, "-c", "import django; django.setup()"],
        cwd=BACKEND_DIR,
        env={**clean_env, "DJANGO_SETTINGS_MODULE": "config.settings"},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


PROD_ENV = {
    "DJANGO_ENV": "production",
    "SECRET_KEY": GOOD_KEY,
    "ALLOWED_HOSTS": "api.adyraforge.com",
    "DATABASE_URL": "postgres://u:p@db.example:5432/app",
    "ADMIN_URL": "forge-console-7f3a9c2e1b/",
    "CORS_ALLOWED_ORIGINS": "https://adyraforge.com",
    "CSRF_TRUSTED_ORIGINS": "https://adyraforge.com",
    "FRONTEND_URL": "https://adyraforge.com",
    "EMAIL_HOST": "smtp.example.com",
    "EMAIL_HOST_USER": "mailer@example.com",
    "EMAIL_HOST_PASSWORD": "placeholder-not-real",
    "TURNSTILE_SECRET_KEY": "0x4AAAAAAA" + "realistic-secret-value",
}


def test_production_boots_with_valid_env() -> None:
    result = _boot(PROD_ENV)
    assert result.returncode == 0, result.stderr


def test_secret_key_starting_with_dollar_is_used_verbatim() -> None:
    # Regression: django-environ treats "$NAME" as a reference to another
    # variable; ~1 in 50 generated Django keys starts with "$".
    key = "$" + get_random_secret_key()[1:]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import django; django.setup(); from django.conf import settings;"
            "import os; print(settings.SECRET_KEY == os.environ['SECRET_KEY'])",
        ],
        cwd=BACKEND_DIR,
        env={
            **{k: v for k, v in os.environ.items() if k in {"PATH", "SYSTEMROOT", "HOME"}},
            **PROD_ENV,
            "SECRET_KEY": key,
            "DJANGO_SETTINGS_MODULE": "config.settings",
        },
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "True"


@pytest.mark.parametrize("missing", ["SECRET_KEY", "ALLOWED_HOSTS", "DATABASE_URL"])
def test_production_refuses_to_boot_without_required_env(missing: str) -> None:
    env = {k: v for k, v in PROD_ENV.items() if k != missing}
    result = _boot(env)
    assert result.returncode != 0
    assert "ImproperlyConfigured" in result.stderr
    assert missing in result.stderr


def test_unset_django_env_means_production() -> None:
    env = {k: v for k, v in PROD_ENV.items() if k not in {"DJANGO_ENV", "SECRET_KEY"}}
    result = _boot(env)
    assert result.returncode != 0
    assert "Refusing to start in production" in result.stderr
