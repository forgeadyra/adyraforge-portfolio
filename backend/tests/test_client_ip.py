"""Client IP behind proxies: one answer for axes, DRF throttles and the IP hash (audit v2, H-1)."""

import pytest
from axes.helpers import get_client_ip_address
from django.core.cache import cache
from django.test import RequestFactory
from rest_framework.settings import api_settings
from rest_framework.test import APIClient

from apps.core.security import client_ip
from apps.core.throttling import AnonRateThrottle

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


# --- Behind Render (1 trusted proxy): every request arrives from the proxy's address,
# and the proxy appends the real client to X-Forwarded-For. ----------------------------
PROXY = "10.0.0.1"
CLIENT_A = "198.51.100.10"
CLIENT_B = "203.0.113.20"


@pytest.fixture
def no_login_throttle(monkeypatch):
    """Isolate axes from the 5/min login throttle, which would also answer 429."""
    from rest_framework.throttling import SimpleRateThrottle

    rates = {**SimpleRateThrottle.THROTTLE_RATES, "login": "1000/min", "anon": "1000/min"}
    monkeypatch.setattr(SimpleRateThrottle, "THROTTLE_RATES", rates)


def via_proxy(real_ip: str, spoofed: str = "") -> dict:
    """Request metadata as Django sees it behind Render: client-sent prefix + appended peer."""
    xff = f"{spoofed}, {real_ip}" if spoofed else real_ip
    return {"REMOTE_ADDR": PROXY, "HTTP_X_FORWARDED_FOR": xff}


@pytest.mark.django_db
def test_behind_one_proxy_two_real_clients_are_throttled_independently(proxies) -> None:
    proxies(1)
    bot = {"name": "n", "email": "n@example.com", "project_type": "other", "message": "m",
           "website": "http://spam.example", "turnstile_token": "t"}  # fmt: skip
    a, b = APIClient(), APIClient()
    codes_a = [a.post("/api/leads/contact/", bot, format="json", **via_proxy(CLIENT_A)).status_code
               for _ in range(6)]  # fmt: skip
    assert codes_a == [201] * 5 + [429]
    # Same proxy address, different real client: its own, untouched bucket.
    assert (
        b.post("/api/leads/contact/", bot, format="json", **via_proxy(CLIENT_B)).status_code == 201
    )


@pytest.mark.django_db
def test_behind_one_proxy_two_real_clients_are_locked_out_independently(
    proxies, make_user, no_login_throttle
) -> None:
    from django.test import Client

    from tests.conftest import api_login

    proxies(1)
    make_user(email="alice@example.com")
    attacker = Client()
    for _ in range(5):
        api_login(attacker, "alice@example.com", "wrong-password-123", **via_proxy(CLIENT_A))
    assert api_login(attacker, "alice@example.com", **via_proxy(CLIENT_A)).status_code == 429
    # Alice herself, from her own network through the same proxy, is not locked out.
    assert api_login(Client(), "alice@example.com", **via_proxy(CLIENT_B)).status_code == 200


@pytest.mark.django_db
def test_spoofed_leftmost_entry_cannot_escape_the_lockout(
    proxies, make_user, no_login_throttle
) -> None:
    from django.test import Client

    from tests.conftest import api_login

    proxies(1)
    make_user(email="alice@example.com")
    attacker = Client()
    for i in range(5):  # a fresh forged "client IP" on every attempt
        api_login(attacker, "alice@example.com", "wrong-password-123",
                  **via_proxy(CLIENT_A, spoofed=f"6.6.6.{i}"))  # fmt: skip
    locked = api_login(attacker, "alice@example.com", **via_proxy(CLIENT_A, spoofed="7.7.7.7"))
    assert locked.status_code == 429
