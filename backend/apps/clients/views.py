"""Client portal API. Everything is scoped with owned_by(request.user).

A client asking for another client's object gets 404, never 403, for every
method, including methods the endpoint doesn't support, so existence never
leaks (CLAUDE.md rule 6).
"""

from typing import Any

from django.conf import settings
from django.db.models import QuerySet
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.permissions import IsClient, IsClientOwner

from .downloads import download_url
from .models import ClientProject, Invoice, Message, ProjectFile
from .serializers import (
    ClientProjectDetailSerializer,
    ClientProjectListSerializer,
    InvoiceSerializer,
    MessageCreateSerializer,
    MessageReadSerializer,
    MessageSerializer,
    ProjectFileSerializer,
)


class PortalViewSet(viewsets.GenericViewSet):
    permission_classes = [IsClient, IsClientOwner]
    model: Any = None

    def get_queryset(self) -> QuerySet:
        qs = self.model.objects.owned_by(self.request.user)
        project = self.request.query_params.get("project")
        if project and hasattr(self.model, "client_project"):
            qs = qs.filter(client_project_id=project) if project.isdigit() else qs.none()
        return qs

    def http_method_not_allowed(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        # Resolve the object first: someone else's id is 404, not 405.
        if kwargs.get(self.lookup_url_kwarg or self.lookup_field) is not None:
            self.get_object()
        return super().http_method_not_allowed(request, *args, **kwargs)


class ClientProjectViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, PortalViewSet):
    model = ClientProject

    def get_queryset(self) -> QuerySet:
        return super().get_queryset().prefetch_related("milestones")

    def get_serializer_class(self) -> Any:
        return (
            ClientProjectListSerializer if self.action == "list" else ClientProjectDetailSerializer
        )

    @action(detail=True, methods=["get", "post"], url_path="messages")
    def messages(self, request: Request, pk: str | None = None) -> Response:
        project = self.get_object()
        if request.method == "POST":
            data = MessageCreateSerializer(data=request.data)
            data.is_valid(raise_exception=True)
            message = data.save(client_project=project, sender=request.user)
            body = MessageSerializer(message, context=self.get_serializer_context()).data
            return Response(body, status=status.HTTP_201_CREATED)
        thread = project.messages.select_related("sender")
        page = self.paginate_queryset(thread)
        rows = MessageSerializer(
            page if page is not None else thread, many=True, context=self.get_serializer_context()
        ).data
        return self.get_paginated_response(rows) if page is not None else Response(rows)


class MessageViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, PortalViewSet
):
    """Read the thread; the only update a client can make is marking a message read."""

    model = Message

    def get_queryset(self) -> QuerySet:
        return super().get_queryset().select_related("sender")

    def get_serializer_class(self) -> Any:
        return (
            MessageReadSerializer
            if self.action in {"update", "partial_update"}
            else MessageSerializer
        )

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        super().update(request, *args, **kwargs)
        message = self.get_object()
        return Response(MessageSerializer(message, context=self.get_serializer_context()).data)


class DownloadMixin:
    kind: str

    @action(detail=True, methods=["get"])
    def download(self, request: Request, pk: str | None = None) -> Response:
        obj = self.get_object()  # type: ignore[attr-defined]
        return Response(
            {
                "url": download_url(request, self.kind, obj),
                "expires_in": settings.DOWNLOAD_URL_MAX_AGE,
            }
        )


class ProjectFileViewSet(
    DownloadMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, PortalViewSet
):
    model = ProjectFile
    kind = "file"
    serializer_class = ProjectFileSerializer


class InvoiceViewSet(
    DownloadMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, PortalViewSet
):
    model = Invoice
    kind = "invoice"
    serializer_class = InvoiceSerializer

    @action(detail=True, methods=["get"])
    def download(self, request: Request, pk: str | None = None) -> Response:
        invoice = self.get_object()
        if not invoice.pdf:
            return Response(
                {"detail": "No PDF for this invoice yet."}, status=status.HTTP_404_NOT_FOUND
            )
        return super().download(request, pk)
