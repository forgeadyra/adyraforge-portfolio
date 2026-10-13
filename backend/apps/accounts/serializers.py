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
