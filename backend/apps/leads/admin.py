from django.contrib import admin

from apps.core.admin import AuditedModelAdmin

from .models import Lead, PlannerSubmission


class PlannerSubmissionInline(admin.TabularInline):
    model = PlannerSubmission
    extra = 0
    can_delete = False
    show_change_link = True
    fields = ("created_at", "project_type", "budget_range", "estimate_min", "estimate_max")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None) -> bool:  # type: ignore[no-untyped-def]
        return False


@admin.register(Lead)
class LeadAdmin(AuditedModelAdmin):
    list_display = (
        "name",
        "email",
        "project_type",
        "budget_range",
        "status",
        "score",
        "created_at",
    )
    list_filter = ("status", "project_type", "budget_range", "timeline", "source", "utm_source")
    search_fields = ("name", "email", "company", "message")
    date_hierarchy = "created_at"
    inlines = [PlannerSubmissionInline]
    audit_readonly_fields = ("created_at", "updated_at", "status_changed_at", "ip_hash")
    fieldsets = (
        (None, {"fields": ("status", "score", "internal_notes")}),
        ("Contact", {"fields": ("name", "email", "company")}),
        ("Request", {"fields": ("project_type", "budget_range", "timeline", "message")}),
        (
            "Attribution",
            {
                "fields": (
                    "source",
                    "utm_source",
                    "utm_medium",
                    "utm_campaign",
                    "utm_term",
                    "utm_content",
                )
            },
        ),
        ("Audit", {"fields": ("created_at", "updated_at", "status_changed_at", "ip_hash")}),
    )


@admin.register(PlannerSubmission)
class PlannerSubmissionAdmin(AuditedModelAdmin):
    list_display = (
        "created_at",
        "project_type",
        "budget_range",
        "timeline",
        "lead",
        "estimate_max",
    )
    list_filter = ("project_type", "budget_range", "timeline", "currency")
    search_fields = ("lead__email", "lead__name")
    autocomplete_fields = ("lead",)
    filter_horizontal = ("recommended_services",)
    audit_readonly_fields = ("created_at", "updated_at", "ip_hash")
