import ipaddress

from django.conf import settings
from django.http import HttpRequest
from django.utils.crypto import salted_hmac

_IP_HASH_SALT = "adyraforge.core.ip_hash"


def _valid_ip(value: str) -> str:
    value = value.strip()
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return ""


def client_ip(request: HttpRequest | None) -> str:
    """The real client IP, used by axes, the DRF throttles and the stored IP hash.

    With TRUSTED_PROXY_COUNT = 0 (local dev, no proxy) this is REMOTE_ADDR and any
    X-Forwarded-For is ignored: it is client-controlled. With N trusted proxies in
    front (Render = 1) each one appends the address it saw, so the client is the
    N-th entry from the right; everything left of it is client-supplied and ignored.
    Same selection as DRF's NUM_PROXIES, which settings set to the same value.
    """
    if request is None:
        return ""
    remote_addr = _valid_ip(str(request.META.get("REMOTE_ADDR", "")))
    proxies = settings.TRUSTED_PROXY_COUNT
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if proxies <= 0 or not xff:
        return remote_addr
    addrs = str(xff).split(",")
    return _valid_ip(addrs[-min(proxies, len(addrs))]) or remote_addr


def hash_ip(ip: str) -> str:
    """Keyed SHA-256 of an IP (HMAC with SECRET_KEY). The raw IP is never stored.

    Stable for the lifetime of SECRET_KEY, so repeat submissions can be grouped,
    but not reversible by brute-forcing the IPv4 space without the key.
    """
    if not ip:
        return ""
    return salted_hmac(_IP_HASH_SALT, ip, algorithm="sha256").hexdigest()


def request_ip_hash(request: HttpRequest | None) -> str:
    return hash_ip(client_ip(request))
