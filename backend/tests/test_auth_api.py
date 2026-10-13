import pytest
from django.conf import settings
from django.contrib.sessions.models import Session
from django.test import Client

from tests.conftest import PASSWORD, api_login

pytestmark = pytest.mark.django_db

SESSION = settings.SESSION_COOKIE_NAME


def test_login_sets_hardened_session_cookie_and_returns_me(make_user) -> None:
    make_user(email="alice@example.com", full_name="Alice")
    resp = api_login(Client(), "ALICE@example.com")
    assert resp.status_code == 200
    assert resp.json() == {
        "id": resp.json()["id"],
        "email": "alice@example.com",
        "full_name": "Alice",
        "role": "client",
    }
    cookie = resp.cookies[SESSION]
    assert cookie["httponly"] is True
    assert cookie["secure"] is True
    assert cookie["samesite"] == "Lax"
    assert int(cookie["max-age"]) == 14 * 24 * 3600


def test_login_rotates_the_session_key(make_user) -> None:
    make_user(email="alice@example.com")
    c = Client()
    pre = c.session
    pre["visited"] = True
    pre.save()
    c.cookies[SESSION] = pre.session_key
    old_key = pre.session_key

    resp = api_login(c, "alice@example.com")
    assert resp.status_code == 200
    assert resp.cookies[SESSION].value != old_key
    assert not Session.objects.filter(session_key=old_key).exists()


@pytest.mark.parametrize(
    "email,password",
    [("alice@example.com", "wrong-password-123"), ("nobody@example.com", PASSWORD)],
    ids=["wrong-password", "unknown-email"],
)
def test_login_failure_is_generic(make_user, email: str, password: str) -> None:
    make_user(email="alice@example.com")
    resp = api_login(Client(), email, password)
    assert resp.status_code == 400
    assert resp.json() == {"detail": "Invalid email or password."}


def test_inactive_and_invited_users_cannot_log_in(make_user) -> None:
    make_user(email="gone@example.com", is_active=False)
    make_user(email="invited@example.com", password=None)
    for email, pw in (("gone@example.com", PASSWORD), ("invited@example.com", "")):
        resp = api_login(Client(), email, pw or "anything-at-all-123")
        assert resp.status_code == 400


def test_logout_deletes_the_session_server_side(make_user) -> None:
    make_user(email="alice@example.com")
    c = Client()
    key = api_login(c, "alice@example.com").cookies[SESSION].value
    assert c.post("/api/auth/logout/").status_code == 204
    assert not Session.objects.filter(session_key=key).exists()

    replay = Client()
    replay.cookies[SESSION] = key  # a stolen cookie is now worthless
    assert replay.get("/api/auth/me/").status_code == 403


def test_logout_all_devices_kills_every_session(make_user) -> None:
    make_user(email="alice@example.com")
    laptop, phone = Client(), Client()
    api_login(laptop, "alice@example.com")
    api_login(phone, "alice@example.com")
    assert phone.get("/api/auth/me/").status_code == 200

    assert laptop.post("/api/auth/logout-all/").status_code == 204
    assert phone.get("/api/auth/me/").status_code == 403
    assert laptop.get("/api/auth/me/").status_code == 403
    # Logging in again works normally.
    assert api_login(phone, "alice@example.com").status_code == 200


def test_password_change_keeps_this_session_and_ends_others(make_user) -> None:
    make_user(email="alice@example.com")
    here, elsewhere = Client(), Client()
    api_login(here, "alice@example.com")
    api_login(elsewhere, "alice@example.com")

    new = "a-brand-new-passphrase-456"
    resp = here.post(
        "/api/auth/password/change/",
        {"current_password": PASSWORD, "new_password": new},
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert here.get("/api/auth/me/").status_code == 200
    assert elsewhere.get("/api/auth/me/").status_code == 403
    assert api_login(Client(), "alice@example.com", new).status_code == 200


@pytest.mark.parametrize(
    "body,field",
    [
        (
            {"current_password": "wrong-one-123", "new_password": "a-brand-new-passphrase-456"},
            "current_password",
        ),
        ({"current_password": PASSWORD, "new_password": "short-pw-1"}, "new_password"),  # < 12
        ({"current_password": PASSWORD, "new_password": "password1234"}, "new_password"),  # common
        ({"current_password": PASSWORD, "new_password": "123456789012"}, "new_password"),  # numeric
    ],
)
def test_password_change_validation(make_user, body, field) -> None:
    make_user(email="alice@example.com")
    c = Client()
    api_login(c, "alice@example.com")
    resp = c.post("/api/auth/password/change/", body, content_type="application/json")
    assert resp.status_code == 400
    assert field in resp.json()


def test_csrf_is_enforced_on_authenticated_writes(make_user) -> None:
    make_user(email="alice@example.com")
    c = Client(enforce_csrf_checks=True)
    token = c.get("/api/auth/csrf/").json()["csrfToken"]
    login = c.post(
        "/api/auth/login/",
        {"email": "alice@example.com", "password": PASSWORD},
        content_type="application/json",
        headers={"X-CSRFToken": token},
    )
    assert login.status_code == 200

    no_token = c.post("/api/auth/logout/", {}, content_type="application/json")
    assert no_token.status_code == 403
    assert "CSRF" in no_token.json()["detail"]
    stale = c.post(
        "/api/auth/logout/", {}, content_type="application/json", headers={"X-CSRFToken": token}
    )  # pre-login token was rotated
    assert stale.status_code == 403
    fresh = c.get("/api/auth/csrf/").json()["csrfToken"]
    ok = c.post(
        "/api/auth/logout/", {}, content_type="application/json", headers={"X-CSRFToken": fresh}
    )
    assert ok.status_code == 204


def test_me_requires_login() -> None:
    assert Client().get("/api/auth/me/").status_code == 403
