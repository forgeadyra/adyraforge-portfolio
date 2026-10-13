"""Lead, ClientProject and Invoice must be fully usable in the Django admin."""

from datetime import date
from decimal import Decimal

import pytest
from django.conf import settings
from django.test import Client
from django_otp.plugins.otp_static.models import StaticDevice

from apps.clients.models import ClientProfile, ClientProject, Invoice, Milestone
from apps.core.models import AuditLog
from apps.leads.models import Lead
from tests.conftest import PASSWORD

pytestmark = pytest.mark.django_db
ROOT = f"/{settings.ADMIN_URL}"


@pytest.fixture
def admin_client(make_user) -> Client:
    staff = make_user(email="forge@example.com", is_staff=True, is_superuser=True)
    device = StaticDevice.objects.create(user=staff, name="backup")
    device.token_set.create(token="otp-admin-1")
    c = Client()
    resp = c.post(
        f"{ROOT}login/",
        {"username": staff.email, "password": PASSWORD, "otp_device": device.persistent_id,
         "otp_token": "otp-admin-1"},
    )  # fmt: skip
    assert resp.status_code == 302
    return c


@pytest.fixture
def project(make_user) -> ClientProject:
    profile = ClientProfile.objects.create(user=make_user(email="c@example.com"), company="Acme")
    return ClientProject.objects.create(client=profile, title="Acme site")


def lead(**kw) -> Lead:
    base = {"name": "L", "email": "l@example.com", "project_type": "other", "message": "m"}
    return Lead.objects.create(**{**base, **kw})


def test_lead_pipeline_is_sorted_by_score(admin_client) -> None:
    lead(name="Low", score=10)
    lead(name="High", score=90)
    html = admin_client.get(f"{ROOT}leads/lead/").content.decode()
    assert html.index("High") < html.index("Low")


def test_invalid_status_move_in_admin_is_a_form_error_not_a_crash(admin_client) -> None:
    item = lead(status="proposal")
    resp = admin_client.post(
        f"{ROOT}leads/lead/{item.pk}/change/",
        {"status": "new", "score": 0, "internal_notes": "", "name": "L", "email": "l@example.com",
         "company": "", "project_type": "other", "budget_range": "not_sure",
         "timeline": "flexible", "message": "m", "source": "contact_form", "utm_source": "",
         "utm_medium": "", "utm_campaign": "", "utm_term": "", "utm_content": "",
         "planner_submissions-TOTAL_FORMS": 0, "planner_submissions-INITIAL_FORMS": 0},
    )  # fmt: skip
    assert resp.status_code == 200  # re-rendered with errors
    assert "can&#x27;t move from" in resp.content.decode()
    item.refresh_from_db()
    assert item.status == "proposal"


def test_client_project_page_has_milestone_and_invoice_inlines(admin_client, project) -> None:
    Milestone.objects.create(client_project=project, title="Kickoff done")
    Invoice.objects.create(
        client_project=project, number="AF-TEST-1", amount=Decimal("10"), due_date=date(2026, 12, 1)
    )
    html = admin_client.get(f"{ROOT}clients/clientproject/{project.pk}/change/").content.decode()
    assert "Kickoff done" in html and "AF-TEST-1" in html
    assert 'id="milestones-group"' in html and 'id="invoices-group"' in html


def test_lead_project_invoice_changelists_filter_and_search(admin_client, project) -> None:
    for path, params in [
        ("leads/lead/", {"status__exact": "new", "q": "acme"}),
        ("clients/clientproject/", {"status__exact": "planning", "q": "acme"}),
        ("clients/invoice/", {"status__exact": "sent", "currency__exact": "INR", "q": "AF"}),
    ]:
        assert admin_client.get(f"{ROOT}{path}", params).status_code == 200, path


def test_mark_paid_action_sets_paid_at_and_audits(admin_client, project) -> None:
    sent = Invoice.objects.create(client_project=project, number="AF-1", amount=Decimal("5"),
                                  status="sent", due_date=date(2026, 12, 1))  # fmt: skip
    draft = Invoice.objects.create(client_project=project, number="AF-2", amount=Decimal("5"),
                                   due_date=date(2026, 12, 1))  # fmt: skip
    resp = admin_client.post(
        f"{ROOT}clients/invoice/",
        {"action": "mark_paid", "_selected_action": [sent.pk, draft.pk]},
    )
    assert resp.status_code == 302
    sent.refresh_from_db()
    draft.refresh_from_db()
    assert sent.status == "paid" and sent.paid_at is not None
    assert draft.status == "draft"  # drafts are never marked paid
    assert AuditLog.objects.filter(object_id=str(sent.pk), message__contains="marked paid").exists()
