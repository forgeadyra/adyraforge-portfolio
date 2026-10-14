import base64
import binascii
import hashlib
import hmac
import ipaddress
import json
import time
from typing import Any

from django.conf import settings
from django.http import HttpRequest
from django.utils.crypto import salted_hmac

_IP_HASH_SALT = "adyraforge.core.ip_hash"
_CACHE_ATTR = "_adyraforge_client_ip"


def _valid_ip(value: str) -> str:
    value = value.strip()
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return ""


def _b64url(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def via_netlify_proxy(request: HttpRequest) -> bool:
    """True only for requests our Netlify site proxied to us (a signed proxy redirect).

    Netlify signs each proxied request with an HS256 JWS in `x-nf-sign`, keyed by
    NETLIFY_PROXY_SIGNING_SECRET (an env var on both sides). Anyone can call the
    Render origin directly, so Netlify's client-IP header is only believable when
    this signature verifies, is unexpired, and names our own site.
    """
    secret = settings.NETLIFY_PROXY_SIGNING_SECRET
    token = str(request.META.get("HTTP_X_NF_SIGN", ""))
    if not secret or token.count(".") != 2:
        return False
    header_part, payload_part, signature_part = token.split(".")
    try:
        header: Any = json.loads(_b64url(header_part))
        payload: Any = json.loads(_b64url(payload_part))
        signature = _b64url(signature_part)
    except (ValueError, binascii.Error):
        return False
    if not isinstance(header, dict) or header.get("alg") != "HS256":
        return False  # never "none" or another algorithm
    expected = hmac.new(
        secret.encode(), f"{header_part}.{payload_part}".encode(), hashlib.sha256
    ).digest()
    if not hmac.compare_digest(expected, signature) or not isinstance(payload, dict):
        return False
    exp = payload.get("exp")
    return (
        payload.get("iss") == "netlify"
        and isinstance(exp, int | float)
        and exp > time.time()
        and str(payload.get("site_url", "")).rstrip("/") == settings.FRONTEND_URL
    )


def client_ip(request: HttpRequest | None) -> str:
    """The real client IP, used by axes, every DRF throttle and the stored IP hash.

    Browser traffic arrives  client -> Netlify (proxy) -> Render -> Django.
    Server-side traffic (Next build/ISR/middleware, admin) arrives  caller -> Render.

    1. Signed by our Netlify site: Netlify's X-Nf-Client-Connection-Ip, the one
       client-IP header Netlify commits to forwarding to proxy origins.
    2. Otherwise X-Forwarded-For with TRUSTED_PROXY_COUNT trusted hops (Render = 1):
       the N-th entry from the right was written by our own proxy; everything left
       of it is client-supplied and ignored.
    3. Otherwise REMOTE_ADDR (local development, no proxy).
    """
    if request is None:
        return ""
    cached = getattr(request, _CACHE_ATTR, None)
    if cached is not None:
        return cached

    ip = ""
    if via_netlify_proxy(request):
        ip = _valid_ip(str(request.META.get("HTTP_X_NF_CLIENT_CONNECTION_IP", "")))
    if not ip:
        remote_addr = _valid_ip(str(request.META.get("REMOTE_ADDR", "")))
        proxies = settings.TRUSTED_PROXY_COUNT
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if proxies > 0 and xff:
            addrs = str(xff).split(",")
            ip = _valid_ip(addrs[-min(proxies, len(addrs))]) or remote_addr
        else:
            ip = remote_addr
    setattr(request, _CACHE_ATTR, ip)
    return ip


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
