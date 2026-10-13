"""Signed, expiring, single-use tokens for invites (password reset uses Django's)."""

from typing import Any

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from .models import User

_INVITE_SALT = "apps.accounts.invite"


def _state(user: User) -> str:
    # Changes as soon as the password is set, which makes the link single-use.
    return salted_hmac(
        _INVITE_SALT, f"{user.pk}:{user.password}:{user.last_login}", algorithm="sha256"
    ).hexdigest()[:32]


def make_invite_token(user: User) -> str:
    return signing.dumps({"u": user.pk, "s": _state(user)}, salt=_INVITE_SALT, compress=True)


def check_invite_token(token: str) -> User | None:
    """The invited user, or None if the token is forged, expired or already used."""
    try:
        data: Any = signing.loads(token, salt=_INVITE_SALT, max_age=settings.INVITE_MAX_AGE)
        user = User.objects.get(pk=int(data["u"]), is_active=True)
    except (signing.BadSignature, User.DoesNotExist, KeyError, TypeError, ValueError):
        return None
    if user.has_usable_password() or not constant_time_compare(_state(user), str(data["s"])):
        return None
    return user


def make_reset_pair(user: User) -> tuple[str, str]:
    return urlsafe_base64_encode(force_bytes(user.pk)), default_token_generator.make_token(user)


def check_reset_pair(uidb64: str, token: str) -> User | None:
    """Django's generator: expires after PASSWORD_RESET_TIMEOUT and is invalidated
    by the password change itself (single-use)."""
    try:
        user = User.objects.get(pk=int(force_str(urlsafe_base64_decode(uidb64))), is_active=True)
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        return None
    return user if default_token_generator.check_token(user, token) else None
