import hashlib

import pytest
from django.conf import settings
from django.contrib.auth import authenticate, user_logged_in, user_logged_out
from django.test import Client, RequestFactory
from django_otp.plugins.otp_static.models import StaticDevice

from apps.core.models import AuditLog
from apps.core.security import hash_ip
from apps.portfolio.models import Service


def test_ip_hash_is_keyed_not_plain_sha256() -> None:
    ip = "203.0.113.7"
    digest = hash_ip(ip)
    assert len(digest) == 64
    assert ip not in digest
    assert digest == hash_ip(ip)  # stable, so repeat visitors can be grouped
    assert digest != hashlib.sha256(ip.encode()).hexdigest()  # not brute-forceable without key
    assert digest != hash_ip("203.0.113.8")
    assert hash_ip("") == ""


@pytest.mark.django_db
def test_audit_log_is_append_only() -> None:
    entry = AuditLog.objects.create(action=AuditLog.Action.LOGIN, actor_repr="x@example.com")
    entry.message = "tampered"
    with pytest.raises(ValueError, match="immutable"):
        entry.save()
    with pytest.raises(ValueError, match="cannot be deleted"):
        entry.delete()


@pytest.mark.django_db
def test_login_and_logout_are_audited_with_ip_hash(make_user) -> None:
    user = make_user(email="client@example.com")
    request = RequestFactory().post("/login", REMOTE_ADDR="198.51.100.4")
    user_logged_in.send(sender=type(user), request=request, user=user)
    user_logged_out.send(sender=type(user), request=request, user=user)

    actions = list(AuditLog.objects.order_by("timestamp").values_list("action", "actor_id"))
    assert actions == [(AuditLog.Action.LOGIN, user.id), (AuditLog.Action.LOGOUT, user.id)]
    entry = AuditLog.objects.first()
    assert entry is not None
    assert entry.ip_hash == hash_ip("198.51.100.4")
    assert "198.51.100.4" not in entry.ip_hash


@pytest.mark.django_db
def test_failed_login_is_audited_without_the_password(make_user) -> None:
    make_user(email="client@example.com")
    rf = RequestFactory()
    authenticate(rf.post("/login"), username="Client@Example.com", password="hunter2-secret")
    entry = AuditLog.objects.get(action=AuditLog.Action.LOGIN_FAILED)
    assert entry.actor is None
    assert entry.actor_repr == "client@example.com"
    assert "hunter2" not in f"{entry.actor_repr}{entry.message}{entry.object_repr}"


@pytest.mark.django_db
def test_failed_login_with_password_typed_as_username_is_not_recorded() -> None:
    authenticate(RequestFactory().post("/login"), username="MyS3cretPass!", password="x")
    entry = AuditLog.objects.get(action=AuditLog.Action.LOGIN_FAILED)
    assert entry.actor_repr == ""


@pytest.mark.django_db
def test_admin_changes_are_audited_end_to_end(make_user) -> None:
    """Real admin flow: password + OTP login, then add and delete via the admin."""
    staff = make_user(email="forge@example.com", is_staff=True, is_superuser=True)
    device = StaticDevice.objects.create(user=staff, name="backup")
    device.token_set.create(token="otp-backup-1")

    c = Client(REMOTE_ADDR="192.0.2.10")
    admin_root = f"/{settings.ADMIN_URL}"
    resp = c.post(
        f"{admin_root}login/",
        {
            "username": "forge@example.com",
            "password": "a-long-test-password-123",
            "otp_device": device.persistent_id,
            "otp_token": "otp-backup-1",
        },
    )
    assert resp.status_code == 302, "OTP login should succeed"

    resp = c.post(
        f"{admin_root}portfolio/service/add/",
        {"name": "Audits", "slug": "audits", "summary": "Security audits", "order": 0},
    )
    assert resp.status_code == 302
    service = Service.objects.get(slug="audits")

    resp = c.post(f"{admin_root}portfolio/service/{service.pk}/delete/", {"post": "yes"})
    assert resp.status_code == 302
    assert not Service.objects.filter(slug="audits").exists()

    trail = AuditLog.objects.filter(object_type="portfolio.service").order_by("timestamp")
    assert [e.action for e in trail] == [AuditLog.Action.ADMIN_ADD, AuditLog.Action.ADMIN_DELETE]
    for e in trail:
        assert e.actor == staff
        assert e.object_repr == "Audits"
        assert e.ip_hash == hash_ip("192.0.2.10")
    assert AuditLog.objects.filter(action=AuditLog.Action.LOGIN, actor=staff).exists()


@pytest.mark.django_db
def test_audit_log_admin_is_read_only(make_user) -> None:
    from django.contrib import admin

    model_admin = admin.site._registry[AuditLog]
    request = RequestFactory().get("/")
    request.user = make_user(email="forge@example.com", is_staff=True, is_superuser=True)
    assert not model_admin.has_add_permission(request)
    assert not model_admin.has_change_permission(request)
    assert not model_admin.has_delete_permission(request)
