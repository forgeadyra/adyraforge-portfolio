"""MANDATORY: client A cannot list, read, update or download client B's data.

Every attempt on another client's object must be a 404 (never 403 or 405),
so the API doesn't even confirm the object exists.
"""

import pytest

pytestmark = pytest.mark.django_db

RESOURCES = {
    "projects": "project",
    "messages": "message",
    "files": "file",
    "invoices": "invoice",
}
WRITE_METHODS = ["put", "patch", "delete"]


def ids(resp) -> set[int]:
    return {row["id"] for row in resp.json()["results"]}


@pytest.mark.parametrize("resource", RESOURCES)
def test_list_never_includes_other_clients_rows(portal, resource: str) -> None:
    key = RESOURCES[resource]
    alice, bob = portal["alice"], portal["bob"]
    resp = alice["client"].get(f"/api/portal/{resource}/")
    assert resp.status_code == 200
    assert ids(resp) == {alice[key].pk}
    assert bob[key].pk not in ids(resp)


@pytest.mark.parametrize("resource", ["messages", "files", "invoices"])
def test_filtering_by_another_clients_project_returns_nothing(portal, resource: str) -> None:
    bob_project = portal["bob"]["project"].pk
    resp = portal["alice"]["client"].get(f"/api/portal/{resource}/", {"project": bob_project})
    assert resp.status_code == 200
    assert ids(resp) == set()


@pytest.mark.parametrize("resource", RESOURCES)
def test_read_other_clients_object_is_404(portal, resource: str) -> None:
    bob_obj = portal["bob"][RESOURCES[resource]]
    resp = portal["alice"]["client"].get(f"/api/portal/{resource}/{bob_obj.pk}/")
    assert resp.status_code == 404


@pytest.mark.parametrize("method", WRITE_METHODS)
@pytest.mark.parametrize("resource", RESOURCES)
def test_update_or_delete_other_clients_object_is_404(portal, resource: str, method: str) -> None:
    bob_obj = portal["bob"][RESOURCES[resource]]
    client = portal["alice"]["client"]
    resp = getattr(client, method)(
        f"/api/portal/{resource}/{bob_obj.pk}/",
        {"read": True, "title": "pwned"},
        content_type="application/json",
    )
    assert resp.status_code == 404, f"{method.upper()} {resource}"
    bob_obj.refresh_from_db()  # still exists, unchanged


@pytest.mark.parametrize("resource", ["files", "invoices"])
def test_download_other_clients_file_is_404(portal, resource: str) -> None:
    bob_obj = portal["bob"][RESOURCES[resource]]
    resp = portal["alice"]["client"].get(f"/api/portal/{resource}/{bob_obj.pk}/download/")
    assert resp.status_code == 404


@pytest.mark.parametrize("method", ["get", "post"])
def test_other_clients_message_thread_is_404(portal, method: str) -> None:
    bob_project = portal["bob"]["project"]
    resp = getattr(portal["alice"]["client"], method)(
        f"/api/portal/projects/{bob_project.pk}/messages/",
        {"body": "injected"},
        content_type="application/json",
    )
    assert resp.status_code == 404
    assert not bob_project.messages.filter(body="injected").exists()


@pytest.mark.parametrize("resource", ["files", "invoices"])
def test_bobs_signed_link_is_useless_to_alice(portal, resource: str) -> None:
    bob = portal["bob"]
    link = bob["client"].get(f"/api/portal/{resource}/{bob[RESOURCES[resource]].pk}/download/")
    assert link.status_code == 200
    url = link.json()["url"]

    assert bob["client"].get(url).status_code == 200  # works for Bob
    assert portal["alice"]["client"].get(url).status_code == 404  # not for Alice


def test_own_data_works_end_to_end(portal) -> None:
    alice = portal["alice"]
    c = alice["client"]
    project = c.get(f"/api/portal/projects/{alice['project'].pk}/").json()
    assert project["title"] == "alice site"

    posted = c.post(
        f"/api/portal/projects/{alice['project'].pk}/messages/",
        {"body": "<script>x</script> hello"},
        content_type="application/json",
    )
    assert posted.status_code == 201
    assert posted.json()["body"] == "<script>x</script> hello"  # stored as text, escaped on render

    link = c.get(f"/api/portal/files/{alice['file'].pk}/download/").json()
    assert link["expires_in"] == 300
    # Same-origin path: the browser follows it through the frontend's /api proxy.
    assert link["url"].startswith("/api/files/") and "://" not in link["url"]
    download = c.get(link["url"])
    assert download.status_code == 200
    assert download["Content-Disposition"].startswith('attachment; filename="alice-brief.pdf"')
    assert download["Cache-Control"] == "private, no-store"
    assert b"".join(download.streaming_content).startswith(b"%PDF")


def test_unsupported_method_on_own_object_is_405_not_404(portal) -> None:
    alice = portal["alice"]
    resp = alice["client"].delete(f"/api/portal/projects/{alice['project'].pk}/")
    assert resp.status_code == 405


def test_tampered_or_expired_links_are_404(portal, monkeypatch) -> None:
    alice = portal["alice"]
    url = alice["client"].get(f"/api/portal/files/{alice['file'].pk}/download/").json()["url"]
    assert alice["client"].get(url.replace("/api/files/", "/api/files/x")).status_code == 404

    import time

    real = time.time
    monkeypatch.setattr("django.core.signing.time.time", lambda: real() + 301)
    assert alice["client"].get(url).status_code == 404


def test_clients_cannot_see_draft_invoices(portal) -> None:
    from datetime import date
    from decimal import Decimal

    from apps.clients.models import Invoice

    alice = portal["alice"]
    draft = Invoice.objects.create(
        client_project=alice["project"], number="INV-draft", amount=Decimal("1"),
        due_date=date(2026, 12, 1),
    )  # fmt: skip
    assert alice["client"].get(f"/api/portal/invoices/{draft.pk}/").status_code == 404


def test_marking_read_only_touches_read_at(portal) -> None:
    from apps.clients.models import Message

    alice = portal["alice"]
    staff_msg = Message.objects.create(client_project=alice["project"], body="update from Forge")
    resp = alice["client"].patch(
        f"/api/portal/messages/{staff_msg.pk}/",
        {"read": True, "body": "rewritten"},
        content_type="application/json",
    )
    assert resp.status_code == 200
    staff_msg.refresh_from_db()
    assert staff_msg.read_at is not None
    assert staff_msg.body == "update from Forge"
