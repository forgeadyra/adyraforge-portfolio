"""Public, read-only content API consumed by the Next.js site (ISR).

Only published rows are ever returned. No session/auth is consulted, so these
endpoints carry no user data and need no CSRF. A dedicated throttle scope keeps
scraping in check without starving the frontend's own revalidation.
"""

from django.db.models import QuerySet
from rest_framework import viewsets
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.throttling import ScopedRateThrottle

from .models import Project, Service, Technology, Testimonial
from .serializers import (
    ProjectCardSerializer,
    ProjectDetailSerializer,
    ServiceSerializer,
    TechnologySerializer,
    TestimonialSerializer,
)


class PublicMixin:
    # Public on purpose: published portfolio content for anonymous visitors.
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "public"
    pagination_class = None


class PublicProjectViewSet(PublicMixin, viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    lookup_field = "slug"

    def get_queryset(self) -> QuerySet:
        qs = Project.objects.published().prefetch_related("technologies", "services", "gallery")
        params = self.request.query_params
        if industry := params.get("industry"):
            qs = qs.filter(industry__iexact=industry[:100])
        if tech := params.get("tech"):
            qs = qs.filter(technologies__slug=tech[:60])
        if params.get("featured") == "1":
            qs = qs.filter(is_featured=True)
        return qs.distinct()

    def get_serializer_class(self):  # type: ignore[no-untyped-def]
        return ProjectDetailSerializer if self.action == "retrieve" else ProjectCardSerializer


class PublicServiceViewSet(PublicMixin, viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    lookup_field = "slug"
    serializer_class = ServiceSerializer

    def get_queryset(self) -> QuerySet:
        return Service.objects.published()


class PublicTechnologyList(PublicMixin, ListAPIView):
    """Technologies used by at least one published project (for Work filters)."""

    permission_classes = [AllowAny]
    serializer_class = TechnologySerializer

    def get_queryset(self) -> QuerySet:
        return Technology.objects.filter(projects__published=True).distinct()


class PublicTestimonialList(PublicMixin, ListAPIView):
    """Real, published testimonials only. Empty until real ones exist."""

    permission_classes = [AllowAny]
    serializer_class = TestimonialSerializer

    def get_queryset(self) -> QuerySet:
        return Testimonial.objects.published().select_related("project")
