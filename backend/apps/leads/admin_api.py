"""/api/admin/leads: staff-only, OTP-verified lead pipeline management."""

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import mixins, serializers, viewsets

from apps.core.audit import record
from apps.core.models import AuditLog
from apps.core.permissions import IsOTPVerifiedStaff

from .models import Lead


class AdminLeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = (
            "id", "name", "email", "company", "budget_range", "project_type", "timeline",
            "message", "source", "utm_source", "utm_medium", "utm_campaign", "status",
            "status_changed_at", "score", "internal_notes", "created_at",
        )  # fmt: skip
        # Only status, score and internal_notes are editable; what the visitor sent is not.
        read_only_fields = (
            "id", "name", "email", "company", "budget_range", "project_type", "timeline",
            "message", "source", "utm_source", "utm_medium", "utm_campaign",
            "status_changed_at", "created_at",
        )  # fmt: skip


class AdminLeadViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsOTPVerifiedStaff]
    serializer_class = AdminLeadSerializer
    queryset = Lead.objects.all()

    def get_queryset(self):  # type: ignore[no-untyped-def]
        qs = super().get_queryset()
        if (lead_status := self.request.query_params.get("status")) in Lead.Status.values:
            qs = qs.filter(status=lead_status)
        return qs

    def perform_update(self, serializer: AdminLeadSerializer) -> None:
        try:
            lead = serializer.save()
        except DjangoValidationError as exc:  # pipeline transition rules
            raise serializers.ValidationError(exc.message_dict) from exc
        changed = ", ".join(
            f"{k}={v}" for k, v in serializer.validated_data.items() if k != "internal_notes"
        )
        record(AuditLog.Action.ADMIN_CHANGE, request=self.request, actor=self.request.user,
               obj=lead, message=f"api: {changed or 'notes'}")  # fmt: skip
