"""Short-lived signed download links for private files.

A link is bound to the requesting user and expires after DOWNLOAD_URL_MAX_AGE.
Serving re-checks the session user and ownership, so a leaked link is useless
to anyone else and goes stale within minutes. In production this module is
the place to swap in S3/Cloudinary presigned URLs.
"""

import re
from typing import Any

from django.conf import settings
from django.core import signing
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.core.permissions import IsClient

from .models import Invoice, ProjectFile

_SALT = "apps.clients.download"
# kind -> (model, file field)
_KINDS: dict[str, tuple[Any, str]] = {"file": (ProjectFile, "file"), "invoice": (Invoice, "pdf")}


def download_url(request: Request, kind: str, obj: Any) -> str:
    token = signing.dumps({"k": kind, "i": obj.pk, "u": request.user.pk}, salt=_SALT)
    return request.build_absolute_uri(reverse("signed-download", args=[token]))


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" .")
    return cleaned[:150] or "download"


class SignedDownloadView(APIView):
    """Stream a private file. Every failure is a plain 404 (no oracle)."""

    permission_classes = [IsClient]

    def get(self, request: Request, token: str) -> FileResponse:
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
        response = FileResponse(
            stored.open("rb"),
            as_attachment=True,
            filename=_safe_filename(filename),
            content_type=content_type,
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
