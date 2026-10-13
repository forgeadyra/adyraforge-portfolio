from typing import Any

from django.conf import settings
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Currency(models.TextChoices):
    INR = "INR", "Indian rupee (₹)"
    USD = "USD", "US dollar ($)"


class AuditLog(models.Model):
    """Append-only record of auth and admin events (who, what, when, from where).

    IPs are stored only as a keyed hash (see apps.core.security.hash_ip).
    """

    class Action(models.TextChoices):
        LOGIN = "auth.login", "Login"
        LOGIN_FAILED = "auth.login_failed", "Login failed"
        LOGOUT = "auth.logout", "Logout"
        ADMIN_ADD = "admin.add", "Admin: added"
        ADMIN_CHANGE = "admin.change", "Admin: changed"
        ADMIN_DELETE = "admin.delete", "Admin: deleted"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    # Snapshot so the trail stays readable after the user is deleted.
    actor_repr = models.CharField(max_length=254, blank=True)
    action = models.CharField(max_length=32, choices=Action.choices)
    object_type = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=64, blank=True)
    object_repr = models.CharField(max_length=200, blank=True)
    message = models.TextField(blank=True)
    ip_hash = models.CharField(max_length=64, blank=True)
    timestamp = models.DateTimeField(default=timezone.now, editable=False, db_index=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [models.Index(fields=["action", "-timestamp"])]

    def __str__(self) -> str:
        return f"{self.timestamp:%Y-%m-%d %H:%M} {self.action} {self.actor_repr}".strip()

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise ValueError("Audit log entries are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> Any:
        raise ValueError("Audit log entries cannot be deleted.")
