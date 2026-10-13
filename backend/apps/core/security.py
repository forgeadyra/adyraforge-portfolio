from django.http import HttpRequest
from django.utils.crypto import salted_hmac

_IP_HASH_SALT = "adyraforge.core.ip_hash"


def client_ip(request: HttpRequest | None) -> str:
    """The connecting IP.

    REMOTE_ADDR only for now. Behind Render's proxy this is the proxy until
    trusted-proxy parsing is configured (README, "Known follow-ups").
    """
    if request is None:
        return ""
    return str(request.META.get("REMOTE_ADDR", ""))


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
