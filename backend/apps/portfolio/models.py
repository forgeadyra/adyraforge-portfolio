from typing import Any

import nh3
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator, MinValueValidator, URLValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import TimeStampedModel
from apps.core.validators import UUIDUploadTo, image_validator

https_url = URLValidator(schemes=["https"])

# Rich text allowlist for blog bodies. Everything else (script, style, iframes,
# event handlers, javascript: URLs) is stripped by nh3.
RICH_TEXT_TAGS = {
    "p", "br", "h2", "h3", "h4", "strong", "em", "b", "i", "u", "s", "a", "ul", "ol",
    "li", "blockquote", "code", "pre", "hr", "img", "figure", "figcaption",
}  # fmt: skip
RICH_TEXT_ATTRIBUTES = {"a": {"href", "title"}, "img": {"src", "alt", "width", "height"}}


def sanitize_rich_text(value: str) -> str:
    return nh3.clean(
        value,
        tags=RICH_TEXT_TAGS,
        attributes=RICH_TEXT_ATTRIBUTES,
        url_schemes={"https", "mailto"},
        link_rel="noopener noreferrer nofollow",
    )


def validate_result_metrics(value: Any) -> None:
    """[{"label": "Load time", "value": "0.8s"}, ...]; at most 8 short entries."""
    if not isinstance(value, list) or len(value) > 8:
        raise ValidationError("Result metrics must be a list of at most 8 items.")
    for item in value:
        if (
            not isinstance(item, dict)
            or set(item) != {"label", "value"}
            or not all(isinstance(item[k], str) and 0 < len(item[k]) <= 60 for k in item)
        ):
            raise ValidationError(
                'Each metric must be {"label": str, "value": str}, each 1-60 characters.'
            )


def validate_includes(value: Any) -> None:
    """["Custom layouts", "SEO foundation", ...]; at most 12 short items."""
    if not isinstance(value, list) or len(value) > 12:
        raise ValidationError("Included items must be a list of at most 12 entries.")
    if not all(isinstance(v, str) and 0 < len(v) <= 80 for v in value):
        raise ValidationError("Each included item must be 1-80 characters.")


class PublishedQuerySet(models.QuerySet):
    def published(self) -> "PublishedQuerySet":
        return self.filter(published=True)


class Service(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    summary = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    includes = models.JSONField(default=list, blank=True, validators=[validate_includes])
    # Public "starting from" prices. Left empty, the site shows no price at all.
    price_from_inr = models.PositiveIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1)], verbose_name="Starting from (₹)"
    )
    price_from_usd = models.PositiveIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1)], verbose_name="Starting from ($)"
    )
    order = models.PositiveSmallIntegerField(default=0)
    published = models.BooleanField(default=False)

    objects = PublishedQuerySet.as_manager()

    class Meta:
        ordering = ["order", "name"]

    def __str__(self) -> str:
        return self.name


class Technology(TimeStampedModel):
    class Category(models.TextChoices):
        FRONTEND = "frontend", "Frontend"
        BACKEND = "backend", "Backend"
        DATABASE = "database", "Database"
        DEVOPS = "devops", "DevOps / hosting"
        DESIGN = "design", "Design"
        OTHER = "other", "Other"

    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=60, unique=True)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "technologies"

    def __str__(self) -> str:
        return self.name


class ProjectQuerySet(PublishedQuerySet):
    def featured(self) -> "ProjectQuerySet":
        return self.filter(is_featured=True)


class Project(TimeStampedModel):
    class Status(models.TextChoices):
        LIVE = "live", "Live"
        CONCEPT = "concept", "Concept"

    title = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150, unique=True)
    summary = models.CharField(max_length=300, blank=True, help_text="One-line card text.")
    client_name = models.CharField(max_length=150, blank=True)
    industry = models.CharField(max_length=100, blank=True)
    problem = models.TextField(blank=True, validators=[MaxLengthValidator(5000)])
    solution = models.TextField(blank=True, validators=[MaxLengthValidator(5000)])
    result_metrics = models.JSONField(
        default=list, blank=True, validators=[validate_result_metrics]
    )
    technologies = models.ManyToManyField(Technology, blank=True, related_name="projects")
    services = models.ManyToManyField(Service, blank=True, related_name="projects")
    live_url = models.URLField(blank=True, validators=[https_url])
    repo_url = models.URLField(blank=True, validators=[https_url])
    cover_image = models.ImageField(
        upload_to=UUIDUploadTo("projects/covers"), blank=True, validators=[image_validator]
    )
    cover_alt = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.CONCEPT)
    is_featured = models.BooleanField(default=False)
    published = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)

    objects = ProjectQuerySet.as_manager()

    class Meta:
        ordering = ["order", "-created_at"]
        indexes = [models.Index(fields=["published", "is_featured", "order"])]

    def __str__(self) -> str:
        return self.title

    def clean(self) -> None:
        super().clean()
        errors: dict[str, str] = {}
        if self.status == self.Status.LIVE and not self.live_url:
            errors["live_url"] = "A live project needs its live URL."
        if self.cover_image and not self.cover_alt.strip():
            errors["cover_alt"] = "Describe the cover image (alt text) for screen readers."
        if errors:
            raise ValidationError(errors)


class ProjectImage(models.Model):
    """Gallery image. Alt text is mandatory (WCAG 2.2 AA)."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="gallery")
    image = models.ImageField(
        upload_to=UUIDUploadTo("projects/gallery"), validators=[image_validator]
    )
    alt_text = models.CharField(max_length=200)
    caption = models.CharField(max_length=200, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return self.alt_text


class Testimonial(TimeStampedModel):
    author_name = models.CharField(max_length=100)
    author_role = models.CharField(max_length=100, blank=True)
    company = models.CharField(max_length=100, blank=True)
    quote = models.TextField(validators=[MaxLengthValidator(1000)])
    project = models.ForeignKey(
        Project, null=True, blank=True, on_delete=models.SET_NULL, related_name="testimonials"
    )
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    avatar = models.ImageField(
        upload_to=UUIDUploadTo("testimonials"), blank=True, validators=[image_validator]
    )
    published = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)

    objects = PublishedQuerySet.as_manager()

    class Meta:
        ordering = ["order", "-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(rating__isnull=True) | Q(rating__gte=1, rating__lte=5),
                name="testimonial_rating_1_to_5",
            )
        ]

    def __str__(self) -> str:
        return f"{self.author_name} ({self.company})" if self.company else self.author_name


class BlogPost(TimeStampedModel):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    excerpt = models.CharField(max_length=300, blank=True)
    body = models.TextField(help_text="HTML. Sanitised on save; scripts and handlers are removed.")
    cover_image = models.ImageField(
        upload_to=UUIDUploadTo("blog"), blank=True, validators=[image_validator]
    )
    cover_alt = models.CharField(max_length=200, blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)

    objects = PublishedQuerySet.as_manager()

    class Meta:
        ordering = ["-published_at", "-created_at"]

    def __str__(self) -> str:
        return self.title

    def clean(self) -> None:
        super().clean()
        if self.cover_image and not self.cover_alt.strip():
            raise ValidationError({"cover_alt": "Describe the cover image (alt text)."})

    def save(self, *args: Any, **kwargs: Any) -> None:
        # Sanitise on every save path (admin, shell, API), not just in forms.
        self.body = sanitize_rich_text(self.body)
        if self.published and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)
