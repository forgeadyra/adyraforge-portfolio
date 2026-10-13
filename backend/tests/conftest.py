from collections.abc import Callable
from typing import Any

import pytest
from django.core.cache import cache

from apps.accounts.models import User


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    # Throttle counters live in the cache; keep tests independent.
    cache.clear()


@pytest.fixture
def make_user(db: Any) -> Callable[..., User]:
    counter = iter(range(1, 10_000))

    def _make(email: str | None = None, **extra: Any) -> User:
        email = email or f"client{next(counter)}@example.com"
        extra.setdefault("password", "a-long-test-password-123")
        return User.objects.create_user(email=email, **extra)

    return _make
