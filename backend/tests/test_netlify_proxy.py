"""Production topology: the browser only talks to adyraforge.netlify.app, which proxies
/api/* to the Render origin with a signed request. Server-side callers (Next build,
ISR, middleware) and attackers can also reach the Render origin directly.

    browser -> Netlify (x-nf-sign, X-Nf-Client-Connection-Ip) -> Render (+XFF) -> Django
    anyone  -> Render (+XFF) -> Django
"""

import base64
import hashlib
import hmac
import json
import time
from http.cookies import SimpleCookie

import pytest
from django.core.cache import cache
from django.test import Client, RequestFactory, override_settings
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework import throttling as drf_throttling

from apps.core import throttling as our_throttling
from apps.core.security import client_ip, via_netlify_proxy
from tests.conftest import PASSWORD

SITE = "https://adyraforge.netlify.app"
API_HOST = "adyraforge-api.onrender.com"
SECRET = "test-netlify-proxy-signing-secret-0123456789"
NETLIFY_EGRESS = "100.64.0.9"  # the address Render sees when Netlify connects
RENDER_PEER = "10.0.0.1"  # Render's load balancer -> Django
REAL_A, REAL_B = "198.51.100.10", "203.0.113.20"

PROXY_SETTINGS = {
    "ALLOWED_HOSTS": [API_HOST],
    "CSRF_TRUSTED_ORIGINS": [SITE],
    "CORS_ALLOWED_ORIGINS": [SITE],
    "FRONTEND_URL": SITE,
    "SESSION_COOKIE_DOMAIN": None,
    "CSRF_COOKIE_DOMAIN": None,
    "SESSION_COOKIE_SECURE": True,
    "CSRF_COOKIE_SECURE": True,
    "NETLIFY_PROXY_SIGNING_SECRET": SECRET,
    "TRUSTED_PROXY_COUNT": 1,
}


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def nf_sign(secret: str = SECRET, alg: str = "HS256", **claims) -> str:
    """An x-nf-sign JWS as Netlify's signed proxy redirects send it."""
    payload = {
        "deploy_context": "production",
        "iss": "netlify",
        "exp": int(time.time()) + 60,
        "netlify_id": "1be0f471-6532-45ff-b1b1-f9c66ea24dc1",
        "site_url": SITE,
        **claims,
    }
    head = _b64(json.dumps({"alg": alg, "typ": "JWT"}).encode())
    body = _b64(json.dumps(payload).encode())
    sig = _b64(hmac.new(secret.encode(), f"{head}.{body}".encode(), hashlib.sha256).digest())
    return f"{head}.{body}.{sig}"


def via_netlify(real_ip: str, spoofed_xff: str = "", sign: str | None = None) -> dict:
    """META for a browser request Netlify proxied: Netlify names the client, Render
    appends the Netlify egress address it saw. A client-sent XFF prefix is kept."""
    xff = ", ".join(p for p in (spoofed_xff, NETLIFY_EGRESS) if p)
    return {"REMOTE_ADDR": RENDER_PEER, "HTTP_X_FORWARDED_FOR": xff, "HTTP_HOST": API_HOST,
            "HTTP_X_NF_SIGN": nf_sign() if sign is None else sign,
            "HTTP_X_NF_CLIENT_CONNECTION_IP": real_ip, "wsgi.url_scheme": "https"}  # fmt: skip


def direct(real_ip: str, spoofed_xff: str = "", **extra: str) -> dict:
    """META for a request sent straight to the Render origin (no Netlify)."""
    xff = ", ".join(p for p in (spoofed_xff, real_ip) if p)
    return {"REMOTE_ADDR": RENDER_PEER, "HTTP_X_FORWARDED_FOR": xff, "HTTP_HOST": API_HOST,
            "wsgi.url_scheme": "https", **extra}  # fmt: skip


