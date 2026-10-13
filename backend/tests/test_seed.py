import pytest
from django.core.management import call_command

from apps.portfolio.models import Project, Service


@pytest.mark.django_db
def test_seed_loads_real_projects() -> None:
    call_command("seed_portfolio")
    projects = {p.slug: p for p in Project.objects.all()}
    assert set(projects) == {
        "latelier-de-gastronomie",
        "medicare-plus",
        "mentality-landing-page",
        "nexus-operations-dashboard",
        "aether-product-launch",
    }
    assert projects["medicare-plus"].live_url == "https://multimedicareplus.netlify.app/"
    assert projects["mentality-landing-page"].live_url == "https://forgementality.netlify.app/"
    # Only L'Atelier is client work; everything else is a concept.
    assert {p.slug for p in Project.objects.filter(kind="client")} == {"latelier-de-gastronomie"}
    # L'Atelier's old URL is a Netlify 404, so it isn't advertised as live.
    assert {p.slug for p in Project.objects.filter(status="not_live")} == {
        "latelier-de-gastronomie",
        "nexus-operations-dashboard",
        "aether-product-launch",
    }
    assert projects["latelier-de-gastronomie"].live_url == ""
    assert all(not p.client_name for p in projects.values() if p.kind == "concept")
    for p in projects.values():
        p.full_clean()
        assert p.result_metrics == [], "metrics must come from the owner, never be invented"
        assert p.technologies.exists()
    assert Service.objects.published().count() == 3


@pytest.mark.django_db
def test_seed_is_idempotent_and_keeps_admin_edits() -> None:
    call_command("seed_portfolio")
    Project.objects.filter(slug="medicare-plus").update(summary="Edited in admin")
    call_command("seed_portfolio")
    assert Project.objects.count() == 5
    assert Project.objects.get(slug="medicare-plus").summary == "Edited in admin"


@pytest.mark.django_db
def test_seed_force_resets_seeded_fields() -> None:
    call_command("seed_portfolio")
    Project.objects.filter(slug="medicare-plus").update(summary="Edited in admin")
    call_command("seed_portfolio", force=True)
    assert Project.objects.get(slug="medicare-plus").summary != "Edited in admin"
