"""DRF throttles keyed on apps.core.security.client_ip.

DRF's own get_ident() can only count a fixed number of proxies (NUM_PROXIES). Our
proxy path differs per request (via Netlify, or straight to Render), so every
throttle in the project uses these subclasses; tests/test_client_ip.py fails if a
stock DRF throttle class is used anywhere.
"""

from rest_framework import throttling
from rest_framework.request import Request

from .security import client_ip


class _ClientIPMixin:
    def get_ident(self, request: Request) -> str:
        return client_ip(request) or super().get_ident(request)  # type: ignore[misc]


class AnonRateThrottle(_ClientIPMixin, throttling.AnonRateThrottle):
    pass


class UserRateThrottle(_ClientIPMixin, throttling.UserRateThrottle):
    pass


class ScopedRateThrottle(_ClientIPMixin, throttling.ScopedRateThrottle):
    pass
