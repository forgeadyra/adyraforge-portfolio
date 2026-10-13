from typing import Any

from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator, MaxValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.core.models import Currency, TimeStampedModel
from apps.core.validators import JSONSizeValidator


class BudgetRange(models.TextChoices):
    UNDER_500 = "under_500", "Under $500 / ₹40k"
    FROM_500 = "500_1500", "$500–1,500 / ₹40k–1.25L"
    FROM_1500 = "1500_5000", "$1,500–5,000 / ₹1.25L–4L"
    OVER_5000 = "5000_plus", "$5,000+ / ₹4L+"
    NOT_SURE = "not_sure", "Not sure yet"


class ProjectType(models.TextChoices):
    LANDING_PAGE = "landing_page", "Landing page"
    BUSINESS_WEBSITE = "business_website", "Business website"
    WEB_APP = "web_app", "Web application"
    ECOMMERCE = "ecommerce", "E-commerce"
    REDESIGN = "redesign", "Redesign"
    OTHER = "other", "Other"


class Timeline(models.TextChoices):
    ASAP = "asap", "As soon as possible"
    ONE_MONTH = "1_month", "Within a month"
    ONE_TO_THREE = "1_3_months", "1–3 months"
    FLEXIBLE = "flexible", "Flexible"


class Lead(TimeStampedModel):
    class Source(models.TextChoices):
        CONTACT_FORM = "contact_form", "Contact form"
        PLANNER = "planner", "Project planner"
        REFERRAL = "referral", "Referral"
        FIVERR = "fiverr", "Fiverr"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        PROPOSAL = "proposal", "Proposal sent"
        WON = "won", "Won"
        LOST = "lost", "Lost"

    # Pipeline: new -> contacted -> proposal -> won. Forward moves may skip
    # steps; "lost" is reachable from any open stage; won/lost are final.
    PIPELINE = [Status.NEW, Status.CONTACTED, Status.PROPOSAL, Status.WON]
    TERMINAL = {Status.WON, Status.LOST}

    name = models.CharField(max_length=120)
    email = models.EmailField(max_length=254)
    company = models.CharField(max_length=150, blank=True)
    budget_range = models.CharField(
        max_length=20, choices=BudgetRange.choices, default=BudgetRange.NOT_SURE
    )
    project_type = models.CharField(max_length=20, choices=ProjectType.choices)
    timeline = models.CharField(max_length=20, choices=Timeline.choices, default=Timeline.FLEXIBLE)
    message = models.TextField(validators=[MaxLengthValidator(5000)])
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.CONTACT_FORM)
    utm_source = models.CharField(max_length=100, blank=True)
    utm_medium = models.CharField(max_length=100, blank=True)
    utm_campaign = models.CharField(max_length=100, blank=True)
    utm_term = models.CharField(max_length=100, blank=True)
    utm_content = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.NEW)
    status_changed_at = models.DateTimeField(default=timezone.now)
    score = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(100)])
    ip_hash = models.CharField(max_length=64, blank=True, help_text="Keyed hash; never the raw IP.")
    internal_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["email"]),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(score__lte=100), name="lead_score_0_to_100"),
        ]

    def __str__(self) -> str:
        return f"{self.name} <{self.email}>"

    @classmethod
    def from_db(cls, db: Any, field_names: Any, values: Any) -> "Lead":
        instance = super().from_db(db, field_names, values)
        instance._loaded_status = instance.status
        return instance

    @classmethod
    def can_transition(cls, old: str, new: str) -> bool:
        if old == new:
            return True
        if old in cls.TERMINAL:
            return False
        if new == cls.Status.LOST:
            return True
        return cls.PIPELINE.index(new) > cls.PIPELINE.index(old)

    def _check_transition(self) -> None:
        old = getattr(self, "_loaded_status", None)
        if old is not None and not self.can_transition(old, self.status):
            raise ValidationError({"status": f"A lead can't move from '{old}' to '{self.status}'."})

    def clean(self) -> None:
        super().clean()
        self.email = self.email.strip().lower()
        self._check_transition()

    def save(self, *args: Any, **kwargs: Any) -> None:
        # Enforced here too, so shell/API code can't skip the pipeline.
        self.email = self.email.strip().lower()
        self._check_transition()
        if getattr(self, "_loaded_status", self.status) != self.status:
            self.status_changed_at = timezone.now()
        super().save(*args, **kwargs)
        self._loaded_status = self.status


def validate_feature_list(value: Any) -> None:
    if not isinstance(value, list) or len(value) > 30:
        raise ValidationError("Features must be a list of at most 30 items.")
    if not all(isinstance(v, str) and 0 < len(v) <= 60 for v in value):
        raise ValidationError("Each feature must be a string of 1-60 characters.")


def validate_answers(value: Any) -> None:
    if not isinstance(value, dict):
        raise ValidationError("Answers must be an object.")


class PlannerSubmission(TimeStampedModel):
    """One run of the public project planner; linked to a Lead if they leave details."""

    lead = models.ForeignKey(
        Lead, null=True, blank=True, on_delete=models.SET_NULL, related_name="planner_submissions"
    )
    project_type = models.CharField(max_length=20, choices=ProjectType.choices)
    budget_range = models.CharField(
        max_length=20, choices=BudgetRange.choices, default=BudgetRange.NOT_SURE
    )
    timeline = models.CharField(max_length=20, choices=Timeline.choices, default=Timeline.FLEXIBLE)
    page_count = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(200)]
    )
    features = models.JSONField(default=list, blank=True, validators=[validate_feature_list])
    answers = models.JSONField(
        default=dict, blank=True, validators=[validate_answers, JSONSizeValidator(10_000)]
    )
    recommended_services = models.ManyToManyField(
        "portfolio.Service", blank=True, related_name="planner_submissions"
    )
    estimate_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    estimate_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.INR)
    ip_hash = models.CharField(max_length=64, blank=True, help_text="Keyed hash; never the raw IP.")

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(estimate_min__isnull=True)
                | Q(estimate_max__isnull=True)
                | Q(estimate_min__lte=F("estimate_max")),
                name="planner_estimate_min_lte_max",
            ),
            models.CheckConstraint(
                condition=Q(estimate_min__isnull=True) | Q(estimate_min__gte=0),
                name="planner_estimate_min_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"Planner {self.created_at:%Y-%m-%d} · {self.get_project_type_display()}"
