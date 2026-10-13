import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.portfolio import models as portfolio_models
from apps.portfolio.models import (
    BlogPost,
    Project,
    ProjectImage,
    Service,
    Technology,
    sanitize_rich_text,
)
from tests.files import png


def make_project(**kw) -> Project:
    defaults = {"title": "Demo", "slug": "demo", "status": Project.Status.CONCEPT}
    return Project(**{**defaults, **kw})


@pytest.mark.django_db
def test_published_and_featured_querysets() -> None:
    make_project(slug="a", published=True, is_featured=True).save()
    make_project(slug="b", published=True).save()
    make_project(slug="c").save()
    assert set(Project.objects.published().values_list("slug", flat=True)) == {"a", "b"}
    assert list(Project.objects.published().featured().values_list("slug", flat=True)) == ["a"]


@pytest.mark.django_db
def test_slug_is_unique() -> None:
    make_project(slug="same").save()
    with pytest.raises(IntegrityError), transaction.atomic():
        make_project(slug="same").save()


def test_live_project_requires_https_live_url() -> None:
    p = make_project(status=Project.Status.LIVE)
    with pytest.raises(ValidationError) as exc:
        p.full_clean(validate_unique=False)
    assert "live_url" in exc.value.message_dict

    p.live_url = "http://insecure.example"
    with pytest.raises(ValidationError) as exc:
        p.full_clean(validate_unique=False)
    assert "live_url" in exc.value.message_dict

    p.live_url = "https://ok.example"
    p.full_clean(validate_unique=False)


@pytest.mark.parametrize(
    "metrics",
    [
        {"label": "x", "value": "y"},
        [{"label": "x"}],
        [{"label": "x", "value": "y", "extra": 1}],
        [{"label": "", "value": "y"}],
        [{"label": "x" * 61, "value": "y"}],
        [{"label": "x", "value": "y"}] * 9,
    ],
)
def test_result_metrics_shape_is_validated(metrics) -> None:
    with pytest.raises(ValidationError) as exc:
        make_project(result_metrics=metrics).full_clean(validate_unique=False)
    assert "result_metrics" in exc.value.message_dict


def test_valid_result_metrics_pass() -> None:
    make_project(result_metrics=[{"label": "LCP", "value": "1.2s"}]).full_clean(
        validate_unique=False
    )


def test_cover_image_needs_alt_text() -> None:
    p = make_project(cover_image=png())
    with pytest.raises(ValidationError) as exc:
        p.full_clean(validate_unique=False)
    assert "cover_alt" in exc.value.message_dict


def test_gallery_image_alt_text_is_required() -> None:
    with pytest.raises(ValidationError) as exc:
        ProjectImage(project=make_project(), image=png(), alt_text="").full_clean(
            exclude=["project"]
        )
    assert "alt_text" in exc.value.message_dict


@pytest.mark.django_db
def test_project_m2m_relations() -> None:
    p = make_project()
    p.save()
    tech = Technology.objects.create(name="Django", slug="django")
    svc = Service.objects.create(name="Web Apps", slug="web-apps", summary="s")
    p.technologies.add(tech)
    p.services.add(svc)
    assert list(tech.projects.all()) == [p]
    assert list(svc.projects.all()) == [p]


@pytest.mark.django_db
def test_testimonial_rating_constraint() -> None:
    portfolio_models.Testimonial.objects.create(author_name="A", quote="Great", rating=5)
    portfolio_models.Testimonial.objects.create(author_name="B", quote="Fine", rating=None)
    with pytest.raises(IntegrityError), transaction.atomic():
        portfolio_models.Testimonial.objects.create(author_name="C", quote="?", rating=6)


@pytest.mark.parametrize(
    ("dirty", "forbidden"),
    [
        ("<p>hi</p><script>alert(1)</script>", "<script"),
        ('<img src="https://x/y.png" onerror="alert(1)">', "onerror"),
        ('<a href="javascript:alert(1)">x</a>', "javascript:"),
        ("<iframe src='https://evil'></iframe>", "<iframe"),
        ('<p style="background:url(x)">x</p>', "style="),
    ],
)
def test_rich_text_is_sanitized(dirty: str, forbidden: str) -> None:
    assert forbidden not in sanitize_rich_text(dirty)


def test_safe_links_keep_href_and_get_rel() -> None:
    out = sanitize_rich_text('<a href="https://adyraforge.com">x</a>')
    assert 'href="https://adyraforge.com"' in out
    assert "noopener" in out


@pytest.mark.django_db
def test_blog_body_is_sanitized_on_save_and_published_at_set() -> None:
    post = BlogPost.objects.create(
        title="Hello", slug="hello", body="<p>ok</p><script>x()</script>", published=True
    )
    post.refresh_from_db()
    assert "<script" not in post.body and "<p>ok</p>" in post.body
    assert post.published_at is not None
