from django.http import HttpRequest, JsonResponse
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    """Hands the SPA a CSRF token in the body and sets the (HttpOnly) cookie."""

    # Public on purpose: anonymous visitors need a token before they can log in
    # or submit the contact form. Rate-limited by the default anon throttle.
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        return Response({"csrfToken": get_token(request)})


# Generic JSON error pages: no stack traces or internals (rule 14).
def bad_request(request: HttpRequest, exception: Exception | None = None) -> JsonResponse:
    return JsonResponse({"detail": "Bad request."}, status=400)


def permission_denied(request: HttpRequest, exception: Exception | None = None) -> JsonResponse:
    return JsonResponse({"detail": "Forbidden."}, status=403)


def page_not_found(request: HttpRequest, exception: Exception | None = None) -> JsonResponse:
    return JsonResponse({"detail": "Not found."}, status=404)


def server_error(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"detail": "Server error."}, status=500)
