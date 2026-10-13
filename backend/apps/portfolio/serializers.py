from typing import Any

from rest_framework import serializers

from .models import Project, ProjectImage, Service, Technology, Testimonial


def file_url(field: Any) -> str | None:
    # MEDIA_URL is absolute in every deployed environment (Cloudinary/S3 or the
    # dev API origin), so this is safe to hand straight to the browser.
    return field.url if field else None


class TechnologySerializer(serializers.ModelSerializer):
    class Meta:
        model = Technology
        fields = ("name", "slug", "category")


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = (
            "name",
            "slug",
            "summary",
            "description",
            "includes",
            "price_from_inr",
            "price_from_usd",
        )


class ServiceRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ("name", "slug")


class ProjectCardSerializer(serializers.ModelSerializer):
    technologies = TechnologySerializer(many=True, read_only=True)
    services = ServiceRefSerializer(many=True, read_only=True)
    cover_image = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = (
            "slug",
            "title",
            "summary",
            "industry",
            "kind",
            "status",
            "is_featured",
            "live_url",
            "cover_image",
            "cover_alt",
            "technologies",
            "services",
            "lighthouse",
            "updated_at",
        )

    lighthouse = serializers.SerializerMethodField()

    def get_lighthouse(self, obj: Project) -> dict[str, Any] | None:
        data = obj.lighthouse
        return {**data, "measured_on": data["measured_on"].isoformat()} if data else None

    def get_cover_image(self, obj: Project) -> str | None:
        return file_url(obj.cover_image)


class GalleryImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = ProjectImage
        fields = ("image", "alt_text", "caption")

    def get_image(self, obj: ProjectImage) -> str | None:
        return file_url(obj.image)


class ProjectDetailSerializer(ProjectCardSerializer):
    gallery = GalleryImageSerializer(many=True, read_only=True)
    similar = serializers.SerializerMethodField()

    class Meta(ProjectCardSerializer.Meta):
        fields = (
            *ProjectCardSerializer.Meta.fields,
            "client_name",
            "problem",
            "solution",
            "result_metrics",
            "results_note",
            "repo_url",
            "gallery",
            "similar",
            "created_at",
        )

    def get_similar(self, obj: Project) -> list[dict[str, Any]]:
        from apps.recommender.services import similar_to

        return ProjectCardSerializer(similar_to(obj), many=True).data


class TestimonialSerializer(serializers.ModelSerializer):
    project = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = Testimonial
        fields = ("author_name", "author_role", "company", "quote", "rating", "project", "avatar")

    def get_avatar(self, obj: Testimonial) -> str | None:
        return file_url(obj.avatar)
