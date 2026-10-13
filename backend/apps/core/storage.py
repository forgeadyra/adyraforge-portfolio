import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateMediaStorage(FileSystemStorage):
    """Client files and invoices: outside MEDIA_ROOT, never given a public URL.

    Files are only reachable through an authorised view that checks ownership
    and issues a short-lived signed URL (API phase). Swap for a private
    S3/Cloudinary bucket in production.
    """

    @property  # type: ignore[override]
    def base_location(self) -> str:
        return str(settings.PRIVATE_MEDIA_ROOT)

    @property  # type: ignore[override]
    def location(self) -> str:
        return os.path.abspath(self.base_location)

    def url(self, name: str | None) -> str:
        raise NotImplementedError("Private files have no public URL; use a signed download view.")


private_storage = PrivateMediaStorage()
