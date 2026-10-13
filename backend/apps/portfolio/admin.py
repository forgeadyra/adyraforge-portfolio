from django.contrib import admin

from apps.core.admin import AuditedModelAdmin

from .models import BlogPost, Project, ProjectImage, Service, Technology, Testimonial


@admin.register(Service)
class ServiceAdmin(AuditedModelAdmin):
    list_display = ("name", "published", "order", "updated_at")
    list_filter = ("published",)
    list_editable = ("order",)
    search_fields = ("name", "summary")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Technology)
class TechnologyAdmin(AuditedModelAdmin):
    list_display = ("name", "category")
    list_filter = ("category",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


class ProjectImageInline(admin.TabularInline):
    model = ProjectImage
    extra = 0
    fields = ("image", "alt_text", "caption", "order")


@admin.register(Project)
class ProjectAdmin(AuditedModelAdmin):
    list_display = ("title", "status", "industry", "published", "is_featured", "order")
    list_filter = ("status", "published", "is_featured", "technologies", "services")
    list_editable = ("order",)
    search_fields = ("title", "client_name", "industry", "summary")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("technologies", "services")
    inlines = [ProjectImageInline]
    fieldsets = (
        (
            None,
            {"fields": ("title", "slug", "summary", "status", "published", "is_featured", "order")},
        ),
        ("Client", {"fields": ("client_name", "industry")}),
        ("Case study", {"fields": ("problem", "solution", "result_metrics")}),
        ("Stack & links", {"fields": ("technologies", "services", "live_url", "repo_url")}),
        ("Cover", {"fields": ("cover_image", "cover_alt")}),
        ("Audit", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(Testimonial)
class TestimonialAdmin(AuditedModelAdmin):
    list_display = ("author_name", "company", "project", "rating", "published", "order")
    list_filter = ("published", "rating")
    search_fields = ("author_name", "company", "quote")
    autocomplete_fields = ("project",)


@admin.register(BlogPost)
class BlogPostAdmin(AuditedModelAdmin):
    list_display = ("title", "published", "published_at", "author")
    list_filter = ("published",)
    search_fields = ("title", "excerpt", "body")
    prepopulated_fields = {"slug": ("title",)}
    date_hierarchy = "created_at"
    audit_readonly_fields = ("created_at", "updated_at", "published_at")
