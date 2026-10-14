"""Sentry: off without a DSN, and nothing personal or secret ever leaves (rule 14)."""

from unittest import mock

from apps.core.monitoring import init_sentry, scrub_event


def event() -> dict:
    return {
        "request": {
            "url": "https://adyraforge.netlify.app/api/files/eyJzaWduZWQ.token/",
            "query_string": "token=abc&next=/portal",
            "cookies": {"sessionid": "s3cr3t", "csrftoken": "c"},
            "data": {"email": "a@example.com", "password": "hunter2hunter2"},
            "env": {"REMOTE_ADDR": "203.0.113.9"},
            "headers": {
                "Cookie": "sessionid=s3cr3t",
                "X-CSRFToken": "c",
                "Authorization": "Bearer t",
                "X-Forwarded-For": "203.0.113.9",
                "User-Agent": "Mozilla/5.0",
            },
        },
        "user": {"id": 7, "email": "a@example.com", "ip_address": "203.0.113.9"},
    }


def test_scrub_removes_secrets_and_pii() -> None:
    out = scrub_event(event())
    flat = repr(out)
    for secret in ["s3cr3t", "hunter2", "a@example.com", "203.0.113.9", "Bearer t", "eyJzaWduZWQ"]:
        assert secret not in flat
    assert out["user"] == {"id": 7}
    assert out["request"]["headers"]["User-Agent"] == "Mozilla/5.0"
    assert out["request"]["query_string"] == "[Filtered]"


def test_scrub_tolerates_events_without_request_or_user() -> None:
    assert scrub_event({"message": "x"}) == {"message": "x"}


def test_disabled_without_dsn() -> None:
    with mock.patch("sentry_sdk.init") as init:
        assert init_sentry("", environment="production") is False
    init.assert_not_called()


def test_init_never_sends_pii_bodies_or_locals() -> None:
    with mock.patch("sentry_sdk.init") as init:
        assert init_sentry("https://k@o1.ingest.sentry.io/1", environment="production") is True
    kwargs = init.call_args.kwargs
    assert kwargs["data_collection"]["user_info"] is False
    assert kwargs["data_collection"]["stack_frame_variables"] is False
    assert kwargs["max_request_body_size"] == "never"
    assert kwargs["before_send"] is scrub_event


def test_real_init_accepts_our_options_and_keeps_them() -> None:
    """Unmocked: an unknown or renamed option would raise here, not silently pass."""
    import sentry_sdk

    try:
        assert init_sentry("https://k@o1.ingest.invalid/1", environment="test") is True
        opts = sentry_sdk.get_client().options
        dc = opts["data_collection"]  # as resolved by the SDK itself
        assert dc["provided_by_user"] is True
        assert dc["user_info"] is False
        assert dc["cookies"]["mode"] == "off"
        assert dc["http_headers"]["request"]["mode"] == "off"
        assert dc["http_bodies"] == []
        assert dc["url_query_params"]["mode"] == "off"
        assert dc["stack_frame_variables"] is False
        assert dc["database_query_data"] is False
        assert dc["graphql"] == {"document": False, "variables": False}
        assert dc["gen_ai"] == {"inputs": False, "outputs": False}
        assert opts["max_request_body_size"] == "never"
        assert opts["traces_sample_rate"] == 0.0
    finally:
        sentry_sdk.init()  # back to a disabled client for the rest of the suite
