"""Client files and invoices in a PRIVATE S3-compatible bucket (production backend).

Runs the real django-storages S3Storage against moto's in-process S3, so uploads,
ACLs and presigned URLs are exercised for real, offline. Ownership is still decided
by our signed link before any bucket URL exists.
"""

from urllib.parse import parse_qs, urlparse

import boto3
import pytest
from moto import mock_aws
from storages.backends.s3 import S3Storage

from apps.clients.models import Invoice, ProjectFile

BUCKET = "adyraforge-private-test"
RESOURCES = {"files": "file", "invoices": "invoice"}


@pytest.fixture
def bucket(monkeypatch):
    """Swap the private storage for a real S3Storage on a mocked private bucket."""
    for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"):
        monkeypatch.setenv(key, "testing")
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=BUCKET)
        storage = S3Storage(
            bucket_name=BUCKET, access_key="testing", secret_key="testing",
            region_name="us-east-1", signature_version="s3v4", default_acl="private",
            querystring_auth=True, querystring_expire=60, file_overwrite=False,
        )  # fmt: skip
        for model, field in ((ProjectFile, "file"), (Invoice, "pdf")):
            monkeypatch.setattr(model._meta.get_field(field), "storage", storage)
        yield s3


def presigned(portal, who: str, resource: str):
    obj = portal[who][RESOURCES[resource]]
    link = portal[who]["client"].get(f"/api/portal/{resource}/{obj.pk}/download/").json()["url"]
    return obj, link


def test_uploads_land_in_the_private_bucket_without_public_grants(bucket, portal) -> None:
    keys = sorted(o["Key"] for o in bucket.list_objects_v2(Bucket=BUCKET)["Contents"])
    assert len(keys) == 4  # alice + bob: one file and one invoice each
    assert all(k.startswith(("client-files/", "invoices/")) for k in keys)
    assert not any("brief" in k or "alice" in k for k in keys)  # UUID names only
    for key in keys:
        grants = bucket.get_object_acl(Bucket=BUCKET, Key=key)["Grants"]
        assert not any("AllUsers" in str(g) or "AuthenticatedUsers" in str(g) for g in grants)


@pytest.mark.parametrize("resource", ["files", "invoices"])
def test_owner_gets_a_60_second_presigned_attachment(bucket, portal, resource) -> None:
    obj, link = presigned(portal, "alice", resource)
    resp = portal["alice"]["client"].get(link)
    assert resp.status_code == 302
    assert resp["Cache-Control"] == "private, no-store"
    assert resp["Referrer-Policy"] == "no-referrer"

    url = urlparse(resp["Location"])
    query = parse_qs(url.query)
    assert url.scheme == "https" and BUCKET in url.netloc + url.path
    assert query["X-Amz-Expires"] == ["60"]
    assert "X-Amz-Signature" in query
    assert query["response-content-disposition"][0].startswith("attachment; filename=")

    # The bytes really are in the bucket. (Fetching through the presigned URL itself,
    # anonymous denial and expiry are checked against a real S3 server in the audit.)
    key = getattr(obj, "file" if resource == "files" else "pdf").name
    body = bucket.get_object(Bucket=BUCKET, Key=key)["Body"].read()
    assert body.startswith(b"%PDF")


@pytest.mark.parametrize("resource", ["files", "invoices"])
def test_bobs_link_never_yields_a_bucket_url_for_alice(bucket, portal, resource) -> None:
    _, bobs_link = presigned(portal, "bob", resource)
    resp = portal["alice"]["client"].get(bobs_link)
    assert resp.status_code == 404
    assert "Location" not in resp


@pytest.mark.parametrize("resource", ["files", "invoices"])
def test_other_clients_download_endpoint_is_404_with_bucket(bucket, portal, resource) -> None:
    bob_obj = portal["bob"][RESOURCES[resource]]
    resp = portal["alice"]["client"].get(f"/api/portal/{resource}/{bob_obj.pk}/download/")
    assert resp.status_code == 404


def test_anonymous_cannot_use_a_valid_link(bucket, portal, client) -> None:
    _, link = presigned(portal, "alice", "files")
    resp = client.get(link)
    assert resp.status_code in (401, 403)
    assert "Location" not in resp
