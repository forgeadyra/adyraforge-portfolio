"""Session auth API (CLAUDE.md rules 3-8). No public registration exists."""

import logging
import threading
from collections.abc import Callable
from typing import Any

from django.conf import settings
from django.contrib.auth import (
    authenticate,
    login,
    logout,
    password_validation,
    update_session_auth_hash,
)
from django.contrib.auth.signals import user_login_failed
from django.core.exceptions import ValidationError as DjangoValidationError
from django_otp import login as otp_login
from django_otp import match_token, user_has_device
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.throttling import AnonRateThrottle, ScopedRateThrottle, UserRateThrottle

from .emails import send_password_reset
from .lockout import lockout_response
from .models import User
from .serializers import (
    InviteAcceptSerializer,
    LoginSerializer,
    MeSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
)
from .tokens import check_invite_token, check_reset_pair

log = logging.getLogger(__name__)

INVALID_CREDENTIALS = "Invalid email or password."
INVALID_LINK = "This link is invalid or has expired."
RESET_ACCEPTED = "If an account exists for that email, we've sent a reset link."

SCOPED = [AnonRateThrottle, UserRateThrottle, ScopedRateThrottle]


def _defer(fn: Callable[..., Any], *args: Any) -> None:
    """Run fn off the request thread when EMAIL_SEND_ASYNC, so response time
    can't reveal whether an email was actually sent."""

    def run() -> None:
        try:
            fn(*args)
        except Exception:  # never leak to the client; log for Sentry
            log.exception("Deferred email failed")

    if settings.EMAIL_SEND_ASYNC:
        threading.Thread(target=run, daemon=True).start()
    else:
        run()


def _set_new_password(user: User, password: str) -> Response | None:
    try:
        password_validation.validate_password(password, user)
    except DjangoValidationError as exc:
        return Response({"new_password": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
    user.set_password(password)
    user.save(update_fields=["password"])
    return None


class MeView(APIView):
    """The signed-in user's own profile. There is deliberately no lookup by id."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response(MeSerializer(request.user).data)


class LoginView(APIView):
    # Public on purpose: this is how users authenticate. Protected by the
    # "login" throttle scope and django-axes lockout (5 failures / 30 min).
    permission_classes = [AllowAny]
    throttle_classes = SCOPED
    throttle_scope = "login"

    def post(self, request: Request) -> Response:
        data = LoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        email, password = data.validated_data["email"], data.validated_data["password"]
        # axes and the session must act on the underlying HttpRequest.
        http_request = request._request

        user = authenticate(http_request, username=email, password=password)
        if getattr(http_request, "axes_locked_out", False):
            return lockout_response(http_request)
        if user is None:
            return Response({"detail": INVALID_CREDENTIALS}, status=status.HTTP_400_BAD_REQUEST)

        device = None
        if user_has_device(user):
            token = data.validated_data.get("otp_token") or ""
            if not token:
                return Response(
                    {"detail": "Enter your authenticator code.", "otp_required": True},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            device = match_token(user, token)
            if device is None:
                # Counts towards the axes lockout like a wrong password.
                user_login_failed.send(
                    sender=__name__, credentials={"username": user.email}, request=http_request
                )
                return Response(
                    {"detail": "Invalid authenticator code.", "otp_required": True},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        login(http_request, user)  # rotates the session key and the CSRF token
        if device is not None:
            otp_login(http_request, device)
        return Response(MeSerializer(user).data)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        logout(request._request)  # deletes the session server-side
        return Response(status=status.HTTP_204_NO_CONTENT)


class LogoutAllView(APIView):
    """Invalidate every session for this user, on every device, including this one."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        user: User = request.user  # type: ignore[assignment]
        user.revoke_all_sessions()
        logout(request._request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = SCOPED
    throttle_scope = "password_change"

    def post(self, request: Request) -> Response:
        data = PasswordChangeSerializer(data=request.data, context={"request": request})
        data.is_valid(raise_exception=True)
        user: User = request.user  # type: ignore[assignment]
        user.set_password(data.validated_data["new_password"])
        user.save(update_fields=["password"])
        # Keep this session; every other session's hash no longer matches.
        update_session_auth_hash(request._request, user)
        return Response({"detail": "Password updated."})


class PasswordResetRequestView(APIView):
    # Public on purpose: users who forgot their password aren't signed in.
    # Same response whether or not the email exists (no account enumeration).
    permission_classes = [AllowAny]
    throttle_classes = SCOPED
    throttle_scope = "password_reset"

    def post(self, request: Request) -> Response:
        data = PasswordResetRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = User.objects.filter(
            email__iexact=data.validated_data["email"].strip(), is_active=True
        ).first()
        if user is not None and user.has_usable_password():
            _defer(send_password_reset, user)
        return Response({"detail": RESET_ACCEPTED}, status=status.HTTP_202_ACCEPTED)


class PasswordResetConfirmView(APIView):
    # Public on purpose: the signed, single-use, 1-hour token is the credential.
    permission_classes = [AllowAny]
    throttle_classes = SCOPED
    throttle_scope = "password_reset_confirm"

    def post(self, request: Request) -> Response:
        data = PasswordResetConfirmSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = check_reset_pair(data.validated_data["uid"], data.validated_data["token"])
        if user is None:
            return Response({"detail": INVALID_LINK}, status=status.HTTP_400_BAD_REQUEST)
        if (error := _set_new_password(user, data.validated_data["new_password"])) is not None:
            return error
        return Response({"detail": "Password updated. You can now sign in."})


class InviteAcceptView(APIView):
    # Public on purpose: the signed, single-use, 72-hour invite token is the
    # credential. This is the only way a client account gets a password.
    permission_classes = [AllowAny]
    throttle_classes = SCOPED
    throttle_scope = "invite_accept"

    def post(self, request: Request) -> Response:
        data = InviteAcceptSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = check_invite_token(data.validated_data["token"])
        if user is None:
            return Response({"detail": INVALID_LINK}, status=status.HTTP_400_BAD_REQUEST)
        if (error := _set_new_password(user, data.validated_data["new_password"])) is not None:
            return error
        return Response({"detail": "Password set. You can now sign in."})
