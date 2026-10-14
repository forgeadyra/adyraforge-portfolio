"""Can a client dodge the per-IP throttles by sending its own X-Forwarded-For?

Each request carries a different, attacker-chosen X-Forwarded-For value from the same
real connection. If any limit stops holding, the throttle is keyed on a spoofable header.
Public forms use the honeypot, so nothing is stored.
"""

import secrets

import requests
from audit_common import API, check, done

bot = {"website": "http://spam.example", "turnstile_token": "t"}


def spoofed() -> dict:
    return {"X-Forwarded-For": f"198.51.100.{secrets.randbelow(250) + 1}, 10.0.0.{secrets.randbelow(250)}"}


def flood(label: str, n: int, send) -> None:
    codes = [send().status_code for _ in range(n)]
    check(f"{label}: {n} requests with rotating X-Forwarded-For still hit 429", codes[-1] == 429,
          f"codes={codes}")  # fmt: skip


flood("contact (5/hour)", 6, lambda: requests.post(
    f"{API}/api/leads/contact/", headers=spoofed(), timeout=10,
    json={"name": "n", "email": "n@example.test", "project_type": "other", "message": "m", **bot}))  # fmt: skip
flood("planner (10/hour)", 11, lambda: requests.post(
    f"{API}/api/leads/planner/", headers=spoofed(), json={"project_type": "web_app", **bot},
    timeout=10))  # fmt: skip
flood("password reset (3/hour)", 4, lambda: requests.post(
    f"{API}/api/auth/password/reset/", headers=spoofed(), json={"email": "nobody@example.test"},
    timeout=10))  # fmt: skip
flood("login (5/min)", 6, lambda: requests.post(
    f"{API}/api/auth/login/", headers=spoofed(), timeout=10,
    json={"email": f"nobody-{secrets.token_hex(3)}@example.test", "password": "x" * 14}))  # fmt: skip
done()