@pytest.fixture(autouse=True)
def _topology():
    cache.clear()
    with override_settings(**PROXY_SETTINGS):
        yield
    cache.clear()


rf = RequestFactory()


# --- client IP ------------------------------------------------------------------


def test_signed_netlify_request_uses_netlifys_client_ip() -> None:
    req = rf.get("/", **via_netlify(REAL_A, spoofed_xff="6.6.6.6"))
    assert via_netlify_proxy(req)
    assert client_ip(req) == REAL_A


def test_direct_request_uses_renders_entry_and_ignores_forged_netlify_header() -> None:
    # An attacker calling Render directly forges Netlify's header: no signature, ignored.
    req = rf.get(
        "/", **direct(REAL_B, spoofed_xff="6.6.6.6", HTTP_X_NF_CLIENT_CONNECTION_IP="7.7.7.7")
    )
    assert not via_netlify_proxy(req)
    assert client_ip(req) == REAL_B


@pytest.mark.parametrize(
    "bad_sign",
    [
        "",  # missing
        "not.a.jws",
        nf_sign(secret="the-wrong-secret-xxxxxxxxxxxxxxxxxxxxxxxx"),
        nf_sign(exp=int(time.time()) - 5),  # expired
        nf_sign(iss="someone-else"),
        nf_sign(site_url="https://evil.netlify.app"),  # another Netlify site's signature
        nf_sign(alg="none"),
    ],
    ids=["missing", "garbage", "wrong-secret", "expired", "wrong-iss", "other-site", "alg-none"],
)
def test_bad_signatures_never_unlock_the_netlify_header(bad_sign: str) -> None:
    req = rf.get("/", **via_netlify("7.7.7.7", sign=bad_sign))
    assert not via_netlify_proxy(req)
    # Falls back to the address Render saw: Netlify's egress, never the forged value.
    assert client_ip(req) == NETLIFY_EGRESS


def test_unsigned_header_is_ignored_when_no_secret_is_configured() -> None:
    with override_settings(NETLIFY_PROXY_SIGNING_SECRET=""):
        req = rf.get("/", **via_netlify(REAL_A))
        assert client_ip(req) == NETLIFY_EGRESS


# --- throttles and lockouts through the proxy -------------------------------------

BOT = {"name": "n", "email": "n@example.com", "project_type": "other", "message": "m",
       "website": "http://spam.example", "turnstile_token": "t"}  # fmt: skip


def contact(client: Client, meta: dict) -> int:
    return client.post(
        "/api/leads/contact/", BOT, content_type="application/json", **meta
    ).status_code


@pytest.mark.django_db
def test_two_real_clients_behind_netlify_are_throttled_independently() -> None:
    a, b = Client(), Client()
    assert [contact(a, via_netlify(REAL_A)) for _ in range(6)] == [201] * 5 + [429]
    # Same Netlify egress, same Render peer, different real client: own bucket.
    assert contact(b, via_netlify(REAL_B)) == 201


@pytest.mark.django_db
def test_rotating_spoofed_xff_through_netlify_cannot_reset_the_throttle() -> None:
    c = Client()
    codes = [contact(c, via_netlify(REAL_A, spoofed_xff=f"6.6.6.{i}")) for i in range(6)]
    assert codes == [201] * 5 + [429]


@pytest.mark.django_db
def test_direct_attacker_forging_netlify_ip_cannot_reset_the_throttle() -> None:
    c = Client()
    codes = [contact(c, direct(REAL_B, spoofed_xff=f"6.6.6.{i}",
                               HTTP_X_NF_CLIENT_CONNECTION_IP=f"7.7.7.{i}"))
             for i in range(6)]  # fmt: skip
    assert codes == [201] * 5 + [429]


