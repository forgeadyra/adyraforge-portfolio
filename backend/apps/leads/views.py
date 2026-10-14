"""Public lead capture: contact form and project planner (CLAUDE.md rules 8-10)."""

from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.security import request_ip_hash
from apps.core.throttling import AnonRateThrottle, ScopedRateThrottle
from apps.recommender.services import services_for

from .models import Lead, PlannerSubmission
from .serializers import UTM_FIELDS, ContactSerializer, PlannerSerializer
from .turnstile import verify_turnstile

THANKS = "Thanks, your message has been received."
VERIFICATION_FAILED = "We couldn't verify you're human. Please try again."


class _PublicFormView(APIView):
    # Public on purpose: anonymous visitors submit these forms. Each is guarded
    # by a strict throttle scope, a honeypot and server-side Turnstile.
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    serializer_class: Any

    def post(self, request: Request) -> Response:
        data = self.serializer_class(data=request.data)
        if data.is_bot:
            # Pretend success so bots don't learn to fill the field; store nothing.
            return Response({"detail": THANKS}, status=status.HTTP_201_CREATED)
        data.is_valid(raise_exception=True)
        if not verify_turnstile(data.validated_data["turnstile_token"]):
            return Response({"detail": VERIFICATION_FAILED}, status=status.HTTP_400_BAD_REQUEST)
        return self.handle(request, data)

    def handle(self, request: Request, data: Any) -> Response:
        raise NotImplementedError


class ContactView(_PublicFormView):
    permission_classes = [AllowAny]
    throttle_scope = "contact"
    serializer_class = ContactSerializer

    def handle(self, request: Request, data: ContactSerializer) -> Response:
        data.save(source=Lead.Source.CONTACT_FORM, ip_hash=request_ip_hash(request._request))
        return Response({"detail": THANKS}, status=status.HTTP_201_CREATED)


class PlannerView(_PublicFormView):
    permission_classes = [AllowAny]
    throttle_scope = "planner"
    serializer_class = PlannerSerializer

    def handle(self, request: Request, data: PlannerSerializer) -> Response:
        v = dict(data.validated_data)
        contact = v.pop("contact", None)
        utm = {k: v.pop(k) for k in UTM_FIELDS if k in v}
        v.pop("website", None)
        v.pop("turnstile_token", None)
        ip_hash = request_ip_hash(request._request)

        # Validate fully before writing anything, so a bad payload is a 400 and
        # never leaves a half-created lead behind.
        submission = PlannerSubmission(ip_hash=ip_hash, **v)
        try:
            submission.full_clean(exclude=["lead"])
        except DjangoValidationError as exc:
            return Response(exc.message_dict, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            lead = None
            if contact:
                lead = Lead.objects.create(
                    name=contact["name"],
                    email=contact["email"],
                    company=contact.get("company", ""),
                    message=contact.get("message") or "Submitted via the project planner.",
                    project_type=v["project_type"],
                    budget_range=v.get(
                        "budget_range", Lead._meta.get_field("budget_range").default
                    ),
                    timeline=v.get("timeline", Lead._meta.get_field("timeline").default),
                    source=Lead.Source.PLANNER,
                    ip_hash=ip_hash,
                    **utm,
                )
            submission.lead = lead
            submission.save()
            recommended = services_for(submission.project_type, submission.features)
            submission.recommended_services.set(recommended)
        return Response(
            {
                "id": submission.pk,
                "detail": THANKS,
                "recommended_services": [
                    {"name": s.name, "slug": s.slug, "summary": s.summary} for s in recommended
                ],
            },
            status=status.HTTP_201_CREATED,
        )
