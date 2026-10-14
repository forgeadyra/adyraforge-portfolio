"""Seed honesty: MediCare Plus and mentality are concepts, never featured as client work.

The seed never overwrites admin edits, so databases seeded before this change are
corrected here once. Only these two rows, only these fields.
"""

from django.db import migrations

MEDICARE_SUMMARY = "Hospital website concept with a 4-step booking flow (front-end prototype)"
MEDICARE_SOLUTION = (
    "A front-end prototype of a multi-specialty hospital website: department "
    "pages and a 4-step appointment booking flow. Not built for a real hospital."
)


def forwards(apps, schema_editor):
    Project = apps.get_model("portfolio", "Project")
    Project.objects.filter(slug__in=["medicare-plus", "mentality-landing-page"]).update(
        kind="concept", is_featured=False, client_name=""
    )
    Project.objects.filter(slug="medicare-plus").update(
        summary=MEDICARE_SUMMARY, solution=MEDICARE_SOLUTION
    )


class Migration(migrations.Migration):
    dependencies = [("portfolio", "0004_public_image_decode_validation")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
