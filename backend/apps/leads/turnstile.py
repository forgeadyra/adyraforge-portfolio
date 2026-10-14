"""Server-side Cloudflare Turnstile verification (CLAUDE.md rule 10). Fails closed."""

import json
import logging
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings

log = logging.getLogger(__name__)

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def verify_turnstile(token: str) -> bool:
    if not token or len(token) > 2048 or not settings.TURNSTILE_SECRET_KEY:
        return False
    # The visitor's IP is deliberately not sent to Cloudflare (optional field).
    body = urlencode({"secret": settings.TURNSTILE_SECRET_KEY, "response": token}).encode()
    request = Request(VERIFY_URL, data=body, method="POST")
    try:
        with urlopen(request, timeout=5) as response:  # noqa: S310 (fixed https URL)
            payload = json.load(response)
    except (URLError, TimeoutError, ValueError):
        log.warning("Turnstile verification unavailable; rejecting submission")
        return False
    # Anything but {"success": true} is a rejection, including a non-object body.
    if not isinstance(payload, dict) or payload.get("success") is not True:
        return False
    expected = settings.TURNSTILE_EXPECTED_HOSTNAME
    return not expected or payload.get("hostname") == expected
