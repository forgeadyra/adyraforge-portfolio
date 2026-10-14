"""Seed XSS payloads into every text field that reaches a rendered page (DEV database).

Each payload sets window.__xss if it ever executes. `--cleanup` removes it all.
"""

import os
import sys

sys.path.insert(0, "/app/backend")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from apps.clients.models import ClientProject, Message  # noqa: E402
from apps.leads.models import Lead  # noqa: E402
from apps.portfolio.models import Project, Service, Technology, Testimonial  # noqa: E402

PAYLOADS = [
    '<script>window.__xss="script"</script>',
    '<img src=x onerror="window.__xss=\'img\'">',
    '"><svg onload="window.__xss=\'svg\'">',
    "</script><script>window.__xss='ldjson-breakout'</script>",
    "javascript:window.__xss='js-url'",
    "{{constructor.constructor('window.__xss=1')()}}",
]
P = " ".join(PAYLOADS)


def cleanup() -> None:
    Project.objects.filter(slug="xss-probe").delete()
    Technology.objects.filter(slug="xss-tech").delete()
    Service.objects.filter(slug="xss-service").delete()
    Testimonial.objects.filter(company__startswith="XSS").delete()
    Lead.objects.filter(email="xss@example.test").delete()
    Message.objects.filter(body__startswith="XSS ").delete()
    print("xss probe data removed")


if "--cleanup" in sys.argv:
    cleanup()
    raise SystemExit

cleanup()
tech = Technology.objects.create(name=PAYLOADS[1][:60], slug="xss-tech")
service = Service.objects.create(
    name=PAYLOADS[0][:100], slug="xss-service", summary=P[:300], description=P,
    includes=[p[:80] for p in PAYLOADS], published=True, order=99,
)  # fmt: skip
project = Project.objects.create(
    slug="xss-probe", kind=Project.Kind.CLIENT, title=PAYLOADS[1][:150], summary=P[:300],
    client_name=PAYLOADS[2][:150], industry=PAYLOADS[0][:100], problem=P, solution=P,
    results_note=P[:1000], result_metrics=[{"label": PAYLOADS[0][:60], "value": PAYLOADS[1][:60]}],
    published=True, is_featured=True, order=0,
)  # fmt: skip
project.technologies.add(tech)
project.services.add(service)
Testimonial.objects.create(author_name=PAYLOADS[1][:100], author_role=PAYLOADS[2][:100],
                           company="XSS " + PAYLOADS[0][:90], quote=P, published=True)  # fmt: skip
Lead.objects.create(name=PAYLOADS[1][:120], email="xss@example.test", company=PAYLOADS[0][:150],
                    project_type="other", message=P, utm_source=PAYLOADS[2][:100])  # fmt: skip
alice_project = ClientProject.objects.get(client__user__email="audit.alice@example.test")
Message.objects.create(client_project=alice_project, body="XSS " + P)
print("seeded payloads into project 'xss-probe', a technology, a service, a testimonial,")
print("a lead and alice's message thread")
