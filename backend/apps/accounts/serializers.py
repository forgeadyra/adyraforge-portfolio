from typing import Any

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import User


class MeSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "email", "full_name", "role")
        read_only_fields = fields

    def get_role(self, obj: User) -> str:
        return "admin" if obj.is_staff else "client"


def password_field() -> serializers.CharField:
    return serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = password_field()
    otp_token = serializers.CharField(
        required=False, allow_blank=True, max_length=16, write_only=True
    )


class PasswordChangeSerializer(serializers.Serializer):
    current_password = password_field()
    new_password = password_field()

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        user: User = self.context["request"].user
        if not user.check_password(attrs["current_password"]):
            raise serializers.ValidationError({"current_password": "Incorrect password."})
        try:
            # Django's validators, incl. min length 12 and the common-password list.
            password_validation.validate_password(attrs["new_password"], user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": exc.messages}) from exc
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField(max_length=64)
    token = serializers.CharField(max_length=128)
    new_password = password_field()


class InviteAcceptSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=512)
    new_password = password_field()
