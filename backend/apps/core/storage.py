import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage, Storage, storages
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateMediaStorage(FileSystemStorage):
    """Development/test backend for client files and invoices.

    Outside MEDIA_ROOT and never given a public URL: files are only reachable through
    the ownership-checked signed download view, which streams them. Production uses a
    private S3-compatible bucket instead (settings STORAGES["private"]).
    """

    @property  # type: ignore[override]
    def base_location(self) -> str:
        return str(settings.PRIVATE_MEDIA_ROOT)

    @property  # type: ignore[override]
    def location(self) -> str:
        return os.path.abspath(self.base_location)

    def url(self, name: str | None) -> str:
        raise NotImplementedError("Private files have no public URL; use a signed download view.")


def private_storage() -> Storage:
    """Storage for client files and invoices, chosen per environment via STORAGES["private"].

    A callable keeps migrations independent of the backend: filesystem locally, a
    private bucket (presigned URLs only) in production.
    """
    return storages["private"]


def presigns_urls(storage: Storage) -> bool:
    """True for a private bucket backend that hands out expiring signed URLs."""
    return bool(getattr(storage, "querystring_auth", False))
