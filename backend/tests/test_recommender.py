from adyra_ml.similarity import (
    ProjectFeatures,
    jaccard,
    recommend_services,
    similar_projects,
    similarity,
)


def f(id_: int, services=(), tech=(), industry="", order=0) -> ProjectFeatures:
    return ProjectFeatures(id_, frozenset(services), frozenset(tech), industry, order)


def test_jaccard() -> None:
    assert jaccard(frozenset({"a", "b"}), frozenset({"b", "c"})) == 1 / 3
    assert jaccard(frozenset(), frozenset({"a"})) == 0.0


def test_similarity_weights_services_over_tech_over_industry() -> None:
    target = f(1, services={"web"}, tech={"react"}, industry="Health")
    same_service = f(2, services={"web"})
    same_tech = f(3, tech={"react"})
    same_industry = f(4, industry="health")
    assert similarity(target, same_service) > similarity(target, same_tech)
    assert similarity(target, same_tech) > similarity(target, same_industry) > 0


def test_similar_projects_excludes_self_and_unrelated() -> None:
    target = f(1, services={"web"}, tech={"react"})
    pool = [target, f(2, services={"web"}), f(3, tech={"vue"}), f(4, tech={"react"})]
    assert similar_projects(target, pool) == [2, 4]


def test_similar_projects_respects_k_and_breaks_ties_by_order() -> None:
    target = f(1, services={"web"})
    pool = [f(i, services={"web"}, order=10 - i) for i in range(2, 7)]
    assert similar_projects(target, pool, k=2) == [6, 5]


def test_recommend_services() -> None:
    assert recommend_services("landing_page") == ["landing-pages"]
    assert recommend_services("business_website", ["Online booking"]) == [
        "websites",
        "web-applications",
    ]
    assert recommend_services("unknown") == ["websites"]
