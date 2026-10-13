"""Public images are decoded and re-encoded: no metadata, no appended payloads (audit v2, M-2)."""

import io

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.clients.models import ClientProfile, ClientProject, ProjectFile
from apps.core.images import MAX_PIXELS, validate_decodable_image
from apps.portfolio import models as portfolio_models

PHP = b"<?php system($_GET['c']); ?>"
JS = b"<script>alert(1)</script>"


def jpeg_with_gps(payload: bytes = b"") -> SimpleUploadedFile:
    img = Image.new("RGB", (8, 8), (212, 175, 55))
    exif = Image.Exif()
    exif[0x010F] = "SecretPhoneMaker"  # Make
    exif[0x8825] = {1: "N", 2: (28.0, 36.0, 50.0), 3: "E", 4: (77.0, 12.0, 30.0)}  # GPS IFD
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    return SimpleUploadedFile("photo.jpg", buf.getvalue() + payload, content_type="image/jpeg")


def png_polyglot() -> SimpleUploadedFile:
    buf = io.BytesIO()
    Image.new("RGBA", (4, 4), (0, 0, 0, 0)).save(buf, format="PNG")
    return SimpleUploadedFile("poly.png", buf.getvalue() + PHP + JS, content_type="image/png")


@pytest.mark.django_db
def test_public_image_is_stripped_of_exif_gps_and_appended_payload() -> None:
    t = portfolio_models.Testimonial.objects.create(
        author_name="A", quote="q", avatar=jpeg_with_gps(PHP + JS)
    )
    stored = t.avatar.open("rb").read()
    assert PHP not in stored and JS not in stored
    assert b"SecretPhoneMaker" not in stored
    reread = Image.open(io.BytesIO(stored))
    assert reread.format == "JPEG"
    assert not reread.getexif()  # no EXIF at all, so no GPS
    assert t.avatar.name.startswith("testimonials/") and "photo" not in t.avatar.name


@pytest.mark.django_db
def test_png_polyglot_is_neutralised_and_transparency_kept() -> None:
    p = portfolio_models.Project.objects.create(
        title="P", slug="p", cover_image=png_polyglot(), cover_alt="alt"
    )
    stored = p.cover_image.open("rb").read()
    assert PHP not in stored and JS not in stored
    assert Image.open(io.BytesIO(stored)).mode == "RGBA"


@pytest.mark.django_db
def test_existing_images_are_not_re_encoded_on_every_save() -> None:
    p = portfolio_models.Project.objects.create(
        title="P", slug="p", cover_image=png_polyglot(), cover_alt="alt"
    )
    first = p.cover_image.name
    p.title = "Renamed"
    p.save()
    assert p.cover_image.name == first


@pytest.mark.django_db
def test_private_client_documents_stay_byte_exact(make_user) -> None:
    profile = ClientProfile.objects.create(user=make_user(email="c@example.com"))
    project = ClientProject.objects.create(client=profile, title="x")
    original = png_polyglot()
    raw = original.read()
    original.seek(0)
    f = ProjectFile.objects.create(client_project=project, file=original)
    assert f.file.open("rb").read() == raw  # deliverables are never altered


def test_truncated_or_fake_images_are_rejected() -> None:
    fake = SimpleUploadedFile("x.png", b"\x89PNG\r\n\x1a\n" + b"garbage" * 10)
    with pytest.raises(ValidationError):
        validate_decodable_image(fake)


def test_decompression_bomb_dimensions_are_rejected() -> None:
    # A tiny file that claims an enormous canvas: rejected before decoding pixels.
    buf = io.BytesIO()
    Image.new("1", (8000, 6000)).save(buf, format="PNG")
    assert MAX_PIXELS < 8000 * 6000
    with pytest.raises(ValidationError):
        validate_decodable_image(SimpleUploadedFile("bomb.png", buf.getvalue()))
