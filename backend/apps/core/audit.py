from typing import Any

from django.db import models
from django.http import HttpRequest

from .models import AuditLog
from .security import request_ip_hash


def record(
    action: str,
    *,
    request: HttpRequest | None = None,
    actor: Any = None,
    actor_repr: str = "",
    obj: models.Model | None = None,
    message: str = "",
) -> AuditLog:
    if actor is not None and not getattr(actor, "is_authenticated", False):
        actor = None
    entry = AuditLog(
        action=action,
        actor=actor,
        actor_repr=(actor_repr or (str(actor) if actor else ""))[:254],
        message=message,
        ip_hash=request_ip_hash(request),
    )
    if obj is not None:
        entry.object_type = obj._meta.label_lower
        entry.object_id = str(obj.pk)[:64]
        entry.object_repr = str(obj)[:200]
    entry.save()
    return entry
