import pytest
from django.conf import settings
from django.test import Client


def test_admin_is_not_at_the_default_path(client: Client) -> None:
    assert client.get("/admin/").status_code == 404


@pytest.mark.django_db
def test_admin_is_served_from_env_path(client: Client) -> None:
    resp = client.get(f"/{settings.ADMIN_URL}")
    assert resp.status_code == 302
    assert "/login/" in resp.headers["Location"]


@pytest.mark.django_db
def test_staff_without_otp_cannot_use_admin(make_user) -> None:
    staff = make_user(email="forge@example.com", is_staff=True, is_superuser=True)
    c = Client()
    c.force_login(staff)  # password OK, but no verified OTP device
    resp = c.get(f"/{settings.ADMIN_URL}")
    assert resp.status_code == 302
    assert "/login/" in resp.headers["Location"]


@pytest.mark.django_db
def test_admin_login_brute_force_is_locked_out(make_user, client: Client) -> None:
    make_user(email="forge@example.com", is_staff=True, is_superuser=True)
    login_url = f"/{settings.ADMIN_URL}login/"
    bad = {"username": "forge@example.com", "password": "wrong", "otp_token": "000000"}
    statuses = [client.post(login_url, bad).status_code for _ in range(5)]
    assert 429 not in statuses[:4]
    # Even the right password is refused once the account+IP pair is locked.
    good = {**bad, "password": "a-long-test-password-123"}
    assert client.post(login_url, good).status_code == 429


def test_ml_package_is_importable() -> None:
    import adyra_ml

    assert adyra_ml.__version__
