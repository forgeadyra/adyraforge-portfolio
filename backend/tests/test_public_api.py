import pytest
from django.core.management import call_command
from django.test import Client

from apps.portfolio import models as portfolio_models
from apps.portfolio.models import Project, Service

pytestmark = pytest.mark.django_db


@pytest.fixture
def seeded():
    call_command("seed_portfolio")


def get(path: str, **params):
    return Client().get(f"/api/public/{path}", params)


def test_only_published_projects_are_listed(seeded) -> None:
    slugs = {p["slug"] for p in get("projects/").json()}
    assert "mentality-landing-page" not in slugs  # unpublished in the seed
    assert "latelier-de-gastronomie" in slugs
    assert get("projects/mentality-landing-page/").status_code == 404


def test_project_filters(seeded) -> None:
    assert {p["slug"] for p in get("projects/", tech="django").json()} == {
        "nexus-operations-dashboard"
    }
    by_industry = get("projects/", industry="healthcare / hospital").json()
    assert [p["slug"] for p in by_industry] == ["medicare-plus"]
    assert {p["slug"] for p in get("projects/", featured="1").json()} == {
        "latelier-de-gastronomie",
        "medicare-plus",
    }


def test_case_study_detail_has_similar_projects_that_really_overlap(seeded) -> None:
    detail = get("projects/aether-product-launch/").json()
    assert detail["title"] == "Aether Product Launch"
    similar = [p["slug"] for p in detail["similar"]]
    assert "aether-product-launch" not in similar
    assert "mentality-landing-page" not in similar  # unpublished never leaks via similar
    assert similar and similar[0] == "latelier-de-gastronomie"  # shares HTML5 + JavaScript


def test_kind_is_exposed_and_only_latelier_is_a_client(seeded) -> None:
    kinds = {p["slug"]: p["kind"] for p in get("projects/").json()}
    assert kinds == {
        "latelier-de-gastronomie": "client",
        "medicare-plus": "concept",
        "nexus-operations-dashboard": "concept",
        "aether-product-launch": "concept",
    }


def test_proof_bar_stats_endpoint_is_gone() -> None:
    assert get("stats/").status_code == 404


def test_lighthouse_is_null_until_complete_then_exposed(seeded) -> None:
    from datetime import date

    def card() -> dict:
        return next(p for p in get("projects/").json() if p["slug"] == "medicare-plus")

    assert card()["lighthouse"] is None
    Project.objects.filter(slug="medicare-plus").update(lighthouse_performance=97)
    assert card()["lighthouse"] is None  # partial scores are never shown
    Project.objects.filter(slug="medicare-plus").update(
        lighthouse_accessibility=100,
        lighthouse_best_practices=96,
        lighthouse_seo=100,
        lighthouse_measured_on=date(2026, 10, 1),
    )
    assert card()["lighthouse"] == {
        "performance": 97,
        "accessibility": 100,
        "best_practices": 96,
        "seo": 100,
        "measured_on": "2026-10-01",
    }


def test_results_note_is_in_case_study_detail(seeded) -> None:
    Project.objects.filter(slug="medicare-plus").update(
        results_note="Concept build: no real traffic, so no conversion data."
    )
    detail = get("projects/medicare-plus/").json()
    assert detail["results_note"].startswith("Concept build")
    assert detail["kind"] == "concept" and detail["client_name"] == ""


def test_services_have_no_invented_prices(seeded) -> None:
    services = get("services/").json()
    assert [s["slug"] for s in services] == ["websites", "landing-pages", "web-applications"]
    assert all(s["price_from_inr"] is None and s["price_from_usd"] is None for s in services)
    assert all(s["includes"] for s in services)


def test_testimonials_are_empty_until_real_ones_are_published() -> None:
    portfolio_models.Testimonial.objects.create(
        author_name="Draft", quote="Not yet approved", published=False
    )
    assert get("testimonials/").json() == []


def test_technologies_only_lists_ones_in_use(seeded) -> None:
    Project.objects.update(published=False)
    assert get("technologies/").json() == []


def test_public_endpoints_ignore_sessions_and_are_read_only(seeded, make_user) -> None:
    c = Client()
    c.force_login(make_user(email="alice@example.com"))
    assert c.get("/api/public/projects/").status_code == 200
    for method in ("post", "put", "patch", "delete"):
        assert getattr(c, method)("/api/public/projects/", {}).status_code in {403, 405}
    assert Client().post("/api/public/services/", {"name": "x"}).status_code == 405
    assert Service.objects.count() == 3


def test_planner_returns_recommended_services(seeded, monkeypatch) -> None:
    monkeypatch.setattr("apps.leads.views.verify_turnstile", lambda token: True)
    resp = Client().post(
        "/api/leads/planner/",
        {"project_type": "business_website", "features": ["client login"], "turnstile_token": "t"},
        content_type="application/json",
    )
    assert resp.status_code == 201
    assert [s["slug"] for s in resp.json()["recommended_services"]] == [
        "websites",
        "web-applications",
    ]
