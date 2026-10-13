"""MANDATORY: axes lockout (5 failures per email+IP, 30 min) and login throttle (5/min)."""

import pytest
from axes.models import AccessAttempt
from django.conf import settings
from django.test import Client
from django_otp.plugins.otp_static.models import StaticDevice
from rest_framework.throttling import SimpleRateThrottle

from tests.conftest import api_login

pytestmark = pytest.mark.django_db


@pytest.fixture
def no_login_throttle(monkeypatch):
    """Isolate axes from the 5/min throttle, which would also answer 429."""
    rates = {**SimpleRateThrottle.THROTTLE_RATES, "login": "1000/min", "anon": "1000/min"}
    monkeypatch.setattr(SimpleRateThrottle, "THROTTLE_RATES", rates)


def test_axes_settings_match_policy() -> None:
    assert settings.AXES_FAILURE_LIMIT == 5
    assert settings.AXES_COOLOFF_TIME.total_seconds() == 30 * 60
    assert settings.AXES_LOCKOUT_PARAMETERS == [["username", "ip_address"]]


def test_five_failures_lock_the_account_even_with_the_right_password(
    make_user, no_login_throttle
) -> None:
    make_user(email="alice@example.com")
    c = Client()
    codes = [api_login(c, "alice@example.com", "wrong-password-123").status_code for _ in range(5)]
    assert codes == [400, 400, 400, 400, 429]  # the 5th failure triggers the lock

    locked = api_login(c, "Alice@Example.com")  # right password, different casing
    assert locked.status_code == 429
    assert locked.json() == {"detail": "Too many failed attempts. Try again later."}
    assert locked["Retry-After"] == "1800"
    assert AccessAttempt.objects.get(username="alice@example.com").failures_since_start >= 5


def test_lockout_response_never_sends_wildcard_cors(make_user, no_login_throttle) -> None:
    make_user(email="alice@example.com")
    c = Client()
    for _ in range(6):
        resp = api_login(
            c, "alice@example.com", "wrong-password-123",
            headers={"Origin": "https://evil.example", "X-Requested-With": "XMLHttpRequest"},
        )  # fmt: skip
    assert resp.status_code == 429
    assert resp.get("Access-Control-Allow-Origin") in (None, "")


def test_lockout_is_per_email_and_ip(make_user, no_login_throttle) -> None:
    make_user(email="alice@example.com")
    make_user(email="bob@example.com")
    attacker = Client(REMOTE_ADDR="203.0.113.66")
    for _ in range(5):
        api_login(attacker, "alice@example.com", "wrong-password-123")
    assert api_login(attacker, "alice@example.com").status_code == 429
    # Same IP, another account: not locked. Same account, another IP: not locked.
    assert api_login(attacker, "bob@example.com").status_code == 200
    assert api_login(Client(REMOTE_ADDR="198.51.100.7"), "alice@example.com").status_code == 200


def test_wrong_otp_codes_count_towards_lockout(make_user, no_login_throttle) -> None:
    staff = make_user(email="forge@example.com", is_staff=True)
    StaticDevice.objects.create(user=staff, name="backup").token_set.create(token="real-code")
    c = Client()
    codes = [api_login(c, staff.email, otp="000000").status_code for _ in range(5)]
    assert codes == [400, 400, 400, 400, 429]
    assert api_login(c, staff.email, otp="real-code").status_code == 429


def test_login_throttle_is_5_per_minute() -> None:
    c = Client()
    # Different emails each time, so this is the throttle and not axes.
    codes = [api_login(c, f"nobody{i}@example.com", "x" * 12).status_code for i in range(6)]
    assert codes == [400, 400, 400, 400, 400, 429]
    blocked = api_login(c, "nobody9@example.com", "x" * 12)
    assert blocked.status_code == 429 and int(blocked["Retry-After"]) > 0
    assert not AccessAttempt.objects.filter(failures_since_start__gte=5).exists()


def test_password_reset_is_throttled() -> None:
    c = Client()
    codes = [
        c.post("/api/auth/password/reset/", {"email": f"x{i}@example.com"},
               content_type="application/json").status_code
        for i in range(4)
    ]  # fmt: skip
    assert codes == [202, 202, 202, 429]
