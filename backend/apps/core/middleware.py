from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse


class PermissionsPolicyMiddleware:
    """Adds the Permissions-Policy header (Django has no built-in setting for it)."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        self.value: str = settings.PERMISSIONS_POLICY

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        response.headers.setdefault("Permissions-Policy", self.value)
        return response


# /healthz/ for platform probes (Render, Docker), /api/health for uptime monitors.
HEALTH_PATHS = frozenset({"/healthz/", "/api/health", "/api/health/"})


class HealthCheckMiddleware:
    """Liveness probe at HEALTH_PATHS, answered before host validation.

    Docker's HEALTHCHECK and platform probes call the container by IP, which is not
    in ALLOWED_HOSTS, so a normal view returns 400 under production settings (audit
    v2). Returns no data and touches no database. Placed after the header-only
    middlewares so the response still carries the full security header set.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.path in HEALTH_PATHS and request.method in ("GET", "HEAD"):
            return JsonResponse({"status": "ok"})
        return self.get_response(request)
