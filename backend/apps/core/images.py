"""Public image hardening (audit v2, finding M-2).

Public images are decoded with Pillow (rejecting non-images and decompression
bombs) and re-encoded from pixels only. That strips EXIF/XMP metadata (GPS,
device serials) and anything appended after the image data (polyglot payloads).
Private client documents are never re-encoded; they must stay byte-exact.
"""

import io
import warnings
from pathlib import Path
from typing import Any

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

# 40 megapixels is far above any real cover/avatar and well below bomb territory.
MAX_PIXELS = 40_000_000
_SAVE_OPTIONS = {
    "JPEG": {"quality": 88, "optimize": True, "progressive": True},
    "PNG": {"optimize": True},
    "WEBP": {"quality": 88, "method": 4},
    "AVIF": {"quality": 70},
}


def _open(data: bytes) -> Image.Image:
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            probe = Image.open(io.BytesIO(data))
            if probe.width * probe.height > MAX_PIXELS:
                raise ValidationError("Image dimensions are too large.", code="image_too_large")
            probe.verify()  # structural check; the object can't be reused afterwards
            image = Image.open(io.BytesIO(data))
            image.load()
        except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError,
                Image.DecompressionBombWarning) as exc:  # fmt: skip
            raise ValidationError("This image could not be read.", code="image_invalid") from exc
    return image


def validate_decodable_image(file: Any) -> None:
    position = file.tell() if hasattr(file, "tell") else 0
    file.seek(0)
    data = file.read()
    file.seek(position)
    _open(data)


def reencode_image(file: Any) -> ContentFile:
    """Pixels-only copy of an uploaded image in its original format."""
    file.seek(0)
    image = _open(file.read())
    fmt = (image.format or "PNG").upper()
    if fmt not in _SAVE_OPTIONS:
        fmt = "PNG"
    icc = image.info.get("icc_profile")  # colour profile only; no metadata
    image = ImageOps.exif_transpose(image)  # bake in orientation before EXIF is dropped
    if fmt == "JPEG" and image.mode not in {"RGB", "L"}:
        image = image.convert("RGB")
    out = io.BytesIO()
    options = dict(_SAVE_OPTIONS[fmt])
    if icc:
        options["icc_profile"] = icc
    image.save(out, format=fmt, **options)
    ext = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "AVIF": ".avif"}[fmt]
    return ContentFile(out.getvalue(), name=Path(file.name).stem + ext)


def sanitize_new_images(instance: Any, *field_names: str) -> None:
    """Re-encode image fields holding a fresh, not-yet-stored upload."""
    for name in field_names:
        field_file = getattr(instance, name)
        if field_file and not getattr(field_file, "_committed", True):
            setattr(instance, name, reencode_image(field_file))
