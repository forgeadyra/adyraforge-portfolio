from typing import Any

from rest_framework import serializers

from .models import Lead, PlannerSubmission

UTM_FIELDS = ("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content")


class BotCheckMixin(serializers.Serializer):
    # Honeypot: hidden from humans by the form, so any value means a bot.
    website = serializers.CharField(
        required=False, allow_blank=True, write_only=True, max_length=200
    )
    turnstile_token = serializers.CharField(write_only=True, max_length=2048)

    @property
    def is_bot(self) -> bool:
        # Non-object bodies (e.g. a JSON array) are not bots; validation rejects them.
        data = self.initial_data
        return isinstance(data, dict) and bool(data.get("website"))


class ContactSerializer(BotCheckMixin, serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = (
            "name", "email", "company", "budget_range", "project_type", "timeline", "message",
            *UTM_FIELDS, "website", "turnstile_token",
        )  # fmt: skip
        extra_kwargs = {"message": {"max_length": 5000}}

    def create(self, validated_data: dict[str, Any]) -> Lead:
        validated_data.pop("website", None)
        validated_data.pop("turnstile_token", None)
        return Lead.objects.create(**validated_data)


class PlannerContactSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    email = serializers.EmailField(max_length=254)
    company = serializers.CharField(max_length=150, required=False, allow_blank=True)
    message = serializers.CharField(max_length=5000, required=False, allow_blank=True)


class PlannerSerializer(BotCheckMixin, serializers.ModelSerializer):
    features = serializers.ListField(
        child=serializers.CharField(max_length=60), max_length=30, required=False
    )
    contact = PlannerContactSerializer(required=False, write_only=True)

    class Meta:
        model = PlannerSubmission
        fields = (
            "id", "project_type", "budget_range", "timeline", "page_count", "features",
            "answers", "currency", "contact", *UTM_FIELDS, "website", "turnstile_token",
        )  # fmt: skip
        read_only_fields = ("id",)

    # UTM fields live on Lead; accept them here so the planner can attribute.
    utm_source = serializers.CharField(max_length=100, required=False, allow_blank=True)
    utm_medium = serializers.CharField(max_length=100, required=False, allow_blank=True)
    utm_campaign = serializers.CharField(max_length=100, required=False, allow_blank=True)
    utm_term = serializers.CharField(max_length=100, required=False, allow_blank=True)
    utm_content = serializers.CharField(max_length=100, required=False, allow_blank=True)
