"""/api/admin/clients: staff-only, OTP-verified. Clients exist only via invite."""

from django.db import transaction
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.emails import send_invite
from apps.accounts.models import User, normalize_email_address
from apps.core.audit import record
from apps.core.models import AuditLog
from apps.core.permissions import IsOTPVerifiedStaff

from .models import ClientProfile
from .serializers import AdminClientSerializer, ClientInviteSerializer


class AdminClientViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsOTPVerifiedStaff]
    serializer_class = AdminClientSerializer

    def get_queryset(self):  # type: ignore[no-untyped-def]
        return ClientProfile.objects.for_user(self.request.user).select_related("user")

    @action(detail=False, methods=["post"])
    def invite(self, request: Request) -> Response:
        """Create a client account with no password and email a 72h invite link."""
        data = ClientInviteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        email = normalize_email_address(data.validated_data["email"])
        if User.objects.filter(email__iexact=email).exists():
            return Response(
                {"email": ["An account with this email already exists."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            user = User.objects.create_user(
                email=email, password=None, full_name=data.validated_data.get("full_name", "")
            )
            profile = ClientProfile.objects.create(
                user=user, company=data.validated_data.get("company", "")
            )
            record(AuditLog.Action.ADMIN_ADD, request=request, actor=request.user, obj=profile,
                   message="api: client invited")  # fmt: skip
        send_invite(user)
        return Response(AdminClientSerializer(profile).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="resend-invite")
    def resend_invite(self, request: Request, pk: str | None = None) -> Response:
        profile = self.get_object()
        if profile.user.has_usable_password():
            return Response(
                {"detail": "This client has already set a password."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        send_invite(profile.user)
        record(AuditLog.Action.ADMIN_CHANGE, request=request, actor=request.user, obj=profile,
               message="api: invite re-sent")  # fmt: skip
        return Response(status=status.HTTP_204_NO_CONTENT)
