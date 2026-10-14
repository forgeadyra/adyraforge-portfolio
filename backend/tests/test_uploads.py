from pathlib import Path

import pytest
from django.conf import settings
from django.core.exceptions import ValidationError

from apps.core.storage import private_storage
from apps.core.validators import (
    MB,
    UUIDUploadTo,
    document_validator,
    image_validator,
    pdf_validator,
)
from tests.files import html_as_png, pdf, png, svg


def test_real_png_and_pdf_are_accepted() -> None:
    image_validator(png())
    pdf_validator(pdf())
    document_validator(png())
    document_validator(pdf())


@pytest.mark.parametrize("upload", [svg(), html_as_png()], ids=["svg", "html-renamed-png"])
def test_scriptable_files_are_rejected_whatever_they_claim(upload) -> None:
    with pytest.raises(ValidationError) as exc:
        image_validator(upload)
    assert exc.value.code == "file_type"


def test_extension_must_match_content() -> None:
    with pytest.raises(ValidationError) as exc:
        pdf_validator(pdf(name="invoice.exe"))
    assert exc.value.code == "file_extension"
    with pytest.raises(ValidationError):
        image_validator(png(name="photo.pdf"))


def test_pdf_validator_rejects_images() -> None:
    with pytest.raises(ValidationError):
        pdf_validator(png())


def test_size_cap_is_enforced() -> None:
    big = png()
    big.size = 6 * MB
    with pytest.raises(ValidationError) as exc:
        image_validator(big)
    assert exc.value.code == "file_too_large"


def test_uploads_are_renamed_to_uuid() -> None:
    path = UUIDUploadTo("client-files")(None, "../../etc/My Contract (final).PDF")
    folder, name = path.split("/")
    assert folder == "client-files"
    assert name.endswith(".pdf")
    assert len(Path(name).stem) == 32
    assert "Contract" not in path and ".." not in path


def test_weird_extensions_are_dropped() -> None:
    assert "." not in UUIDUploadTo("x")(None, "payload.p<h>p").split("/")[1]


def test_private_storage_is_outside_public_media_and_has_no_url() -> None:
    private = Path(private_storage().location).resolve()
    public = Path(settings.MEDIA_ROOT).resolve()
    assert private != public and public not in private.parents
    with pytest.raises(NotImplementedError):
        private_storage().url("client-files/abc.pdf")
