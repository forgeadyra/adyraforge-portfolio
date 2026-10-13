from typing import Any

from django.http import HttpRequest

from .models import normalize_email_address

_USERNAME_KEYS = ("username", "email")


def lockout_username(request: HttpRequest, credentials: dict[str, Any] | None) -> str:
    """Username key for django-axes lockouts.

    Accepts the email under either key (Django's authenticate() and the admin form
    use ``username``; a JSON login body may use ``email``) and normalises it, so
    "Forge@X.com" and "forge@x.com" share one failure counter and casing can't
    bypass the lockout.
    """
    sources: list[Any] = [credentials or {}]
    sources.append(getattr(request, "data", None) or request.POST)
    for source in sources:
        for key in _USERNAME_KEYS:
            value = source.get(key)
            if value:
                return normalize_email_address(str(value))
    return ""
