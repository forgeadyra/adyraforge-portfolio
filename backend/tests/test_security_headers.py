import pytest
from django.conf import settings
from django.test import Client, override_settings


@pytest.fixture
def response(client: Client):
    return client.get("/healthz/", secure=True)


def test_security_headers_present(response) -> None:
    h = response.headers
    assert h["X-Frame-Options"] == "DENY"
    assert h["X-Content-Type-Options"] == "nosniff"
    assert h["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert h["Cross-Origin-Opener-Policy"] == "same-origin"
    assert "camera=()" in h["Permissions-Policy"]


def test_hsts_one_year_with_subdomains_and_preload(response) -> None:
    assert response.headers["Strict-Transport-Security"] == (
        "max-age=31536000; includeSubDomains; preload"
    )


def test_csp_is_locked_down(response) -> None:
    csp = response.headers["Content-Security-Policy"]
    assert "default-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "unsafe-inline" not in csp
    assert "unsafe-eval" not in csp


def test_cookie_flags_are_secure_by_default() -> None:
    assert settings.SESSION_COOKIE_HTTPONLY is True
    assert settings.SESSION_COOKIE_SECURE is True
    assert settings.SESSION_COOKIE_SAMESITE == "Lax"
    assert settings.CSRF_COOKIE_SECURE is True
    assert settings.CSRF_COOKIE_SAMESITE == "Lax"


@override_settings(SECURE_SSL_REDIRECT=True)
def test_http_is_redirected_to_https(client: Client) -> None:
    resp = client.get("/api/auth/me/")
    assert resp.status_code == 301
    assert resp.headers["Location"].startswith("https://")


@override_settings(SECURE_SSL_REDIRECT=True)
def test_healthcheck_is_exempt_from_https_redirect(client: Client) -> None:
    assert client.get("/healthz/").status_code == 200


def test_cors_allows_only_listed_origins(client: Client) -> None:
    allowed = client.get("/api/auth/csrf/", headers={"Origin": "https://adyraforge.test"})
    assert allowed.headers["Access-Control-Allow-Origin"] == "https://adyraforge.test"
    assert allowed.headers["Access-Control-Allow-Credentials"] == "true"

    evil = client.get("/api/auth/csrf/", headers={"Origin": "https://evil.example"})
    assert "Access-Control-Allow-Origin" not in evil.headers
    assert settings.CORS_ALLOW_ALL_ORIGINS is False


@override_settings(ALLOWED_HOSTS=["api.adyraforge.test"])
def test_healthcheck_answers_probes_by_container_ip(client: Client) -> None:
    # Docker/Render probe the container by IP, which is never in ALLOWED_HOSTS.
    resp = client.get("/healthz/", HTTP_HOST="10.0.0.5:8000", secure=True)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'none'" in resp.headers["Content-Security-Policy"]


@override_settings(ALLOWED_HOSTS=["api.adyraforge.test"])
def test_host_validation_still_applies_everywhere_else(client: Client) -> None:
    assert client.get("/api/auth/csrf/", HTTP_HOST="10.0.0.5:8000", secure=True).status_code == 400
    assert client.get("/healthz/x", HTTP_HOST="10.0.0.5:8000", secure=True).status_code == 400
    assert client.post("/healthz/", HTTP_HOST="10.0.0.5:8000", secure=True).status_code == 400


@pytest.mark.parametrize("path", ["/api/health", "/api/health/"])
def test_uptime_monitor_health_path(client: Client, path: str) -> None:
    resp = client.get(path, secure=True)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
