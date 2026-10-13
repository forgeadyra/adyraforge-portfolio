from django.contrib import admin, messages

from apps.accounts.emails import send_invite
from apps.core.admin import AuditedModelAdmin

from .models import ClientProfile, ClientProject, Invoice, Message, Milestone, ProjectFile


@admin.register(ClientProfile)
class ClientProfileAdmin(AuditedModelAdmin):
    """Creating a profile for a user without a password emails them a 72h invite."""

    list_display = ("user", "company", "phone", "has_password", "created_at")
    search_fields = ("user__email", "user__full_name", "company")
    autocomplete_fields = ("user",)
    actions = ["send_invite_email"]

    @admin.display(boolean=True, description="Password set")
    def has_password(self, obj: ClientProfile) -> bool:
        return obj.user.has_usable_password()

    def save_model(self, request, obj, form, change):  # type: ignore[no-untyped-def]
        super().save_model(request, obj, form, change)
        if not change and not obj.user.has_usable_password():
            send_invite(obj.user)
            self.message_user(request, f"Invite emailed to {obj.user.email}.", messages.SUCCESS)

    @admin.action(description="Send invite email (clients without a password)")
    def send_invite_email(self, request, queryset):  # type: ignore[no-untyped-def]
        sent = 0
        for profile in queryset.select_related("user"):
            if not profile.user.has_usable_password():
                send_invite(profile.user)
                sent += 1
        self.message_user(request, f"Sent {sent} invite(s). Clients with a password were skipped.")


class MilestoneInline(admin.TabularInline):
    model = Milestone
    extra = 0
    fields = ("title", "due_date", "completed_at", "order")


class ProjectFileInline(admin.TabularInline):
    model = ProjectFile
    extra = 0
    fields = ("file", "description", "original_name", "content_type", "size", "uploaded_by")
    readonly_fields = ("original_name", "content_type", "size", "uploaded_by")


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = ("created_at", "sender", "body", "read_at")
    readonly_fields = ("created_at", "sender", "read_at")


@admin.register(ClientProject)
class ClientProjectAdmin(AuditedModelAdmin):
    list_display = ("title", "client", "status", "progress", "start_date", "due_date")
    list_filter = ("status", ("due_date", admin.DateFieldListFilter))
    search_fields = ("title", "client__user__email", "client__company")
    autocomplete_fields = ("client", "portfolio_project")
    inlines = [MilestoneInline, ProjectFileInline, MessageInline]

    def save_formset(self, request, form, formset, change):  # type: ignore[no-untyped-def]
        # Stamp the uploader / sender on rows added through the inlines.
        for obj in formset.save(commit=False):
            if isinstance(obj, ProjectFile) and not obj.uploaded_by_id:
                obj.uploaded_by = request.user
            if isinstance(obj, Message) and not obj.sender_id:
                obj.sender = request.user
            obj.save()
        for obj in formset.deleted_objects:
            obj.delete()
        formset.save_m2m()


@admin.register(Milestone)
class MilestoneAdmin(AuditedModelAdmin):
    list_display = ("title", "client_project", "due_date", "completed_at")
    list_filter = (("due_date", admin.DateFieldListFilter),)
    search_fields = ("title", "client_project__title")
    autocomplete_fields = ("client_project",)


@admin.register(ProjectFile)
class ProjectFileAdmin(AuditedModelAdmin):
    list_display = ("original_name", "client_project", "content_type", "size", "created_at")
    list_filter = ("content_type",)
    search_fields = ("original_name", "description", "client_project__title")
    autocomplete_fields = ("client_project",)
    audit_readonly_fields = (
        "created_at", "updated_at", "original_name", "content_type", "size", "uploaded_by",
    )  # fmt: skip

    def save_model(self, request, obj, form, change):  # type: ignore[no-untyped-def]
        if not obj.uploaded_by_id:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Message)
class MessageAdmin(AuditedModelAdmin):
    list_display = ("client_project", "sender", "created_at", "read_at")
    list_filter = (("created_at", admin.DateFieldListFilter),)
    search_fields = ("body", "client_project__title", "sender__email")
    autocomplete_fields = ("client_project",)
    audit_readonly_fields = ("created_at", "updated_at", "sender")

    def save_model(self, request, obj, form, change):  # type: ignore[no-untyped-def]
        if not obj.sender_id:
            obj.sender = request.user
        super().save_model(request, obj, form, change)


@admin.register(Invoice)
class InvoiceAdmin(AuditedModelAdmin):
    list_display = ("number", "client_project", "amount", "currency", "status", "due_date")
    list_filter = ("status", "currency", ("due_date", admin.DateFieldListFilter))
    search_fields = ("number", "client_project__title", "client_project__client__user__email")
    autocomplete_fields = ("client_project",)
