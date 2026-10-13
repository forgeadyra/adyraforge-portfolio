from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse


def lockout_response(
    request: HttpRequest, original_response: HttpResponse | None = None, credentials: Any = None
) -> JsonResponse:
    """django-axes lockout response.

    Replaces axes' default JSON response, which sets Access-Control-Allow-Origin
    from AXES_ALLOWED_CORS_ORIGINS (default "*") and would bypass the CORS
    allowlist. The message is the same whether or not the account exists.
    """
    response = JsonResponse({"detail": "Too many failed attempts. Try again later."}, status=429)
    response["Retry-After"] = str(int(settings.AXES_COOLOFF_TIME.total_seconds()))
    return response
