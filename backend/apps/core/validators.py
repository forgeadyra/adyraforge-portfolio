"""Reusable validators for uploads and JSON fields (CLAUDE.md rule 9)."""

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import filetype
from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible

MB = 1024 * 1024

# Detected MIME type -> extensions allowed for it. SVG and HTML are never
# accepted: both can carry script.
IMAGE_TYPES: dict[str, list[str]] = {
    "image/jpeg": [".jpg", ".jpeg"],
    "image/png": [".png"],
    "image/webp": [".webp"],
    "image/avif": [".avif"],
}
PDF_TYPES: dict[str, list[str]] = {"application/pdf": [".pdf"]}
DOCUMENT_TYPES: dict[str, list[str]] = {
    **IMAGE_TYPES,
    **PDF_TYPES,
    "application/zip": [".zip"],
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": [".pptx"],
}


def detect_mime(file: Any) -> str | None:
    """MIME type from the file's magic bytes (never from its name or the client)."""
    position = file.tell() if hasattr(file, "tell") else 0
    file.seek(0)
    head = file.read(8192)
    file.seek(position)
    kind = filetype.guess(head)
    return kind.mime if kind else None


@deconstructible
class FileTypeValidator:
    """Allowlist by detected content type, require a matching extension, cap size."""

    def __init__(self, allowed: dict[str, list[str]], max_bytes: int) -> None:
        self.allowed = allowed
        self.max_bytes = max_bytes

    def __call__(self, file: Any) -> None:
        if file.size > self.max_bytes:
            raise ValidationError(
                "File is too large (max %(mb)s MB).",
                code="file_too_large",
                params={"mb": self.max_bytes // MB},
            )
        mime = detect_mime(file)
        if mime not in self.allowed:
            raise ValidationError("This file type is not allowed.", code="file_type")
        if Path(file.name).suffix.lower() not in self.allowed[mime]:
            raise ValidationError(
                "The file extension does not match its contents.", code="file_extension"
            )

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, FileTypeValidator)
            and self.allowed == other.allowed
            and self.max_bytes == other.max_bytes
        )


@deconstructible
class UUIDUploadTo:
    """Store uploads as <prefix>/<uuid4><ext>; the user's filename is never used on disk."""

    def __init__(self, prefix: str) -> None:
        self.prefix = prefix.strip("/")

    def __call__(self, instance: Any, filename: str) -> str:
        ext = Path(filename).suffix.lower()
        if not ext[1:].isalnum() or len(ext) > 6:
            ext = ""
        return f"{self.prefix}/{uuid4().hex}{ext}"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, UUIDUploadTo) and self.prefix == other.prefix


@deconstructible
class JSONSizeValidator:
    """Cap the serialised size of a JSONField value."""

    def __init__(self, max_bytes: int) -> None:
        self.max_bytes = max_bytes

    def __call__(self, value: Any) -> None:
        if len(json.dumps(value, separators=(",", ":"))) > self.max_bytes:
            raise ValidationError("This data is too large.", code="json_too_large")

    def __eq__(self, other: object) -> bool:
        return isinstance(other, JSONSizeValidator) and self.max_bytes == other.max_bytes


image_validator = FileTypeValidator(IMAGE_TYPES, 5 * MB)
pdf_validator = FileTypeValidator(PDF_TYPES, 10 * MB)
document_validator = FileTypeValidator(DOCUMENT_TYPES, 25 * MB)
