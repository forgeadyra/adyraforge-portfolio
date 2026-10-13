from typing import Any

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from django.http import HttpRequest

from .audit import record
from .models import AuditLog


@receiver(user_logged_in, dispatch_uid="core.audit.login")
def _logged_in(sender: Any, request: HttpRequest | None, user: Any, **kwargs: Any) -> None:
    record(AuditLog.Action.LOGIN, request=request, actor=user)


@receiver(user_logged_out, dispatch_uid="core.audit.logout")
def _logged_out(sender: Any, request: HttpRequest | None, user: Any, **kwargs: Any) -> None:
    record(AuditLog.Action.LOGOUT, request=request, actor=user)


@receiver(user_login_failed, dispatch_uid="core.audit.login_failed")
def _login_failed(
    sender: Any, credentials: dict[str, Any], request: HttpRequest | None = None, **kwargs: Any
) -> None:
    # Record the attempted email only if it looks like one: people sometimes type
    # their password into the username box, and that must never be logged.
    attempted = str(credentials.get("username") or credentials.get("email") or "")
    attempted = attempted.strip().lower() if "@" in attempted else ""
    record(AuditLog.Action.LOGIN_FAILED, request=request, actor_repr=attempted)
