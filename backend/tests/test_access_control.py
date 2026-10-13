"""MANDATORY: anonymous users get 401/403 on every portal and admin endpoint;
staff without OTP can't reach the admin API; the portal is never a staff bypass."""

import pytest
from django.test import Client
from django.urls import URLPattern, URLResolver, get_resolver
from django_otp.plugins.otp_static.models import StaticDevice

from apps.core.models import AuditLog
from apps.leads.models import Lead
from tests.conftest import api_login

pytestmark = pytest.mark.django_db

PROTECTED_PREFIXES = ("api/portal/", "api/admin/", "api/files/")
PROTECTED_AUTH = {
    "api/auth/me/",
    "api/auth/logout/",
    "api/auth/logout-all/",
    "api/auth/password/change/",
}
METHODS = ["get", "post", "put", "patch", "delete"]


def _routes(patterns=None, prefix=""):
    for p in patterns if patterns is not None else get_resolver().url_patterns:
        if isinstance(p, URLResolver):
            yield from _routes(p.url_patterns, prefix + str(p.pattern))
        elif isinstance(p, URLPattern):
            yield prefix + str(p.pattern)


def _concrete(route: str) -> str:
    """Turn a URL pattern into a real path with dummy arguments."""
    import re

    path = route.replace("^", "").replace("$", "")
    path = re.sub(r"\(\?P<pk>[^)]*\)", "1", path)
    path = re.sub(r"<str:token>", "dummy-token", path)
    path = re.sub(r"\\\.\(\?P<format>[^)]*\)/?", "", path)
    return "/" + path.replace("\\", "")


PROTECTED = sorted(
    {
        _concrete(r)
        for r in _routes()
        if (r.startswith(PROTECTED_PREFIXES) or r in PROTECTED_AUTH) and "format" not in r
    }
)


def test_route_discovery_found_the_api() -> None:
    joined = " ".join(PROTECTED)
    for expected in (
        "/api/portal/projects/",
        "/api/portal/invoices/1/download/",
        "/api/admin/leads/",
        "/api/admin/clients/invite/",
        "/api/files/dummy-token/",
    ):
        assert expected in joined, expected


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("path", PROTECTED)
def test_anonymous_is_rejected_everywhere(path: str, method: str) -> None:
    resp = getattr(Client(), method)(path, {}, content_type="application/json")
    assert resp.status_code in {401, 403}, f"{method.upper()} {path} -> {resp.status_code}"


@pytest.fixture
def staff(make_user):
    return make_user(email="forge@example.com", is_staff=True, is_superuser=True)


ADMIN_ENDPOINTS = ["/api/admin/leads/", "/api/admin/clients/"]


@pytest.mark.parametrize("path", ADMIN_ENDPOINTS)
def test_staff_without_otp_cannot_reach_admin_api(staff, path: str) -> None:
    c = Client()
    c.force_login(staff)  # session exists, but never passed OTP
    assert c.get(path).status_code == 403
    assert (
        c.post(
            "/api/admin/clients/invite/",
            {"email": "x@example.com"},
            content_type="application/json",
        ).status_code
        == 403
    )


def test_staff_with_device_but_no_code_cannot_log_in(staff) -> None:
    StaticDevice.objects.create(user=staff, name="backup").token_set.create(token="otp-1")
    resp = api_login(Client(), staff.email)
    assert resp.status_code == 400
    assert resp.json()["otp_required"] is True


@pytest.mark.parametrize("path", ADMIN_ENDPOINTS)
def test_client_cannot_reach_admin_api(portal, path: str) -> None:
    assert portal["alice"]["client"].get(path).status_code == 403


@pytest.mark.parametrize("path", ["/api/portal/projects/", "/api/portal/invoices/"])
def test_staff_cannot_use_portal_as_a_bypass(staff, portal, path: str) -> None:
    c = Client()
    c.force_login(staff)
    assert c.get(path).status_code == 403


@pytest.fixture
def otp_staff_client(staff):
    device = StaticDevice.objects.create(user=staff, name="backup")
    device.token_set.create(token="otp-ok-1")
    c = Client()
    resp = api_login(c, staff.email, otp="otp-ok-1")
    assert resp.status_code == 200, resp.content
    return c


def test_otp_verified_staff_can_use_admin_api(otp_staff_client, portal) -> None:
    clients = otp_staff_client.get("/api/admin/clients/")
    assert clients.status_code == 200
    assert {r["email"] for r in clients.json()["results"]} == {
        "alice@example.com",
        "bob@example.com",
    }


def test_admin_invite_creates_passwordless_client_and_emails_link(otp_staff_client) -> None:
    from django.core import mail

    from apps.accounts.models import User

    resp = otp_staff_client.post(
        "/api/admin/clients/invite/",
        {"email": "New.Client@Example.com", "full_name": "New Client", "company": "Acme"},
        content_type="application/json",
    )
    assert resp.status_code == 201
    user = User.objects.get(email="new.client@example.com")
    assert not user.has_usable_password()
    assert user.client_profile.company == "Acme"
    assert len(mail.outbox) == 1 and "/invite/" in mail.outbox[0].body
    assert AuditLog.objects.filter(
        action=AuditLog.Action.ADMIN_ADD, object_type="clients.clientprofile"
    ).exists()


def test_admin_lead_pipeline_rules_apply_through_api(otp_staff_client) -> None:
    lead = Lead.objects.create(name="L", email="l@example.com", project_type="other", message="m")
    url = f"/api/admin/leads/{lead.pk}/"
    ok = otp_staff_client.patch(url, {"status": "proposal"}, content_type="application/json")
    assert ok.status_code == 200
    back = otp_staff_client.patch(url, {"status": "new"}, content_type="application/json")
    assert back.status_code == 400
    readonly = otp_staff_client.patch(
        url, {"email": "evil@example.com"}, content_type="application/json"
    )
    assert readonly.status_code == 200
    lead.refresh_from_db()
    assert lead.email == "l@example.com" and lead.status == "proposal"


def test_there_is_no_registration_endpoint() -> None:
    for path in ("/api/auth/register/", "/api/auth/signup/", "/api/portal/clients/"):
        resp = Client().post(path, {"email": "a@b.co", "password": "x" * 20})
        assert resp.status_code == 404
