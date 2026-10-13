"""Project-wide guarantees that every future endpoint inherits (rules 5, 8, 14)."""

import pytest
from django.conf import settings
from django.core.cache import cache
from django.test import Client, override_settings
from django.urls import URLPattern, URLResolver, get_resolver, path
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView


def _api_views(patterns=None, prefix=""):
    for p in patterns if patterns is not None else get_resolver().url_patterns:
        if isinstance(p, URLResolver):
            yield from _api_views(p.url_patterns, prefix + str(p.pattern))
        elif isinstance(p, URLPattern):
            cls = getattr(p.callback, "cls", None)
            if cls is not None and issubclass(cls, APIView):
                yield prefix + str(p.pattern), cls


def test_there_are_api_views_to_check() -> None:
    assert list(_api_views())


@pytest.mark.parametrize(("route", "view"), list(_api_views()))
def test_every_api_view_declares_permission_classes_explicitly(route: str, view: type) -> None:
    declared = any("permission_classes" in vars(k) for k in view.__mro__ if k is not APIView)
    assert declared, f"{route} ({view.__name__}) must set permission_classes explicitly"


def test_defaults_are_authenticated_session_json() -> None:
    rf = settings.REST_FRAMEWORK
    assert rf["DEFAULT_PERMISSION_CLASSES"] == ["rest_framework.permissions.IsAuthenticated"]
    assert rf["DEFAULT_AUTHENTICATION_CLASSES"] == [
        "rest_framework.authentication.SessionAuthentication"
    ]
    assert rf["DEFAULT_RENDERER_CLASSES"] == ["rest_framework.renderers.JSONRenderer"]
    for scope in ("anon", "user", "login", "password_reset", "contact", "planner"):
        assert scope in rf["DEFAULT_THROTTLE_RATES"]


def test_anon_throttle_returns_429_with_retry_after(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    rates = {**SimpleRateThrottle.THROTTLE_RATES, "anon": "2/min"}
    monkeypatch.setattr(SimpleRateThrottle, "THROTTLE_RATES", rates)
    cache.clear()
    codes = [client.get("/api/auth/csrf/").status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    blocked = client.get("/api/auth/csrf/")
    assert int(blocked.headers["Retry-After"]) > 0


def test_unknown_url_returns_generic_json_404(client: Client) -> None:
    resp = client.get("/definitely-not-a-route/")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Not found."}


def _boom(request):
    raise RuntimeError("internal detail that must never leak")


urlpatterns = [path("boom/", _boom)]
handler500 = "apps.core.views.server_error"


@override_settings(ROOT_URLCONF=__name__, DEBUG=False)
def test_server_error_is_generic_json_without_traceback() -> None:
    client = Client(raise_request_exception=False)
    resp = client.get("/boom/")
    assert resp.status_code == 500
    assert resp.json() == {"detail": "Server error."}
    assert b"internal detail" not in resp.content
    assert b"Traceback" not in resp.content
