"""Tiny in-memory files for upload tests."""

import io

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image


def png(name: str = "shot.png", size: tuple[int, int] = (4, 4)) -> SimpleUploadedFile:
    buf = io.BytesIO()
    Image.new("RGB", size, (212, 175, 55)).save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


def pdf(name: str = "invoice.pdf") -> SimpleUploadedFile:
    body = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
    return SimpleUploadedFile(name, body, content_type="application/pdf")


def svg(name: str = "logo.svg") -> SimpleUploadedFile:
    body = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    return SimpleUploadedFile(name, body, content_type="image/svg+xml")


def html_as_png(name: str = "innocent.png") -> SimpleUploadedFile:
    body = b"<!doctype html><html><script>alert(1)</script></html>"
    # The client lies about the content type; detection must not trust it.
    return SimpleUploadedFile(name, body, content_type="image/png")
