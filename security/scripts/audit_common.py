"""Shared helpers for the live-stack attack scripts (run inside the backend container).

Credentials for the throwaway audit accounts live only in /tmp/audit_creds.json
inside the container (written by audit_fixtures.py, mode 600). Never committed.
"""

import json
import os
import sys

import requests

API = os.environ.get("AUDIT_API", "http://127.0.0.1:8000")
FRONTEND = os.environ.get("AUDIT_FRONTEND", "http://frontend:3000")
CREDS_PATH = "/tmp/audit_creds.json"  # noqa: S108 - container-only, mode 600

_failures: list[str] = []


def creds() -> dict:
    with open(CREDS_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def check(label: str, ok: bool, detail: str = "") -> None:
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {label}" + (f"  ->  {detail}" if detail else ""))
    if not ok:
        _failures.append(label)


def done() -> None:
    print(f"\n{len(_failures)} failure(s)")
    for f in _failures:
        print(f"  - {f}")
    sys.exit(1 if _failures else 0)


def api_session(email: str, password: str, base: str = API, headers: dict | None = None):
    """Log in through the real API (CSRF flow included). Returns (session, csrf_token)."""
    s = requests.Session()
    if headers:
        s.headers.update(headers)
    token = s.get(f"{base}/api/auth/csrf/", timeout=10).json()["csrfToken"]
    r = s.post(
        f"{base}/api/auth/login/",
        json={"email": email, "password": password},
        headers={"X-CSRFToken": token},
        timeout=15,
    )
    if r.status_code != 200:
        raise SystemExit(f"login failed for {email}: {r.status_code} {r.text[:200]}")
    # Django rotates the CSRF token at login; fetch the new one.
    token = s.get(f"{base}/api/auth/csrf/", timeout=10).json()["csrfToken"]
    return s, token
