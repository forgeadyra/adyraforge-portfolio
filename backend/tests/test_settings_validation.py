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
        "allowed_hosts": ["adyraforge-api.onrender.com"],
        "database_url": "postgres://u:p@db.example:5432/app?sslmode=require",
        "debug": False,
        "admin_url": "forge-console-7f3a9c2e1b/",
        "cors_allowed_origins": ["https://adyraforge.netlify.app"],
        "csrf_trusted_origins": ["https://adyraforge.netlify.app"],
        "frontend_url": "https://adyraforge.netlify.app",
        "email_backend": "django.core.mail.backends.smtp.EmailBackend",
        "email_host": "smtp.example.com",
        "email_host_user": "mailer@example.com",
        "email_host_password": "placeholder-not-real",
        "email_use_tls": True,
        "email_use_ssl": False,
        "turnstile_secret": "0x4AAAAAAA" + "realistic-secret-value",
        "trusted_proxy_count": "1",
        "private_bucket": "adyraforge-private",
        "media_bucket": "adyraforge-media",
        "media_url": "https://adyraforge-media.s3.us-west-004.backblazeb2.com/",
        "storage_access_key_id": "placeholder-key-id",
        "storage_secret_access_key": "placeholder-not-real",
        "netlify_proxy_signing_secret": "x" * 16 + "placeholder-not-a-real-secret",
        "default_from_email": "AdyraForge <sender@example.test>",
        "lead_notify_email": "leads@example.test",
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
        ({"database_url": "postgres://u:p@db.example:5432/app"}, "sslmode=require"),
        ({"database_url": "postgres://u:p@db.example/app?sslmode=prefer"}, "sslmode=require"),
        ({"database_url": "postgres://u:p@db.example/app?sslmode=disable"}, "sslmode=require"),
        ({"debug": True}, "DEBUG must be False"),
        ({"admin_url": ""}, "ADMIN_URL is missing"),
        ({"admin_url": "admin/"}, "unguessable"),
        ({"admin_url": "short/"}, "unguessable"),
        ({"cors_allowed_origins": []}, "CORS_ALLOWED_ORIGINS is missing"),
        ({"cors_allowed_origins": ["http://adyraforge.netlify.app"]}, "https:// origins only"),
        ({"csrf_trusted_origins": ["https://*.netlify.app"]}, "https:// origins only"),
        ({"frontend_url": "http://adyraforge.netlify.app"}, "FRONTEND_URL"),
        ({"email_backend": "django.core.mail.backends.console.EmailBackend"}, "EMAIL_BACKEND"),
        ({"email_host": ""}, "EMAIL_HOST is missing"),
        ({"email_host_user": ""}, "EMAIL_HOST_USER is missing"),
        ({"email_host_password": ""}, "EMAIL_HOST_PASSWORD is missing"),
        ({"email_use_tls": False}, "never plaintext SMTP"),
        ({"email_use_ssl": True}, "never plaintext SMTP"),
        ({"turnstile_secret": ""}, "TURNSTILE_SECRET_KEY is missing"),
        ({"turnstile_secret": "1x0000000000" + "000000000000000000000AA"}, "Cloudflare test key"),
        ({"trusted_proxy_count": ""}, "TRUSTED_PROXY_COUNT must be set"),
        ({"trusted_proxy_count": "-1"}, "TRUSTED_PROXY_COUNT must be set"),
        ({"trusted_proxy_count": "one"}, "TRUSTED_PROXY_COUNT must be set"),
        ({"trusted_proxy_count": "9"}, "TRUSTED_PROXY_COUNT must be set"),
        ({"private_bucket": ""}, "PRIVATE_BUCKET is missing"),
        ({"media_bucket": ""}, "MEDIA_BUCKET is missing"),
        ({"storage_access_key_id": ""}, "STORAGE_ACCESS_KEY_ID is missing"),
        ({"storage_secret_access_key": ""}, "STORAGE_SECRET_ACCESS_KEY is missing"),
        ({"media_bucket": "adyraforge-private"}, "must differ"),
        (
            {"media_url": "http://adyraforge-media.s3.us-west-004.backblazeb2.com/"},
            "MEDIA_URL must be",
        ),
        ({"media_url": "/media/"}, "MEDIA_URL must be"),
        ({"netlify_proxy_signing_secret": ""}, "NETLIFY_PROXY_SIGNING_SECRET must be set"),
        ({"netlify_proxy_signing_secret": "short"}, "NETLIFY_PROXY_SIGNING_SECRET must be set"),
        ({"default_from_email": ""}, "DEFAULT_FROM_EMAIL is missing"),
        ({"lead_notify_email": ""}, "LEAD_NOTIFY_EMAIL is missing"),
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
    "ALLOWED_HOSTS": "adyraforge-api.onrender.com",
    "DATABASE_URL": "postgres://u:p@db.example:5432/app?sslmode=require",
    "ADMIN_URL": "forge-console-7f3a9c2e1b/",
    "CORS_ALLOWED_ORIGINS": "https://adyraforge.netlify.app",
    "CSRF_TRUSTED_ORIGINS": "https://adyraforge.netlify.app",
    "FRONTEND_URL": "https://adyraforge.netlify.app",
    "EMAIL_HOST": "smtp.example.com",
    "EMAIL_HOST_USER": "mailer@example.com",
    "EMAIL_HOST_PASSWORD": "placeholder-not-real",
    "TURNSTILE_SECRET_KEY": "0x4AAAAAAA" + "realistic-secret-value",
    "TRUSTED_PROXY_COUNT": "1",
    "PRIVATE_BUCKET": "adyraforge-private",
    "MEDIA_BUCKET": "adyraforge-media",
    "MEDIA_URL": "https://adyraforge-media.s3.us-west-004.backblazeb2.com/",
    "STORAGE_ACCESS_KEY_ID": "placeholder-key-id",
    "STORAGE_SECRET_ACCESS_KEY": "placeholder-not-real",
    "STORAGE_ENDPOINT_URL": "https://s3.us-west-004.backblazeb2.com",
    "STORAGE_REGION": "us-west-004",
    "NETLIFY_PROXY_SIGNING_SECRET": "x" * 16 + "placeholder-not-a-real-secret",
    "DEFAULT_FROM_EMAIL": "AdyraForge <sender@example.test>",
    "LEAD_NOTIFY_EMAIL": "leads@example.test",
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


