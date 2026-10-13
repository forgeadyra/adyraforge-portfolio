import json
from unittest import mock
from urllib.error import URLError

import pytest
from django.test import Client

from apps.leads import turnstile
from apps.leads.models import Lead, PlannerSubmission

pytestmark = pytest.mark.django_db

CONTACT = {
    "name": "Asha",
    "email": "asha@example.com",
    "project_type": "business_website",
    "budget_range": "500_1500",
    "message": "We need a new site.",
    "utm_source": "linkedin",
    "turnstile_token": "tok",
}


@pytest.fixture
def human(monkeypatch):
    monkeypatch.setattr("apps.leads.views.verify_turnstile", lambda token: True)


@pytest.fixture
def bot(monkeypatch):
    monkeypatch.setattr("apps.leads.views.verify_turnstile", lambda token: False)


def post(path: str, body: dict, **extra):
    return Client(**extra).post(path, body, content_type="application/json")


def test_contact_creates_lead_with_hashed_ip(human) -> None:
    resp = post("/api/leads/contact/", CONTACT, REMOTE_ADDR="203.0.113.5")
    assert resp.status_code == 201
    lead = Lead.objects.get()
    assert lead.source == "contact_form" and lead.utm_source == "linkedin"
    assert len(lead.ip_hash) == 64 and "203.0.113.5" not in lead.ip_hash


def test_honeypot_pretends_success_but_stores_nothing(human) -> None:
    resp = post("/api/leads/contact/", {**CONTACT, "website": "http://spam.example"})
    assert resp.status_code == 201
    assert Lead.objects.count() == 0


def test_failed_turnstile_is_rejected(bot) -> None:
    resp = post("/api/leads/contact/", CONTACT)
    assert resp.status_code == 400
    assert Lead.objects.count() == 0


@pytest.mark.parametrize(
    "override",
    [
        {"project_type": "spaceship"},
        {"email": "not-an-email"},
        {"message": "x" * 5001},
        {"turnstile_token": ""},
        {"name": ""},
    ],
)
def test_contact_validation(human, override) -> None:
    assert post("/api/leads/contact/", {**CONTACT, **override}).status_code == 400
    assert Lead.objects.count() == 0


def test_contact_is_throttled_5_per_hour(human) -> None:
    codes = [post("/api/leads/contact/", CONTACT).status_code for _ in range(6)]
    assert codes == [201] * 5 + [429]


PLANNER = {
    "project_type": "web_app",
    "budget_range": "1500_5000",
    "features": ["client portal", "payments"],
    "answers": {"pages": 6},
    "turnstile_token": "tok",
}


def test_planner_is_throttled_10_per_hour(human) -> None:
    codes = [post("/api/leads/planner/", PLANNER).status_code for _ in range(11)]
    assert codes == [201] * 10 + [429]
    blocked = post("/api/leads/planner/", PLANNER)
    assert blocked.status_code == 429 and int(blocked["Retry-After"]) > 0


def test_planner_without_contact_stores_anonymous_submission(human) -> None:
    resp = post("/api/leads/planner/", PLANNER)
    assert resp.status_code == 201
    sub = PlannerSubmission.objects.get(pk=resp.json()["id"])
    assert sub.lead is None and sub.features == ["client portal", "payments"]


def test_planner_with_contact_creates_lead(human) -> None:
    body = {
        **PLANNER,
        "contact": {"name": "Ravi", "email": "Ravi@Example.com"},
        "utm_campaign": "q4",
    }
    resp = post("/api/leads/planner/", body)
    assert resp.status_code == 201
    lead = Lead.objects.get()
    assert (
        lead.source == "planner" and lead.email == "ravi@example.com" and lead.utm_campaign == "q4"
    )
    assert PlannerSubmission.objects.get().lead == lead


def test_planner_rejects_oversized_answers_without_creating_a_lead(human) -> None:
    body = {
        **PLANNER,
        "answers": {"blob": "x" * 10_001},
        "contact": {"name": "R", "email": "r@example.com"},
    }
    assert post("/api/leads/planner/", body).status_code == 400
    assert Lead.objects.count() == 0 and PlannerSubmission.objects.count() == 0


def test_turnstile_verification_fails_closed_when_cloudflare_is_unreachable() -> None:
    with mock.patch("apps.leads.turnstile.urlopen", side_effect=URLError("down")):
        assert turnstile.verify_turnstile("token") is False


def test_turnstile_verification_parses_success() -> None:
    fake = mock.MagicMock()
    fake.__enter__.return_value = fake
    fake.read.return_value = json.dumps({"success": True}).encode()
    with mock.patch("apps.leads.turnstile.urlopen", return_value=fake) as opened:
        assert turnstile.verify_turnstile("token") is True
    sent = opened.call_args.args[0].data.decode()
    assert "secret=" in sent and "remoteip" not in sent  # visitor IP never shared
    assert turnstile.verify_turnstile("") is False
