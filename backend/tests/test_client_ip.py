"""Client IP behind proxies: one answer for axes, DRF throttles and the IP hash (audit v2, H-1)."""

import pytest
from axes.helpers import get_client_ip_address
from django.core.cache import cache
from django.test import RequestFactory
from rest_framework.settings import api_settings
from rest_framework.test import APIClient
from rest_framework.throttling import AnonRateThrottle

from apps.core.security import client_ip

rf = RequestFactory()
SPOOFED = "6.6.6.6, 7.7.7.7"


def drf_ident(request) -> str:
    return AnonRateThrottle().get_ident(request)


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def proxies(settings):
    """Set TRUSTED_PROXY_COUNT and DRF's NUM_PROXIES together, as base settings do."""

    def apply(count: int) -> None:
        settings.TRUSTED_PROXY_COUNT = count
        settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": count}
        api_settings.reload()

    yield apply
    api_settings.reload()


def test_without_trusted_proxies_x_forwarded_for_is_ignored(proxies) -> None:
    proxies(0)
    req = rf.get("/", REMOTE_ADDR="203.0.113.5", HTTP_X_FORWARDED_FOR=SPOOFED)
    assert client_ip(req) == drf_ident(req) == get_client_ip_address(req) == "203.0.113.5"


def test_behind_one_proxy_only_the_proxy_appended_entry_counts(proxies) -> None:
    proxies(1)
    # Client sent "6.6.6.6, 7.7.7.7"; Render appended the real peer 198.51.100.9.
    req = rf.get("/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR=SPOOFED + ", 198.51.100.9")
    assert client_ip(req) == drf_ident(req) == get_client_ip_address(req) == "198.51.100.9"


def test_behind_two_proxies(proxies) -> None:
    proxies(2)
    req = rf.get(
        "/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="6.6.6.6, 198.51.100.9, 10.0.0.7"
    )
    assert client_ip(req) == drf_ident(req) == "198.51.100.9"


def test_missing_or_garbage_header_falls_back_to_remote_addr(proxies) -> None:
    proxies(1)
    assert client_ip(rf.get("/", REMOTE_ADDR="10.0.0.1")) == "10.0.0.1"
    bad = rf.get("/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="not-an-ip")
    assert client_ip(bad) == "10.0.0.1"


@pytest.mark.django_db
@pytest.mark.parametrize("count", [0, 1])
def test_rotating_x_forwarded_for_does_not_reset_the_contact_throttle(proxies, count) -> None:
    """The live exploit: a new spoofed X-Forwarded-For per request used to get a fresh bucket."""
    proxies(count)
    client = APIClient()
    bot = {"name": "n", "email": "n@example.com", "project_type": "other", "message": "m",
           "website": "http://spam.example", "turnstile_token": "t"}  # fmt: skip
    codes = []
    for i in range(6):
        # Attacker-chosen prefix changes every time; the proxy-appended peer stays the same.
        xff = f"198.51.100.{i + 1}, 203.0.113.50"
        resp = client.post("/api/leads/contact/", bot, format="json",
                           REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR=xff)  # fmt: skip
        codes.append(resp.status_code)
    assert codes == [201] * 5 + [429]
