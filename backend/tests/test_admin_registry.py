import pytest
from django.apps import apps
from django.conf import settings
from django.contrib import admin
from django.test import Client
from django_otp.plugins.otp_static.models import StaticDevice

from apps.core.admin import AuditedAdminMixin

PROJECT_APPS = ["accounts", "core", "portfolio", "leads", "clients"]
PROJECT_MODELS = [m for label in PROJECT_APPS for m in apps.get_app_config(label).get_models()]


@pytest.mark.parametrize("model", PROJECT_MODELS, ids=lambda m: m._meta.label)
def test_every_model_is_registered(model) -> None:
    if model._meta.model_name == "projectimage":
        pytest.skip("edited inline on Project")
    assert model in admin.site._registry


@pytest.mark.parametrize("model", PROJECT_MODELS, ids=lambda m: m._meta.label)
def test_registered_admins_are_audited_and_searchable(model) -> None:
    model_admin = admin.site._registry.get(model)
    if model_admin is None:
        pytest.skip("not registered directly")
    if model._meta.label != "core.AuditLog":
        assert isinstance(model_admin, AuditedAdminMixin)
    assert model_admin.search_fields


@pytest.mark.django_db
def test_every_admin_changelist_and_add_page_renders(make_user) -> None:
    """Catches broken list_filter/search/fieldsets config in one sweep."""
    staff = make_user(email="forge@example.com", is_staff=True, is_superuser=True)
    device = StaticDevice.objects.create(user=staff, name="backup")
    device.token_set.create(token="otp-backup-2")
    c = Client()
    root = f"/{settings.ADMIN_URL}"
    c.post(
        f"{root}login/",
        {
            "username": "forge@example.com",
            "password": "a-long-test-password-123",
            "otp_device": device.persistent_id,
            "otp_token": "otp-backup-2",
        },
    )
    for model in admin.site._registry:
        if model._meta.app_label not in PROJECT_APPS:
            continue
        base = f"{root}{model._meta.app_label}/{model._meta.model_name}/"
        resp = c.get(base, {"q": "x"})
        assert resp.status_code == 200, f"changelist {base}"
        add = c.get(f"{base}add/")
        assert add.status_code in {200, 403}, f"add {base}"


@pytest.mark.django_db
def test_admin_timestamps_are_read_only(make_user) -> None:
    from django.test import RequestFactory

    from apps.leads.models import Lead

    request = RequestFactory().get("/")
    request.user = make_user(email="forge@example.com", is_staff=True, is_superuser=True)
    readonly = admin.site._registry[Lead].get_readonly_fields(request)
    assert {"created_at", "updated_at", "ip_hash", "status_changed_at"} <= set(readonly)
