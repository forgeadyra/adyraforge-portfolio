from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from django.core.cache import cache
from django.test import Client

from apps.accounts.models import User

PASSWORD = "a-long-test-password-123"


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    # Throttle counters live in the cache; keep tests independent.
    cache.clear()


@pytest.fixture
def make_user(db: Any) -> Callable[..., User]:
    counter = iter(range(1, 10_000))

    def _make(email: str | None = None, **extra: Any) -> User:
        email = email or f"client{next(counter)}@example.com"
        extra.setdefault("password", PASSWORD)
        return User.objects.create_user(email=email, **extra)

    return _make


def api_login(
    client: Client, email: str, password: str = PASSWORD, otp: str | None = None, **extra: Any
) -> Any:
    body = {"email": email, "password": password}
    if otp is not None:
        body["otp_token"] = otp
    return client.post("/api/auth/login/", body, content_type="application/json", **extra)


@pytest.fixture
def portal(make_user):
    """Alice and Bob: each a client with a project, file, message and sent invoice."""
    from apps.clients.models import ClientProfile, ClientProject, Invoice, Message, ProjectFile
    from tests.files import pdf

    world: dict[str, dict[str, Any]] = {}
    for name in ("alice", "bob"):
        user = make_user(email=f"{name}@example.com", full_name=name.title())
        profile = ClientProfile.objects.create(user=user, company=name.title())
        project = ClientProject.objects.create(client=profile, title=f"{name} site")
        message = Message.objects.create(client_project=project, sender=user, body=f"hi {name}")
        file = ProjectFile.objects.create(client_project=project, file=pdf(f"{name}-brief.pdf"))
        invoice = Invoice.objects.create(
            client_project=project, number=f"INV-{name}", amount=Decimal("100.00"),
            status=Invoice.Status.SENT, due_date=date(2026, 12, 1), pdf=pdf(f"{name}.pdf"),
        )  # fmt: skip
        client = Client()
        client.force_login(user)
        world[name] = {
            "user": user, "profile": profile, "project": project, "message": message,
            "file": file, "invoice": invoice, "client": client,
        }  # fmt: skip
    return world
