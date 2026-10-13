"""Client data isolation and integrity (CLAUDE.md rule 6)."""

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.utils import timezone

from apps.clients.models import (
    ClientProfile,
    ClientProject,
    Invoice,
    Message,
    Milestone,
    ProjectFile,
    clean_display_name,
)
from tests.files import pdf


@pytest.fixture
def two_clients(make_user):
    """Alice and Bob, each with one project holding one of everything."""
    world = {}
    for name in ("alice", "bob"):
        user = make_user(email=f"{name}@example.com")
        profile = ClientProfile.objects.create(user=user, company=name.title())
        project = ClientProject.objects.create(client=profile, title=f"{name} site")
        Milestone.objects.create(client_project=project, title=f"{name} kickoff")
        Message.objects.create(client_project=project, sender=user, body=f"hi from {name}")
        ProjectFile.objects.create(client_project=project, file=pdf(f"{name}.pdf"))
        Invoice.objects.create(
            client_project=project, number=f"INV-{name}", amount=Decimal("100.00"),
            status=Invoice.Status.SENT, due_date=date(2026, 12, 1),
        )  # fmt: skip
        world[name] = {"user": user, "profile": profile, "project": project}
    return world


SCOPED_MODELS = [ClientProfile, ClientProject, Milestone, Message, ProjectFile, Invoice]


@pytest.mark.django_db
@pytest.mark.parametrize("model", SCOPED_MODELS, ids=lambda m: m.__name__)
def test_client_cannot_read_another_clients_rows(two_clients, model) -> None:
    alice, bob = two_clients["alice"], two_clients["bob"]
    alice_rows = model.objects.for_user(alice["user"])
    bob_rows = model.objects.for_user(bob["user"])

    assert alice_rows.count() == 1 and bob_rows.count() == 1
    assert not set(alice_rows.values_list("pk", flat=True)) & set(
        bob_rows.values_list("pk", flat=True)
    )
    # Fetching Bob's row by primary key through Alice's scope finds nothing (-> 404 in views).
    bob_pk = bob_rows.get().pk
    assert not alice_rows.filter(pk=bob_pk).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("model", SCOPED_MODELS, ids=lambda m: m.__name__)
def test_anonymous_and_inactive_users_see_nothing(two_clients, model) -> None:
    assert model.objects.for_user(AnonymousUser()).count() == 0
    assert model.objects.for_user(None).count() == 0
    alice = two_clients["alice"]["user"]
    alice.is_active = False
    alice.save()
    assert model.objects.for_user(alice).count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("model", SCOPED_MODELS, ids=lambda m: m.__name__)
def test_staff_sees_all_clients(two_clients, make_user, model) -> None:
    staff = make_user(email="forge@example.com", is_staff=True)
    assert model.objects.for_user(staff).count() == 2


@pytest.mark.django_db
def test_clients_never_see_draft_invoices(two_clients, make_user) -> None:
    alice = two_clients["alice"]
    Invoice.objects.create(
        client_project=alice["project"], number="INV-draft", amount=Decimal("5"),
        due_date=date(2026, 12, 1),
    )  # fmt: skip
    numbers = set(Invoice.objects.for_user(alice["user"]).values_list("number", flat=True))
    assert numbers == {"INV-alice"}
    staff = make_user(email="forge@example.com", is_staff=True)
    assert Invoice.objects.for_user(staff).filter(number="INV-draft").exists()


@pytest.mark.django_db
def test_deleting_a_client_cannot_cascade_into_projects_or_invoices(two_clients) -> None:
    alice = two_clients["alice"]
    with pytest.raises(ProtectedError):
        alice["user"].delete()
    with pytest.raises(ProtectedError):
        alice["profile"].delete()
    assert ClientProject.objects.filter(pk=alice["project"].pk).exists()
    # Invoices protect their project too.
    with pytest.raises(ProtectedError):
        alice["project"].delete()


@pytest.mark.django_db
def test_invoice_integrity_constraints(two_clients) -> None:
    project = two_clients["alice"]["project"]
    base = {"client_project": project, "due_date": date(2026, 12, 1)}
    with pytest.raises(IntegrityError), transaction.atomic():
        Invoice.objects.create(number="INV-0", amount=Decimal("0"), **base)
    with pytest.raises(IntegrityError), transaction.atomic():
        Invoice.objects.create(number="INV-paid", amount=Decimal("1"), status="paid", **base)
    with pytest.raises(IntegrityError), transaction.atomic():
        Invoice.objects.create(number="INV-alice", amount=Decimal("1"), **base)  # duplicate
    Invoice.objects.create(
        number="INV-ok", amount=Decimal("1"), status="paid", paid_at=timezone.now(), **base
    )


@pytest.mark.django_db
def test_invoice_currency_is_inr_or_usd() -> None:
    inv = Invoice(number="X", amount=Decimal("1"), currency="EUR", due_date=date(2026, 1, 1))
    with pytest.raises(ValidationError) as exc:
        inv.full_clean(exclude=["client_project"])
    assert "currency" in exc.value.message_dict


@pytest.mark.django_db
def test_client_project_progress_and_dates(two_clients) -> None:
    profile = two_clients["alice"]["profile"]
    with pytest.raises(IntegrityError), transaction.atomic():
        ClientProject.objects.create(client=profile, title="x", progress=101)
    with pytest.raises(IntegrityError), transaction.atomic():
        ClientProject.objects.create(
            client=profile, title="x", start_date=date(2026, 5, 1), due_date=date(2026, 4, 1)
        )


@pytest.mark.django_db
def test_project_file_metadata_and_private_storage(two_clients) -> None:
    f = ProjectFile.objects.get(client_project=two_clients["alice"]["project"])
    assert f.original_name == "alice.pdf"
    assert f.content_type == "application/pdf"
    assert f.size > 0
    assert f.file.name.startswith("client-files/") and "alice" not in f.file.name
    with pytest.raises(NotImplementedError):
        _ = f.file.url


def test_display_name_is_sanitized() -> None:
    assert clean_display_name("..\\..\\windows\\evil\x00.pdf") == "evil.pdf"
    assert clean_display_name("/etc/passwd") == "passwd"
    assert clean_display_name("\x07") == "file"
    assert len(clean_display_name("a" * 400 + ".pdf")) == 255


@pytest.mark.django_db
def test_staff_cannot_be_a_client_profile(make_user) -> None:
    staff = make_user(email="forge@example.com", is_staff=True)
    with pytest.raises(ValidationError):
        ClientProfile(user=staff).full_clean()


@pytest.mark.django_db
def test_message_thread_is_per_project_and_ordered(two_clients) -> None:
    alice = two_clients["alice"]
    Message.objects.create(client_project=alice["project"], sender=alice["user"], body="second")
    bodies = list(alice["project"].messages.values_list("body", flat=True))
    assert bodies == ["hi from alice", "second"]