@pytest.mark.django_db
def test_lockout_is_per_real_client_behind_netlify(make_user, monkeypatch) -> None:
    rates = {**drf_throttling.SimpleRateThrottle.THROTTLE_RATES, "login": "1000/min",
             "anon": "1000/min"}  # fmt: skip
    monkeypatch.setattr(drf_throttling.SimpleRateThrottle, "THROTTLE_RATES", rates)
    make_user(email="alice@example.com")
    attacker = Client()
    for _ in range(5):
        wrong = {"email": "alice@example.com", "password": "wrong-pw-123"}
        attacker.post(
            "/api/auth/login/", wrong, content_type="application/json", **via_netlify(REAL_A)
        )
    login = {"email": "alice@example.com", "password": PASSWORD}
    locked = attacker.post("/api/auth/login/", login, content_type="application/json",
                           **via_netlify(REAL_A))  # fmt: skip
    assert locked.status_code == 429
    ok = Client().post("/api/auth/login/", login, content_type="application/json",
                       **via_netlify(REAL_B))  # fmt: skip
    assert ok.status_code == 200


def test_no_stock_drf_throttle_is_used_anywhere() -> None:
    """Stock DRF throttles key on NUM_PROXIES, which can't express the two paths."""
    from django.conf import settings

    for dotted in settings.REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"]:
        assert dotted.startswith("apps.core.throttling."), dotted

    def views(patterns):
        for p in patterns:
            if isinstance(p, URLResolver):
                yield from views(p.url_patterns)
            elif isinstance(p, URLPattern):
                cls = getattr(p.callback, "cls", None) or getattr(p.callback, "view_class", None)
                if cls is not None:
                    yield cls

    for cls in views(get_resolver().url_patterns):
        for throttle in getattr(cls, "throttle_classes", []):
            assert throttle.__module__ == our_throttling.__name__, f"{cls.__name__}: {throttle}"


# --- login + CSRF through the proxy -------------------------------------------------


def _cookie(response, name: str) -> str:
    raw = [h for k, h in response.items() if k.lower() == "set-cookie"]
    jar = SimpleCookie()
    for morsel in response.cookies.values():
        jar[morsel.key] = morsel
    assert name in jar, raw
    return jar[name].OutputString()


@pytest.mark.django_db
def test_login_and_csrf_work_with_the_netlify_origin(make_user) -> None:
    make_user(email="alice@example.com")
    c = Client(enforce_csrf_checks=True)
    origin = {"HTTP_ORIGIN": SITE, **via_netlify(REAL_A)}

    csrf = c.get("/api/auth/csrf/", **origin)
    assert csrf.status_code == 200
    token = csrf.json()["csrfToken"]
    flags = _cookie(csrf, "csrftoken").lower()
    assert "secure" in flags and "httponly" in flags and "samesite=lax" in flags
    assert "domain=" not in flags  # host-only: the browser binds it to adyraforge.netlify.app

    login = c.post("/api/auth/login/", {"email": "alice@example.com", "password": PASSWORD},
                   content_type="application/json", HTTP_X_CSRFTOKEN=token, **origin)  # fmt: skip
    assert login.status_code == 200, login.content
    session = _cookie(login, "sessionid").lower()
    assert "secure" in session and "httponly" in session and "samesite=lax" in session
    assert "domain=" not in session

    assert c.get("/api/auth/me/", **origin).status_code == 200
    token = c.get("/api/auth/csrf/", **origin).json()["csrfToken"]  # rotated at login

    json_ = {"content_type": "application/json"}
    evil = c.post("/api/auth/logout/", HTTP_X_CSRFTOKEN=token, **json_,
                  **{**origin, "HTTP_ORIGIN": "https://evil.example"})  # fmt: skip
    assert evil.status_code == 403
    no_token = c.post("/api/auth/logout/", **json_, **origin)
    assert no_token.status_code == 403
    ok = c.post("/api/auth/logout/", HTTP_X_CSRFTOKEN=token, **json_, **origin)
    assert ok.status_code == 204
    assert c.get("/api/auth/me/", **origin).status_code == 403