@pytest.mark.parametrize(
    "missing",
    ["SECRET_KEY", "ALLOWED_HOSTS", "DATABASE_URL", "TRUSTED_PROXY_COUNT", "PRIVATE_BUCKET"],
)
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


def test_production_uploads_go_to_buckets_never_the_container_disk() -> None:
    result = subprocess.run(
        [sys.executable, "-c",
         "import django; django.setup(); from django.conf import settings as s;"
         "print(s.STORAGES['private']['BACKEND'], s.STORAGES['default']['BACKEND'],"
         " s.STORAGES['private']['OPTIONS']['querystring_auth'],"
         " s.STORAGES['default']['OPTIONS']['querystring_auth'],"
         " s.STORAGES['private']['OPTIONS']['bucket_name'])"],
        cwd=BACKEND_DIR,
        env={**{k: v for k, v in os.environ.items() if k in {"PATH", "SYSTEMROOT", "HOME"}},
             **PROD_ENV, "DJANGO_SETTINGS_MODULE": "config.settings"},
        capture_output=True, text=True, timeout=60, check=False,
    )  # fmt: skip
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == [
        "storages.backends.s3.S3Storage",
        "storages.backends.s3.S3Storage",
        "True",  # private: presigned URLs only
        "False",  # public media: plain URLs on the media domain
        "adyraforge-private",
    ]


def _maintenance(env: dict[str, str], code: str) -> subprocess.CompletedProcess[str]:
    clean = {k: v for k, v in os.environ.items() if k in {"PATH", "SYSTEMROOT", "HOME"}}
    return subprocess.run(
        [sys.executable, "-c", "import django; django.setup();" + code],
        cwd=BACKEND_DIR,
        env={**clean, "DJANGO_ENV": "maintenance", "DJANGO_SETTINGS_MODULE": "config.settings",
             **env},
        capture_output=True, text=True, timeout=60, check=False,
    )  # fmt: skip


MAINT_ENV = {
    "SECRET_KEY": GOOD_KEY,
    "DATABASE_URL": "postgres://u:p@db.example/app?sslmode=require",
}


def test_maintenance_settings_need_only_an_ssl_database_url_and_a_key() -> None:
    result = _maintenance(MAINT_ENV, "from django.conf import settings as s; print(s.DEBUG)")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False"


@pytest.mark.parametrize(
    ("override", "message"),
    [({"DATABASE_URL": "postgres://u:p@db.example/app"}, "sslmode=require"),
     ({"SECRET_KEY": ""}, "SECRET_KEY is missing")],
)  # fmt: skip
def test_maintenance_settings_refuse_insecure_config(override, message) -> None:
    result = _maintenance({**MAINT_ENV, **override}, "")
    assert result.returncode != 0
    assert message in result.stderr


def test_maintenance_settings_can_never_serve_the_site() -> None:
    code = (
        "from django.test import Client;"
        "c = Client();"
        "print(c.get('/api/public/projects/', HTTP_HOST='adyraforge-api.onrender.com').status_code,"
        " c.get('/api/health', HTTP_HOST='x').status_code,"
        " c.get('/', HTTP_HOST='localhost').status_code)"
    )
    result = _maintenance(MAINT_ENV, code)
    assert result.returncode == 0, result.stderr
    statuses = result.stdout.split()
    # 400 DisallowedHost (no ALLOWED_HOSTS); /api/health is answered before host
    # validation by design but touches nothing.
    assert statuses[0] == "400" and statuses[2] == "400", statuses
