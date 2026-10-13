"""Bridge between Django models and the adyra_ml package."""

from collections.abc import Iterable

from adyra_ml.similarity import ProjectFeatures, recommend_services, similar_projects
from apps.portfolio.models import Project, Service


def _features(project: Project) -> ProjectFeatures:
    return ProjectFeatures(
        id=project.pk,
        services=frozenset(s.slug for s in project.services.all()),
        technologies=frozenset(t.slug for t in project.technologies.all()),
        industry=project.industry,
        order=project.order,
    )


def similar_to(project: Project, k: int = 3) -> list[Project]:
    pool = list(
        Project.objects.published()
        .prefetch_related("services", "technologies")
        .exclude(pk=project.pk)
    )
    ids = similar_projects(_features(project), [_features(p) for p in pool], k=k)
    by_id = {p.pk: p for p in pool}
    return [by_id[i] for i in ids]


def services_for(project_type: str, features: Iterable[str] = ()) -> list[Service]:
    slugs = recommend_services(project_type, features)
    found = {s.slug: s for s in Service.objects.published().filter(slug__in=slugs)}
    return [found[s] for s in slugs if s in found]
