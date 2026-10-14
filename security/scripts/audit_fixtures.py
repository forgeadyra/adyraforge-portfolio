"""Create throwaway audit accounts + data in the DEV database (idempotent).

Run inside the backend container:  python /tmp/audit/audit_fixtures.py
Writes random passwords and object ids to /tmp/audit_creds.json (mode 600).
"""

import json
import os
import secrets
import sys
from datetime import date
from decimal import Decimal

sys.path.insert(0, "/app/backend")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from axes.utils import reset  # noqa: E402
from django.core.files.base import ContentFile  # noqa: E402
from django_otp.plugins.otp_static.models import StaticDevice  # noqa: E402

from apps.accounts.models import User  # noqa: E402
from apps.clients.models import (  # noqa: E402
    ClientProfile,
    ClientProject,
    Invoice,
    Message,
    Milestone,
    ProjectFile,
)

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
out: dict = {}


def client(tag: str) -> dict:
    email = f"audit.{tag}@example.test"
    password = secrets.token_urlsafe(18)
    user, _ = User.objects.get_or_create(email=email)
    user.set_password(password)
    user.is_active, user.is_staff, user.is_superuser = True, False, False
    user.save()
    profile, _ = ClientProfile.objects.get_or_create(user=user, defaults={"company": f"Audit {tag}"})
    project, _ = ClientProject.objects.get_or_create(client=profile, title=f"Audit {tag} project")
    milestone, _ = Milestone.objects.get_or_create(client_project=project, title=f"{tag} milestone")
    message = project.messages.first() or Message.objects.create(
        client_project=project, sender=user, body=f"private note from {tag}"
    )
    file = project.files.first()
    if file is None:
        file = ProjectFile(client_project=project)
        file.file = ContentFile(PDF, name=f"{tag}-contract.pdf")
        file.save()
    invoice = Invoice.objects.filter(number=f"AUDIT-{tag.upper()}").first()
    if invoice is None:
        invoice = Invoice(
            client_project=project, number=f"AUDIT-{tag.upper()}", amount=Decimal("1000.00"),
            status=Invoice.Status.SENT, due_date=date(2026, 12, 31),
        )  # fmt: skip
        invoice.pdf = ContentFile(PDF, name=f"{tag}-invoice.pdf")
        invoice.save()
    reset(username=email)
    return {
        "email": email, "password": password, "project": project.pk, "milestone": milestone.pk,
        "message": message.pk, "file": file.pk, "invoice": invoice.pk,
    }  # fmt: skip


out["alice"] = client("alice")
out["bob"] = client("bob")

staff_email = "audit.staff@example.test"
staff_password = secrets.token_urlsafe(18)
staff, _ = User.objects.get_or_create(email=staff_email)
staff.set_password(staff_password)
staff.is_active = staff.is_staff = staff.is_superuser = True
staff.save()
StaticDevice.objects.filter(user=staff).delete()
device = StaticDevice.objects.create(user=staff, name="audit")
tokens = [secrets.token_hex(4) for _ in range(20)]
for t in tokens:
    device.token_set.create(token=t)
reset(username=staff_email)
out["staff"] = {"email": staff_email, "password": staff_password, "otp_tokens": tokens,
                "device": device.persistent_id}  # fmt: skip

path = "/tmp/audit_creds.json"  # noqa: S108
with open(path, "w", encoding="utf-8") as fh:
    json.dump(out, fh)
os.chmod(path, 0o600)
print("audit fixtures ready (credentials in", path + ", not printed)")
print("bob object ids:", {k: v for k, v in out["bob"].items() if k not in {"email", "password"}})
