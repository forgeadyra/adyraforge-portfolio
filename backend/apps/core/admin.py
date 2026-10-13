from typing import Any

from django.contrib import admin
from django.db import models
from django.db.models import Model, QuerySet
from django.http import HttpRequest

from .audit import record
from .models import AuditLog


class AuditedAdminMixin:
    """Mirror every admin add/change/delete into AuditLog, with the actor's IP hash."""

    def log_addition(self, request: HttpRequest, obj: Model, message: Any) -> Any:
        entry = super().log_addition(request, obj, message)  # type: ignore[misc]
        record(AuditLog.Action.ADMIN_ADD, request=request, actor=request.user, obj=obj)
        return entry

    def log_change(self, request: HttpRequest, obj: Model, message: Any) -> Any:
        entry = super().log_change(request, obj, message)  # type: ignore[misc]
        record(
            AuditLog.Action.ADMIN_CHANGE,
            request=request,
            actor=request.user,
            obj=obj,
            message=entry.get_change_message() if entry else "",
        )
        return entry

    def log_deletions(self, request: HttpRequest, queryset: QuerySet) -> Any:
        # Called before the rows are deleted, so the objects still exist here.
        for obj in queryset:
            record(AuditLog.Action.ADMIN_DELETE, request=request, actor=request.user, obj=obj)
        return super().log_deletions(request, queryset)  # type: ignore[misc]


class AuditedModelAdmin(AuditedAdminMixin, admin.ModelAdmin):
    """Base for every project ModelAdmin: audited, timestamps read-only."""

    audit_readonly_fields: tuple[str, ...] = ("created_at", "updated_at")
    # Scheme-less URLs typed into the admin become https:// (we never link over http).
    formfield_overrides = {models.URLField: {"assume_scheme": "https"}}

    def get_readonly_fields(self, request: HttpRequest, obj: Model | None = None) -> Any:
        fields = tuple(super().get_readonly_fields(request, obj))
        own = [f for f in self.audit_readonly_fields if hasattr(self.model, f)]
        return fields + tuple(f for f in own if f not in fields)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Read-only. Entries can't be added, edited or deleted from the admin."""

    list_display = ("timestamp", "action", "actor_repr", "object_type", "object_repr")
    list_filter = ("action", "object_type", ("timestamp", admin.DateFieldListFilter))
    search_fields = ("actor_repr", "object_repr", "object_type", "object_id", "ip_hash")
    date_hierarchy = "timestamp"
    list_per_page = 100

    def get_readonly_fields(self, request: HttpRequest, obj: Model | None = None) -> Any:
        return [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Model | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Model | None = None) -> bool:
        return False
