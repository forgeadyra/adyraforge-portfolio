"""Flood login / contact / planner / password reset and confirm 429 (+ Retry-After),
then confirm the axes lockout. Uses the honeypot on public forms so nothing is stored."""

import secrets

import requests
from audit_common import API, check, creds, done


def flood(label: str, n: int, send) -> None:
    codes, last = [], None
    for _ in range(n):
        last = send()
        codes.append(last.status_code)
    ok = codes[-1] == 429 and int(last.headers.get("Retry-After", "0")) > 0
    check(f"{label}: {n} requests -> last is 429 with Retry-After", ok,
          f"codes={codes} retry-after={last.headers.get('Retry-After')}")  # fmt: skip


s = requests.Session()
flood("login (5/min, random emails)", 6, lambda: s.post(
    f"{API}/api/auth/login/",
    json={"email": f"nobody-{secrets.token_hex(3)}@example.test", "password": "x" * 14},
    timeout=10))  # fmt: skip

bot = {"website": "http://spam.example", "turnstile_token": "t"}
flood("contact (5/hour)", 6, lambda: s.post(
    f"{API}/api/leads/contact/",
    json={"name": "n", "email": "n@example.test", "project_type": "other", "message": "m", **bot},
    timeout=10))  # fmt: skip
flood("planner (10/hour)", 11, lambda: s.post(
    f"{API}/api/leads/planner/", json={"project_type": "web_app", **bot}, timeout=10))
flood("password reset (3/hour)", 4, lambda: s.post(
    f"{API}/api/auth/password/reset/", json={"email": "nobody@example.test"}, timeout=10))

# Axes: 5 wrong passwords for a real account from this IP locks it, even for the right password.
c = creds()["bob"]
fresh = requests.Session()
fresh.headers["X-Forwarded-For"] = "203.0.113.200"  # ignored unless a trusted proxy count is set
codes = []
for _ in range(5):
    wrong = {"email": c["email"], "password": "wrong-pass-123"}  # gitleaks:allow (deliberately wrong)
    r = fresh.post(f"{API}/api/auth/login/", json=wrong,
                   timeout=10)  # fmt: skip
    codes.append(r.status_code)
right = fresh.post(f"{API}/api/auth/login/", json={"email": c["email"], "password": c["password"]},
                   timeout=10)  # fmt: skip
check("axes: 5th failure locks; right password then refused (429)",
      codes[-1] == 429 and right.status_code == 429, f"codes={codes} then {right.status_code}")  # fmt: skip
check("axes lockout response has no wildcard CORS",
      right.headers.get("Access-Control-Allow-Origin") in (None, ""),
      str(right.headers.get("Access-Control-Allow-Origin")))  # fmt: skip
done()
