"""Short-lived signed download links for private files.

A link is bound to the requesting user and expires after DOWNLOAD_URL_MAX_AGE.
Serving re-checks the session user and ownership, so a leaked link is useless
to anyone else and goes stale within minutes. Only then is the file released:
streamed from local storage in development, or, from the private production
bucket, via a redirect to a presigned URL that expires in PRIVATE_URL_EXPIRE
seconds (the bucket itself has no public access).
"""

import re
from typing import Any

from django.conf import settings
from django.core import signing
from django.http import FileResponse, Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.core.permissions import IsClient
from apps.core.storage import presigns_urls

from .models import Invoice, ProjectFile

_SALT = "apps.clients.download"
# kind -> (model, file field)
_KINDS: dict[str, tuple[Any, str]] = {"file": (ProjectFile, "file"), "invoice": (Invoice, "pdf")}


def download_url(request: Request, kind: str, obj: Any) -> str:
    """A same-origin PATH, never an absolute URL.

    The browser reaches the API through the frontend's /api proxy (first-party
    cookies). An absolute URL built here would name the API's own host, where the
    browser holds no session cookie, so the download would always be refused.
    """
    token = signing.dumps({"k": kind, "i": obj.pk, "u": request.user.pk}, salt=_SALT)
    return reverse("signed-download", args=[token])


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" .")
    return cleaned[:150] or "download"


class SignedDownloadView(APIView):
    """Stream a private file. Every failure is a plain 404 (no oracle)."""

    permission_classes = [IsClient]

    def get(self, request: Request, token: str) -> HttpResponse:
        try:
            data = signing.loads(token, salt=_SALT, max_age=settings.DOWNLOAD_URL_MAX_AGE)
            model, field = _KINDS[data["k"]]
            object_id, user_id = int(data["i"]), int(data["u"])
        except (signing.BadSignature, KeyError, TypeError, ValueError) as exc:
            raise Http404 from exc
        if user_id != request.user.pk:
            raise Http404
        obj = get_object_or_404(model.objects.owned_by(request.user), pk=object_id)
        stored = getattr(obj, field)
        if not stored:
            raise Http404

        if isinstance(obj, ProjectFile):
            filename, content_type = obj.original_name, obj.content_type
        else:
            filename, content_type = f"{obj.number}.pdf", "application/pdf"
        safe_name = _safe_filename(filename)
        response: HttpResponse
        if presigns_urls(stored.storage):
            # Private bucket: hand over a presigned URL that dies in seconds and forces
            # a download with our filename and type (no inline rendering of uploads).
            response = HttpResponseRedirect(
                stored.storage.url(
                    stored.name,
                    parameters={
                        "ResponseContentDisposition": f'attachment; filename="{safe_name}"',
                        "ResponseContentType": content_type,
                    },
                    expire=settings.PRIVATE_URL_EXPIRE,
                )
            )
            response["Referrer-Policy"] = "no-referrer"
        else:
            response = FileResponse(
                stored.open("rb"), as_attachment=True, filename=safe_name, content_type=content_type
            )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
