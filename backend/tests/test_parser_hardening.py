"""Regression: malformed / pathological bodies are 400s, never 500s (audit v2, finding M-1)."""

import pytest
from django.test import Client

from apps.core.parsers import MAX_JSON_DEPTH, json_depth

pytestmark = pytest.mark.django_db

PUBLIC_JSON_ENDPOINTS = [
    "/api/auth/login/",
    "/api/auth/password/reset/",
    "/api/auth/password/reset/confirm/",
    "/api/auth/invite/accept/",
    "/api/leads/contact/",
    "/api/leads/planner/",
]


def post(path: str, body: str):
    return Client(raise_request_exception=False).post(path, body, content_type="application/json")


@pytest.mark.parametrize("path", PUBLIC_JSON_ENDPOINTS)
@pytest.mark.parametrize("depth", [MAX_JSON_DEPTH + 1, 1_000, 100_000])
def test_deeply_nested_json_is_400(path: str, depth: int) -> None:
    resp = post(path, "[" * depth + "]" * depth)
    assert resp.status_code == 400, resp.content[:200]
    assert resp.json() == {"detail": "JSON is nested too deeply."}


@pytest.mark.parametrize("path", PUBLIC_JSON_ENDPOINTS)
@pytest.mark.parametrize(
    "body", ["[]", "[1, 2]", '"string"', "42", "null", "{bad json", "\x00\xff"]
)
def test_non_object_or_malformed_bodies_are_400(path: str, body: str) -> None:
    assert post(path, body).status_code == 400


def test_planner_rejects_deep_answers_object() -> None:
    nested: dict = {}
    cursor = nested
    for _ in range(MAX_JSON_DEPTH + 5):
        cursor["x"] = {}
        cursor = cursor["x"]
    import json

    resp = post("/api/leads/planner/", json.dumps({"project_type": "web_app", "answers": nested}))
    assert resp.status_code == 400


def test_json_depth() -> None:
    assert json_depth(1) == 0
    assert json_depth([]) == 1
    assert json_depth({"a": [1, {"b": []}]}) == 4  # dict > list > dict > list
