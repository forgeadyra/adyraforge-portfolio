"""MANDATORY: password reset never reveals whether an email exists.
Plus: reset links are 1h + single-use; invite links are signed, 72h, single-use."""

import re
import time
from datetime import datetime, timedelta

import pytest
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core import mail
from django.test import Client

from apps.accounts.emails import send_invite
from apps.accounts.tokens import make_invite_token
from tests.conftest import api_login

pytestmark = pytest.mark.django_db

NEW = "a-brand-new-passphrase-456"


def request_reset(email: str):
    return Client().post(
        "/api/auth/password/reset/", {"email": email}, content_type="application/json"
    )


def confirm(uid: str, token: str, password: str = NEW):
    return Client().post(
        "/api/auth/password/reset/confirm/",
        {"uid": uid, "token": token, "new_password": password},
        content_type="application/json",
    )


def reset_link_parts() -> tuple[str, str]:
    match = re.search(r"/reset-password/([^/\s]+)/([^/\s]+)", mail.outbox[-1].body)
    assert match, mail.outbox[-1].body
    return match.group(1), match.group(2)


@pytest.fixture
def no_reset_throttle(monkeypatch):
    from rest_framework.throttling import SimpleRateThrottle

    rates = {**SimpleRateThrottle.THROTTLE_RATES, "password_reset": "1000/min", "anon": "1000/min"}
    monkeypatch.setattr(SimpleRateThrottle, "THROTTLE_RATES", rates)


def test_reset_response_is_identical_whether_or_not_the_email_exists(
    make_user, no_reset_throttle
) -> None:
    make_user(email="alice@example.com")
    make_user(email="gone@example.com", is_active=False)
    make_user(email="invited@example.com", password=None)

    responses = [
        request_reset(e)
        for e in (
            "alice@example.com",
            "nobody@example.com",
            "gone@example.com",
            "invited@example.com",
        )
    ]
    assert {r.status_code for r in responses} == {202}
    assert len({r.content for r in responses}) == 1  # byte-for-byte identical bodies
    assert (
        len({tuple(sorted((k, v) for k, v in r.items() if k not in {"Date"})) for r in responses})
        == 1
    )
    # Only the real, active account with a password gets an email.
    assert [m.to for m in mail.outbox] == [["alice@example.com"]]


def test_reset_link_works_once(make_user) -> None:
    make_user(email="alice@example.com")
    request_reset("alice@example.com")
    uid, token = reset_link_parts()

    assert confirm(uid, token).status_code == 200
    assert api_login(Client(), "alice@example.com", NEW).status_code == 200
    second = confirm(uid, token, "another-new-passphrase-789")
    assert second.status_code == 400
    assert second.json() == {"detail": "This link is invalid or has expired."}


def test_reset_link_expires_after_one_hour(make_user, monkeypatch) -> None:
    make_user(email="alice@example.com")
    request_reset("alice@example.com")
    uid, token = reset_link_parts()
    now = datetime.now()  # Django's generator uses naive local time
    monkeypatch.setattr(
        PasswordResetTokenGenerator, "_now", lambda self: now + timedelta(minutes=61)
    )
    assert confirm(uid, token).status_code == 400
    monkeypatch.setattr(
        PasswordResetTokenGenerator, "_now", lambda self: now + timedelta(minutes=59)
    )
    assert confirm(uid, token).status_code == 200


def test_reset_enforces_password_validators(make_user) -> None:
    make_user(email="alice@example.com")
    request_reset("alice@example.com")
    uid, token = reset_link_parts()
    weak = confirm(uid, token, "short-1")
    assert weak.status_code == 400 and "new_password" in weak.json()


def test_reset_signs_out_existing_sessions(make_user) -> None:
    make_user(email="alice@example.com")
    old = Client()
    api_login(old, "alice@example.com")
    request_reset("alice@example.com")
    confirm(*reset_link_parts())
    assert old.get("/api/auth/me/").status_code == 403


def test_garbage_reset_tokens_are_rejected(make_user) -> None:
    make_user(email="alice@example.com")
    for uid, token in (("MQ", "nope"), ("!!", "x"), ("", "")):
        assert confirm(uid, token).status_code == 400


# --- invites --------------------------------------------------------------------


def accept(token: str, password: str = NEW):
    return Client().post(
        "/api/auth/invite/accept/",
        {"token": token, "new_password": password},
        content_type="application/json",
    )


def invite_token_from_email() -> str:
    match = re.search(r"/invite/(\S+)", mail.outbox[-1].body)
    assert match
    return match.group(1)


def test_invite_lets_a_new_client_set_a_password_once(make_user) -> None:
    user = make_user(email="new@example.com", password=None)
    send_invite(user)
    token = invite_token_from_email()

    assert api_login(Client(), "new@example.com", NEW).status_code == 400  # not yet
    assert accept(token).status_code == 200
    assert api_login(Client(), "new@example.com", NEW).status_code == 200
    assert accept(token, "attacker-chosen-pass-1").status_code == 400  # single-use


def test_invite_expires_after_72_hours(make_user, monkeypatch) -> None:
    user = make_user(email="new@example.com", password=None)
    token = make_invite_token(user)
    real = time.time
    monkeypatch.setattr("django.core.signing.time.time", lambda: real() + 72 * 3600 + 1)
    assert accept(token).status_code == 400
    monkeypatch.setattr("django.core.signing.time.time", lambda: real() + 71 * 3600)
    assert accept(token).status_code == 200


def test_invite_tokens_cannot_be_forged_or_reused_for_existing_accounts(make_user) -> None:
    user = make_user(email="new@example.com", password=None)
    token = make_invite_token(user)
    assert accept(token[:-2] + ("AA" if not token.endswith("AA") else "BB")).status_code == 400

    has_password = make_user(email="alice@example.com")
    assert accept(make_invite_token(has_password)).status_code == 400  # can't hijack via invite


def test_invite_enforces_password_validators(make_user) -> None:
    user = make_user(email="new@example.com", password=None)
    resp = accept(make_invite_token(user), "elevenchars")
    assert resp.status_code == 400 and "new_password" in resp.json()
