from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.core.security import hash_ip
from apps.leads.models import Lead, PlannerSubmission, ProjectType

pytestmark = pytest.mark.django_db

S = Lead.Status


def make_lead(**kw) -> Lead:
    defaults = {
        "name": "Asha",
        "email": "Asha@Example.COM ",
        "project_type": ProjectType.BUSINESS_WEBSITE,
        "message": "We need a site.",
    }
    return Lead.objects.create(**{**defaults, **kw})


@pytest.mark.django_db
def test_email_is_normalized_and_ip_is_stored_hashed() -> None:
    lead = make_lead(ip_hash=hash_ip("203.0.113.9"))
    lead.refresh_from_db()
    assert lead.email == "asha@example.com"
    assert lead.status == S.NEW
    assert "203.0.113.9" not in lead.ip_hash and len(lead.ip_hash) == 64


@pytest.mark.parametrize(
    ("old", "new", "ok"),
    [
        (S.NEW, S.CONTACTED, True),
        (S.NEW, S.PROPOSAL, True),  # skipping forward is fine
        (S.CONTACTED, S.WON, True),
        (S.PROPOSAL, S.LOST, True),
        (S.NEW, S.LOST, True),
        (S.PROPOSAL, S.CONTACTED, False),  # no going back
        (S.CONTACTED, S.NEW, False),
        (S.WON, S.LOST, False),  # terminal
        (S.LOST, S.NEW, False),
        (S.WON, S.WON, True),
    ],
)
def test_pipeline_transitions(old: str, new: str, ok: bool) -> None:
    assert Lead.can_transition(old, new) is ok


@pytest.mark.django_db
def test_invalid_transition_is_blocked_on_save_not_just_in_forms() -> None:
    lead = make_lead()
    lead.status = S.PROPOSAL
    lead.save()
    first_change = lead.status_changed_at

    lead = Lead.objects.get(pk=lead.pk)
    lead.status = S.CONTACTED
    with pytest.raises(ValidationError):
        lead.save()
    with pytest.raises(ValidationError):
        lead.full_clean()

    lead = Lead.objects.get(pk=lead.pk)
    lead.status = S.WON
    lead.save()
    assert lead.status_changed_at > first_change


@pytest.mark.django_db
def test_score_is_capped_at_100() -> None:
    with pytest.raises(ValidationError):
        Lead(
            name="x", email="x@example.com", project_type="other", message="m", score=101
        ).full_clean()
    with pytest.raises(IntegrityError), transaction.atomic():
        make_lead(score=101)


def test_message_length_is_capped() -> None:
    lead = Lead(name="x", email="x@example.com", project_type="other", message="m" * 5001)
    with pytest.raises(ValidationError) as exc:
        lead.full_clean()
    assert "message" in exc.value.message_dict


def test_invalid_choices_are_rejected() -> None:
    lead = Lead(name="x", email="x@example.com", project_type="spaceship", message="m",
                budget_range="a-billion")  # fmt: skip
    with pytest.raises(ValidationError) as exc:
        lead.full_clean()
    assert {"project_type", "budget_range"} <= set(exc.value.message_dict)


@pytest.mark.django_db
def test_planner_submission_links_to_lead_and_survives_its_deletion() -> None:
    lead = make_lead()
    sub = PlannerSubmission.objects.create(
        lead=lead, project_type=ProjectType.WEB_APP, features=["auth", "dashboard"],
        estimate_min=Decimal("40000"), estimate_max=Decimal("90000"),
    )  # fmt: skip
    assert list(lead.planner_submissions.all()) == [sub]
    lead.delete()
    sub.refresh_from_db()
    assert sub.lead is None


@pytest.mark.django_db
def test_planner_estimate_bounds_are_enforced() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        PlannerSubmission.objects.create(
            project_type="web_app", estimate_min=Decimal("10"), estimate_max=Decimal("5")
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        PlannerSubmission.objects.create(project_type="web_app", estimate_min=Decimal("-1"))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("features", "not-a-list"),
        ("features", ["x" * 61]),
        ("features", ["f"] * 31),
        ("features", [1, 2]),
        ("answers", ["not", "a", "dict"]),
        ("answers", {"blob": "x" * 10_001}),
    ],
)
def test_planner_json_is_validated(field: str, value) -> None:
    sub = PlannerSubmission(project_type="web_app", **{field: value})
    with pytest.raises(ValidationError) as exc:
        sub.full_clean()
    assert field in exc.value.message_dict
