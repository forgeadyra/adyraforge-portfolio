"""Content-based recommendations.

Baseline that works with a handful of projects: weighted Jaccard overlap of
services and technologies plus an industry match. A learned model (scikit-learn)
can replace these functions once planner/lead data exists to train on; the
backend only depends on the signatures below.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

SERVICE_WEIGHT = 0.5
TECH_WEIGHT = 0.35
INDUSTRY_WEIGHT = 0.15


@dataclass(frozen=True)
class ProjectFeatures:
    id: int
    services: frozenset[str] = field(default_factory=frozenset)
    technologies: frozenset[str] = field(default_factory=frozenset)
    industry: str = ""
    order: int = 0


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def similarity(a: ProjectFeatures, b: ProjectFeatures) -> float:
    industry = 1.0 if a.industry and a.industry.lower() == b.industry.lower() else 0.0
    return (
        SERVICE_WEIGHT * jaccard(a.services, b.services)
        + TECH_WEIGHT * jaccard(a.technologies, b.technologies)
        + INDUSTRY_WEIGHT * industry
    )


def similar_projects(
    target: ProjectFeatures, candidates: Iterable[ProjectFeatures], k: int = 3
) -> list[int]:
    """Ids of up to k candidates that genuinely overlap with target, best first.

    Unrelated projects are never padded in: "similar" must mean similar.
    """
    scored = [(similarity(target, c), c) for c in candidates if c.id != target.id]
    scored = [(s, c) for s, c in scored if s > 0]
    scored.sort(key=lambda sc: (-sc[0], sc[1].order, sc[1].id))
    return [c.id for _, c in scored[:k]]


# Planner: which services fit a request. Slugs match portfolio.Service.slug.
_BY_PROJECT_TYPE: dict[str, Sequence[str]] = {
    "landing_page": ("landing-pages",),
    "business_website": ("websites",),
    "ecommerce": ("websites", "web-applications"),
    "web_app": ("web-applications",),
    "redesign": ("websites",),
    "other": ("websites",),
}
_APP_FEATURE_HINTS = ("login", "portal", "dashboard", "account", "payment", "booking", "admin")


def recommend_services(project_type: str, features: Iterable[str] = ()) -> list[str]:
    slugs = list(_BY_PROJECT_TYPE.get(project_type, ("websites",)))
    text = " ".join(features).lower()
    if any(hint in text for hint in _APP_FEATURE_HINTS) and "web-applications" not in slugs:
        slugs.append("web-applications")
    return slugs
