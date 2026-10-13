from typing import Any

from rest_framework import serializers

from .models import ClientProfile, ClientProject, Invoice, Message, Milestone, ProjectFile


class MilestoneSerializer(serializers.ModelSerializer):
    is_complete = serializers.BooleanField(read_only=True)

    class Meta:
        model = Milestone
        fields = ("id", "title", "description", "due_date", "completed_at", "is_complete", "order")
        read_only_fields = fields


class ClientProjectListSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientProject
        fields = ("id", "title", "status", "progress", "start_date", "due_date", "updated_at")
        read_only_fields = fields


class ClientProjectDetailSerializer(serializers.ModelSerializer):
    milestones = MilestoneSerializer(many=True, read_only=True)

    class Meta:
        model = ClientProject
        fields = (
            "id",
            "title",
            "description",
            "status",
            "progress",
            "start_date",
            "due_date",
            "milestones",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()
    read = serializers.BooleanField(write_only=True, required=False)

    class Meta:
        model = Message
        fields = (
            "id",
            "client_project",
            "body",
            "sender_name",
            "is_mine",
            "read_at",
            "read",
            "created_at",
        )
        read_only_fields = (
            "id",
            "client_project",
            "sender_name",
            "is_mine",
            "read_at",
            "created_at",
        )
        # Plain text; the frontend renders it escaped. Never HTML.
        extra_kwargs = {"body": {"max_length": 5000, "trim_whitespace": True}}

    def get_sender_name(self, obj: Message) -> str:
        # In a client's own thread, anything not from a client account is from us.
        if obj.sender is None or obj.sender.is_staff:
            return "AdyraForge"
        return obj.sender.full_name or obj.sender.email

    def get_is_mine(self, obj: Message) -> bool:
        return obj.sender_id == self.context["request"].user.pk


class MessageCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ("body",)
        extra_kwargs = {"body": {"max_length": 5000, "trim_whitespace": True}}


class MessageReadSerializer(serializers.ModelSerializer):
    """The only client-writable message field: mark as read."""

    read = serializers.BooleanField(write_only=True)

    class Meta:
        model = Message
        fields = ("read",)

    def update(self, instance: Message, validated_data: dict[str, Any]) -> Message:
        from django.utils import timezone

        user = self.context["request"].user
        # Only messages someone else sent can be marked read.
        if validated_data["read"] and instance.sender_id != user.pk and instance.read_at is None:
            instance.read_at = timezone.now()
            instance.save(update_fields=["read_at", "updated_at"])
        return instance


class ProjectFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectFile
        fields = (
            "id",
            "client_project",
            "original_name",
            "description",
            "content_type",
            "size",
            "created_at",
        )
        read_only_fields = fields


class InvoiceSerializer(serializers.ModelSerializer):
    has_pdf = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = (
            "id",
            "client_project",
            "number",
            "amount",
            "currency",
            "status",
            "issued_on",
            "due_date",
            "paid_at",
            "has_pdf",
        )
        read_only_fields = fields

    def get_has_pdf(self, obj: Invoice) -> bool:
        return bool(obj.pdf)


class AdminClientSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    has_password = serializers.SerializerMethodField()

    class Meta:
        model = ClientProfile
        fields = ("id", "email", "full_name", "company", "phone", "has_password", "created_at")
        read_only_fields = fields

    def get_has_password(self, obj: ClientProfile) -> bool:
        return obj.user.has_usable_password()


class ClientInviteSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    full_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    company = serializers.CharField(max_length=150, required=False, allow_blank=True)
