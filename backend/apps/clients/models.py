"""Client portal data. Every queryset here is scoped with ``for_user()``.

Two scopes (CLAUDE.md rule 6):

- ``owned_by(user)``: strictly the user's own rows, no staff bypass. Every
  client-portal view uses this, so a staff account without OTP can't read
  other clients' data through the portal.
- ``for_user(user)``: own rows for clients, everything for staff. Only for the
  OTP-gated admin API.

Deletion is
conservative: client projects and invoices are PROTECTed, so removing a user or
profile can never silently cascade into financial records.
"""

import unicodedata
from pathlib import PurePath
from typing import Any, ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q

from apps.core.models import Currency, TimeStampedModel
from apps.core.storage import private_storage
from apps.core.validators import UUIDUploadTo, detect_mime, document_validator, pdf_validator


class OwnedQuerySet(models.QuerySet):
    """Row-level scoping. Subclasses name the lookup path to the owning User."""

    owner_lookup: ClassVar[str]

    def owned_by(self, user: Any) -> "OwnedQuerySet":
        if user is None or not getattr(user, "is_authenticated", False) or not user.is_active:
            return self.none()
        return self.filter(**{self.owner_lookup: user})

    def for_user(self, user: Any) -> "OwnedQuerySet":
        if user is None or not getattr(user, "is_authenticated", False) or not user.is_active:
            return self.none()
        if user.is_staff:
            return self.all()
        return self.filter(**{self.owner_lookup: user})


class ClientProfile(TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="client_profile"
    )
    company = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    timezone = models.CharField(max_length=64, default="UTC")
    internal_notes = models.TextField(
        blank=True, help_text="Admin only; never shown to the client."
    )

    class ProfileQuerySet(OwnedQuerySet):
        owner_lookup = "user"

    objects = ProfileQuerySet.as_manager()

    class Meta:
        ordering = ["user__email"]

    def __str__(self) -> str:
        return f"{self.user.email} ({self.company})" if self.company else self.user.email

    def clean(self) -> None:
        super().clean()
        if self.user_id and self.user.is_staff:
            raise ValidationError({"user": "Staff accounts can't be client profiles."})


class ClientProject(TimeStampedModel):
    class Status(models.TextChoices):
        PLANNING = "planning", "Planning"
        IN_PROGRESS = "in_progress", "In progress"
        REVIEW = "review", "In review"
        COMPLETED = "completed", "Completed"
        ON_HOLD = "on_hold", "On hold"
        CANCELLED = "cancelled", "Cancelled"

    client = models.ForeignKey(ClientProfile, on_delete=models.PROTECT, related_name="projects")
    portfolio_project = models.ForeignKey(
        "portfolio.Project",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="client_projects",
        help_text="Optional link to the public case study.",
    )
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True, validators=[MaxLengthValidator(5000)])
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PLANNING)
    progress = models.PositiveSmallIntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)

    class ProjectQuerySet(OwnedQuerySet):
        owner_lookup = "client__user"

    objects = ProjectQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(progress__lte=100), name="clientproject_progress_0_100"
            ),
            models.CheckConstraint(
                condition=Q(start_date__isnull=True)
                | Q(due_date__isnull=True)
                | Q(due_date__gte=F("start_date")),
                name="clientproject_due_after_start",
            ),
        ]

    def __str__(self) -> str:
        return self.title


class Milestone(TimeStampedModel):
    client_project = models.ForeignKey(
        ClientProject, on_delete=models.CASCADE, related_name="milestones"
    )
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True, validators=[MaxLengthValidator(2000)])
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class MilestoneQuerySet(OwnedQuerySet):
        owner_lookup = "client_project__client__user"

    objects = MilestoneQuerySet.as_manager()

    class Meta:
        ordering = ["order", "due_date", "id"]

    def __str__(self) -> str:
        return self.title

    @property
    def is_complete(self) -> bool:
        return self.completed_at is not None


def clean_display_name(name: str) -> str:
    """Original filename for display only: basename, no control chars, bounded."""
    base = PurePath(name.replace("\\", "/")).name
    cleaned = "".join(c for c in base if unicodedata.category(c)[0] != "C").strip()
    return cleaned[:255] or "file"


class ProjectFile(TimeStampedModel):
    """Private deliverable/asset. Stored outside the web root under a UUID name."""

    client_project = models.ForeignKey(
        ClientProject, on_delete=models.CASCADE, related_name="files"
    )
    file = models.FileField(
        storage=private_storage,
        upload_to=UUIDUploadTo("client-files"),
        validators=[document_validator],
        max_length=255,
    )
    original_name = models.CharField(max_length=255, editable=False)
    content_type = models.CharField(max_length=120, editable=False)
    size = models.PositiveBigIntegerField(editable=False, default=0)
    description = models.CharField(max_length=300, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class FileQuerySet(OwnedQuerySet):
        owner_lookup = "client_project__client__user"

    objects = FileQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.original_name or self.file.name

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.file and not self.original_name:
            self.original_name = clean_display_name(self.file.name)
            self.size = self.file.size
            self.content_type = detect_mime(self.file) or "application/octet-stream"
        super().save(*args, **kwargs)


class Message(TimeStampedModel):
    """Plain text (escaped on render, never treated as HTML). One thread per ClientProject."""

    client_project = models.ForeignKey(
        ClientProject, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    body = models.TextField(validators=[MaxLengthValidator(5000)])
    read_at = models.DateTimeField(null=True, blank=True)

    class MessageQuerySet(OwnedQuerySet):
        owner_lookup = "client_project__client__user"

    objects = MessageQuerySet.as_manager()

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return f"{self.sender} @ {self.created_at:%Y-%m-%d %H:%M}"


class Invoice(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"
        PAID = "paid", "Paid"
        OVERDUE = "overdue", "Overdue"
        VOID = "void", "Void"

    client_project = models.ForeignKey(
        ClientProject, on_delete=models.PROTECT, related_name="invoices"
    )
    # Entered by the admin; numbering scheme is a business decision, not generated.
    number = models.CharField(max_length=32, unique=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.INR)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    issued_on = models.DateField(null=True, blank=True)
    due_date = models.DateField()
    paid_at = models.DateTimeField(null=True, blank=True)
    pdf = models.FileField(
        storage=private_storage,
        upload_to=UUIDUploadTo("invoices"),
        validators=[pdf_validator],
        blank=True,
        max_length=255,
    )
    notes = models.TextField(blank=True, validators=[MaxLengthValidator(2000)])

    class InvoiceQuerySet(OwnedQuerySet):
        owner_lookup = "client_project__client__user"

        def for_user(self, user: Any) -> "OwnedQuerySet":
            qs = super().for_user(user)
            # Clients never see drafts.
            return qs if getattr(user, "is_staff", False) else qs.exclude(status="draft")

        def owned_by(self, user: Any) -> "OwnedQuerySet":
            return super().owned_by(user).exclude(status="draft")

    objects = InvoiceQuerySet.as_manager()

    class Meta:
        ordering = ["-due_date", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="invoice_amount_positive"),
            models.CheckConstraint(
                condition=~Q(status="paid") | Q(paid_at__isnull=False),
                name="invoice_paid_has_paid_at",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.number} · {self.amount} {self.currency}"


def owner_of(obj: models.Model) -> Any:
    """The User who owns obj, following its queryset's owner_lookup path."""
    lookup = type(obj).objects.get_queryset().owner_lookup  # type: ignore[attr-defined]
    target: Any = obj
    for attr in lookup.split("__"):
        target = getattr(target, attr)
    return target
