import pytest
from django.contrib.auth import authenticate, get_user_model
from django.db import IntegrityError, transaction
from django.test import Client, RequestFactory

from apps.accounts.models import User


def test_custom_user_model_is_active() -> None:
    assert get_user_model() is User
    assert User.USERNAME_FIELD == "email"


@pytest.mark.django_db
def test_email_is_normalised_and_password_hashed_with_argon2() -> None:
    user = User.objects.create_user(email="  Forge@AdyraForge.COM ", password="correct horse 42!")
    assert user.email == "forge@adyraforge.com"
    assert user.password.startswith("argon2")
    assert "correct horse" not in user.password
    assert user.check_password("correct horse 42!")


@pytest.mark.django_db
def test_email_is_unique_case_insensitively(make_user) -> None:
    make_user(email="client@example.com")
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create(email="CLIENT@example.com")


@pytest.mark.django_db
def test_invited_user_without_password_cannot_log_in() -> None:
    user = User.objects.create_user(email="invitee@example.com")
    assert not user.has_usable_password()


@pytest.mark.django_db
def test_superuser_flags() -> None:
    admin = User.objects.create_superuser(email="forge@example.com", password="x" * 16)
    assert admin.is_staff and admin.is_superuser
    with pytest.raises(ValueError):
        User.objects.create_superuser(email="no@example.com", password="x" * 16, is_staff=False)


@pytest.mark.django_db
def test_login_by_email_is_case_insensitive(make_user) -> None:
    make_user(email="client@example.com", password="a-long-test-password-123")
    request = RequestFactory().post("/login")
    user = authenticate(request, username="CLIENT@Example.com", password="a-long-test-password-123")
    assert user is not None


@pytest.mark.django_db
def test_axes_locks_out_after_repeated_failures(make_user) -> None:
    make_user(email="target@example.com")
    rf = RequestFactory()
    for _ in range(5):
        failed = authenticate(rf.post("/login"), username="target@example.com", password="nope")
        assert failed is None
    # Correct password is refused while locked out.
    locked = authenticate(
        rf.post("/login"), username="target@example.com", password="a-long-test-password-123"
    )
    assert locked is None


@pytest.mark.django_db
def test_axes_lockout_cannot_be_bypassed_by_changing_email_case(make_user) -> None:
    make_user(email="target@example.com")
    rf = RequestFactory()
    for variant in ["target@example.com", "TARGET@example.com", "Target@Example.com"] * 2:
        authenticate(rf.post("/login"), username=variant, password="nope")
    locked = authenticate(
        rf.post("/login"), username="tArGeT@example.com", password="a-long-test-password-123"
    )
    assert locked is None


# --- /api/auth/me/ ----------------------------------------------------------------


@pytest.mark.django_db
def test_me_requires_authentication(client: Client) -> None:
    assert client.get("/api/auth/me/").status_code == 403


@pytest.mark.django_db
def test_me_returns_only_the_requesting_users_data(make_user) -> None:
    alice = make_user(email="alice@example.com", full_name="Alice")
    bob = make_user(email="bob@example.com", full_name="Bob")

    alice_client, bob_client = Client(), Client()
    alice_client.force_login(alice)
    bob_client.force_login(bob)

    a = alice_client.get("/api/auth/me/").json()
    b = bob_client.get("/api/auth/me/").json()
    assert a == {
        "id": alice.id,
        "email": "alice@example.com",
        "full_name": "Alice",
        "role": "client",
    }
    assert b["email"] == "bob@example.com"
    # A client cannot ask for someone else's profile: query params are ignored.
    assert alice_client.get(f"/api/auth/me/?id={bob.id}").json()["email"] == "alice@example.com"
    assert "password" not in a


@pytest.mark.django_db
def test_csrf_endpoint_sets_httponly_lax_cookie(client: Client) -> None:
    resp = client.get("/api/auth/csrf/")
    assert resp.status_code == 200
    assert resp.json()["csrfToken"]
    cookie = resp.cookies["csrftoken"]
    assert cookie["httponly"] is True
    assert cookie["samesite"] == "Lax"
    assert cookie["secure"] is True
