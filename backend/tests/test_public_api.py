import pytest
from django.core.management import call_command
from django.test import Client, override_settings

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


def test_stats_are_computed_from_published_data(seeded) -> None:
    stats = get("stats/").json()
    assert stats["live_projects"] == 2  # mėntality is live but unpublished
    assert "Healthcare / hospital" in stats["industries"]
    assert stats["response_time_hours"] is None


@override_settings(RESPONSE_TIME_HOURS=24)
def test_response_time_only_appears_when_configured(seeded) -> None:
    assert get("stats/").json()["response_time_hours"] == 24


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
