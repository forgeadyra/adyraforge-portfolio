"""Private-bucket check against a REAL S3 server (throwaway local S3 server), dev database.

What moto cannot show: that the bucket refuses anonymous reads and listing, that the
presigned URL our download view redirects to really serves the file as an attachment,
and that tampered or expired signatures are refused. Uses the same S3Storage options
as config/settings/production.py. Run inside the backend container:
    AUDIT_S3=http://af-s3:8333 python bucket_live_check.py
"""

import os
import sys
import time
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

sys.path.insert(0, "/app/backend")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

import boto3  # noqa: E402
import requests  # noqa: E402
from audit_common import check, done  # noqa: E402
from django.core.files.base import ContentFile  # noqa: E402
from django.test import Client  # noqa: E402
from storages.backends.s3 import S3Storage  # noqa: E402

from apps.accounts.models import User  # noqa: E402
from apps.clients.models import ClientProfile, ClientProject, ProjectFile  # noqa: E402

ENDPOINT = os.environ["AUDIT_S3"]
KEY, SECRET = os.environ["AUDIT_S3_KEY"], os.environ["AUDIT_S3_SECRET"]
BUCKET = "adyraforge-private-live"
PDF = b"%PDF-1.4\n% live bucket check\n%%EOF\n"

s3 = boto3.client("s3", endpoint_url=ENDPOINT, aws_access_key_id=KEY,
                  aws_secret_access_key=SECRET, region_name="us-east-1")  # fmt: skip
s3.create_bucket(Bucket=BUCKET)
# Same options as production.py's STORAGES["private"] (endpoint/region differ).
storage = S3Storage(
    bucket_name=BUCKET, access_key=KEY, secret_key=SECRET, endpoint_url=ENDPOINT,
    region_name="us-east-1", signature_version="s3v4", file_overwrite=False,
    default_acl="private", querystring_auth=True, querystring_expire=60, custom_domain=None,
)  # fmt: skip

print("== the bucket itself ==")
name = storage.save("client-files/live-check.pdf", ContentFile(PDF))
plain = f"{ENDPOINT}/{BUCKET}/{name}"
r = requests.get(plain, timeout=10)
check("anonymous GET of an object is refused", r.status_code == 403, f"{r.status_code}")
r = requests.get(f"{ENDPOINT}/{BUCKET}/", timeout=10)
check("anonymous bucket listing is refused", r.status_code == 403, f"{r.status_code}")

url = storage.url(name, parameters={"ResponseContentDisposition": 'attachment; filename="x.pdf"',
                                    "ResponseContentType": "application/pdf"}, expire=60)  # fmt: skip
r = requests.get(url, timeout=10)
check("presigned URL serves the exact bytes", r.status_code == 200 and r.content == PDF,
      f"{r.status_code} {len(r.content)}B")  # fmt: skip
check("served as an attachment, not inline",
      r.headers.get("Content-Disposition", "").startswith("attachment"),
      r.headers.get("Content-Disposition", ""))  # fmt: skip
check("X-Amz-Expires is 60 s", parse_qs(urlparse(url).query).get("X-Amz-Expires") == ["60"])

parts = urlparse(url)
q = parse_qs(parts.query)
sig = q["X-Amz-Signature"][0]
q["X-Amz-Signature"] = [("0" if sig[0] != "0" else "1") + sig[1:]]
tampered = urlunparse(parts._replace(query=urlencode({k: v[0] for k, v in q.items()})))
r = requests.get(tampered, timeout=10)
check("tampered signature is refused", r.status_code == 403, f"{r.status_code}")

q = parse_qs(parts.query)
q["X-Amz-Expires"] = ["3600"]
stretched = urlunparse(parts._replace(query=urlencode({k: v[0] for k, v in q.items()})))
r = requests.get(stretched, timeout=10)
check("extending X-Amz-Expires invalidates the signature", r.status_code == 403, f"{r.status_code}")

short = storage.url(name, expire=1)
time.sleep(3)
r = requests.get(short, timeout=10)
check("expired presigned URL is refused", r.status_code == 403, f"{r.status_code}")

print("\n== end to end through the Django download view ==")
field = ProjectFile._meta.get_field("file")
original_storage = field.storage
field.storage = storage
owner = User.objects.create_user(email="bucket.owner@example.test", password="x" * 20)  # noqa: S106
other = User.objects.create_user(email="bucket.other@example.test", password="x" * 20)  # noqa: S106
try:
    project = ClientProject.objects.create(
        client=ClientProfile.objects.create(user=owner), title="bucket live check"
    )
    ClientProfile.objects.create(user=other)
    pf = ProjectFile.objects.create(client_project=project, file=ContentFile(PDF, name="brief.pdf"))
    alice, mallory = Client(), Client()
    alice.force_login(owner)
    mallory.force_login(other)
    link = alice.get(f"/api/portal/files/{pf.pk}/download/", HTTP_HOST="localhost").json()["url"]
    path = urlparse(link).path
    resp = alice.get(path, HTTP_HOST="localhost")
    check("owner: signed link -> 302 to the bucket", resp.status_code == 302, str(resp.status_code))
    r = requests.get(resp["Location"], timeout=10)
    check("following the redirect downloads the file", r.status_code == 200 and r.content == PDF,
          f"{r.status_code}")  # fmt: skip
    resp = mallory.get(path, HTTP_HOST="localhost")
    check("another client with the same link: 404, no bucket URL",
          resp.status_code == 404 and "Location" not in resp, str(resp.status_code))  # fmt: skip
    resp = mallory.get(f"/api/portal/files/{pf.pk}/download/", HTTP_HOST="localhost")
    check("another client asking for a link: 404", resp.status_code == 404, str(resp.status_code))
finally:
    # Dependency order: client projects are PROTECTed from cascading deletes.
    ProjectFile.objects.filter(client_project__title="bucket live check").delete()
    ClientProject.objects.filter(title="bucket live check").delete()
    ClientProfile.objects.filter(user__email__startswith="bucket.").delete()
    User.objects.filter(email__startswith="bucket.").delete()
    field.storage = original_storage
done()
