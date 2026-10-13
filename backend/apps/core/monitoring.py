"""Sentry error monitoring with PII scrubbing (CLAUDE.md rule 14).

Off unless SENTRY_DSN is set. Never sends passwords, tokens, cookies, request bodies,
IP addresses or stack-frame local variables.
"""

from typing import Any

# Headers that may carry credentials or identify the visitor.
_SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-csrftoken",
    "x-forwarded-for",
    "x-real-ip",
    "cf-connecting-ip",
}
_FILTERED = "[Filtered]"

# sentry-sdk's data_collection: a partial dict means "collect everything else", so every
# category is listed and switched off. scrub_event below is the second layer.
_OFF = {"mode": "off"}
DATA_COLLECTION: dict[str, Any] = {
    "user_info": False,
    "cookies": _OFF,
    "http_headers": {"request": _OFF},
    "http_bodies": [],
    "url_query_params": _OFF,
    "graphql": {"document": False, "variables": False},
    "gen_ai": {"inputs": False, "outputs": False},
    "database_query_data": False,
    "queues": False,
    "stack_frame_variables": False,  # frame locals can hold passwords and tokens
}


def scrub_event(event: dict[str, Any], hint: dict[str, Any] | None = None) -> dict[str, Any]:
    """before_send / before_send_transaction hook: strip anything personal or secret."""
    request = event.get("request")
    if isinstance(request, dict):
        request.pop("cookies", None)
        request.pop("data", None)
        request.pop("env", None)  # REMOTE_ADDR etc.
        if request.get("query_string"):
            # Signed download tokens, reset/invite tokens can sit in URLs.
            request["query_string"] = _FILTERED
        headers = request.get("headers")
        if isinstance(headers, dict):
            for name in list(headers):
                if name.lower() in _SENSITIVE_HEADERS:
                    headers[name] = _FILTERED
        url = request.get("url")
        if isinstance(url, str) and "/api/files/" in url:
            request["url"] = url.split("/api/files/")[0] + "/api/files/" + _FILTERED
    user = event.get("user")
    if isinstance(user, dict):
        # Keep only the opaque id: no email, username or IP.
        event["user"] = {"id": user["id"]} if "id" in user else {}
    return event


def init_sentry(dsn: str, environment: str, release: str = "") -> bool:
    if not dsn:
        return False
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release or None,
        integrations=[DjangoIntegration()],
        data_collection=DATA_COLLECTION,  # no user, cookies, headers, bodies, query, locals
        max_request_body_size="never",
        traces_sample_rate=0.0,  # errors only; no performance data
        before_send=scrub_event,
        before_send_transaction=scrub_event,
    )
    return True
