from typing import Any

from rest_framework.permissions import BasePermission
from rest_framework.request import Request


class IsClient(BasePermission):
    """An active, non-staff user with a client profile. Staff use the admin API."""

    def has_permission(self, request: Request, view: Any) -> bool:
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and not user.is_staff
            and hasattr(user, "client_profile")
        )


class IsClientOwner(BasePermission):
    """Object-level check that the object belongs to request.user.

    Defence in depth: portal querysets are already filtered with owned_by(), so a
    foreign object 404s before this runs. This catches any view that forgets.
    """

    def has_object_permission(self, request: Request, view: Any, obj: Any) -> bool:
        from apps.clients.models import owner_of

        return owner_of(obj) == request.user


class IsOTPVerifiedStaff(BasePermission):
    """Staff whose session passed TOTP/static-token verification (django-otp)."""

    def has_permission(self, request: Request, view: Any) -> bool:
        user = request.user
        if not (user and user.is_authenticated and user.is_active and user.is_staff):
            return False
        is_verified = getattr(user, "is_verified", None)
        return bool(callable(is_verified) and is_verified())
