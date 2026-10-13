"""Probe the backend running with PRODUCTION settings (gunicorn, DEBUG=False).

Targets two throwaway containers on the compose network:
  AUDIT_PROD       production settings, real (dev) database
  AUDIT_PROD_NODB  same image and settings, database unreachable -> forced 500s
Requests carry X-Forwarded-Proto: https as Render's proxy would. Cookies are handled
by hand because `requests` (correctly) refuses to send Secure cookies over plain http.
"""

import json
import os
import re
import secrets

import requests
from audit_common import check, creds, done

PROD = os.environ["AUDIT_PROD"]
NODB = os.environ["AUDIT_PROD_NODB"]
ADMIN_URL = os.environ["AUDIT_ADMIN_URL"].strip("/")
HOST = "api.adyraforge.test"
BASE = {"Host": HOST, "X-Forwarded-Proto": "https", "Origin": "https://adyraforge.test",
        "Referer": "https://adyraforge.test/"}  # fmt: skip
LEAK = re.compile(r"Traceback|File \"/|site-packages|psycopg|OperationalError|DEBUG = True|"
                  r"Django tried these URL patterns|settings\.py|SECRET_KEY|/app/backend", re.I)  # fmt: skip


class Jar:
    """Minimal cookie jar that also sends Secure cookies (we are the TLS-terminating proxy)."""

    def __init__(self) -> None:
        self.cookies: dict[str, str] = {}
        self.raw: list[str] = []
        # Each jar is a distinct visitor: the "proxy" (us) appends its client IP, as
        # Render does; TRUSTED_PROXY_COUNT=1 makes Django use exactly that entry.
        self.ip = f"198.51.100.{secrets.randbelow(250) + 1}"

    def req(self, method: str, url: str, base: str = PROD, **kw) -> requests.Response:
        headers = {**BASE, "X-Forwarded-For": self.ip, **kw.pop("headers", {})}
        if self.cookies:
            headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
        r = requests.request(method, base + url, headers=headers, allow_redirects=False,
                             timeout=20, **kw)  # fmt: skip
        r.set_cookies = r.raw.headers.getlist("Set-Cookie")
        for raw in r.set_cookies:
            self.raw.append(raw)
            name, _, rest = raw.partition("=")
            value = rest.split(";", 1)[0]
            if value in ("", '""') or "max-age=0" in raw.lower():
                self.cookies.pop(name, None)
            else:
                self.cookies[name] = value
        return r

    def csrf(self) -> str:
        return self.req("GET", "/api/auth/csrf/").json()["csrfToken"]


def no_leak(label: str, r: requests.Response) -> None:
    m = LEAK.search(r.text)
    check(f"{label}: no stack trace / internals in body", m is None,
          f"matched {m.group(0)!r}" if m else f"{r.status_code} {r.text[:90]!r}")  # fmt: skip


print("== transport & headers ==")
r = requests.get(PROD + "/api/public/projects/", headers={"Host": HOST}, allow_redirects=False,
                 timeout=20)  # fmt: skip
check("plain http is redirected to https (SECURE_SSL_REDIRECT)",
      r.status_code == 301 and r.headers.get("Location", "").startswith("https://"),
      f"{r.status_code} {r.headers.get('Location')}")  # fmt: skip
r = Jar().req("GET", "/api/public/projects/")
print(f"GET /api/public/projects/ -> {r.status_code}")
for name in ["Strict-Transport-Security", "X-Content-Type-Options", "X-Frame-Options",
             "Referrer-Policy", "Content-Security-Policy", "Permissions-Policy",
             "Cross-Origin-Opener-Policy", "Server", "X-Powered-By"]:  # fmt: skip
    print(f"    {name}: {r.headers.get(name)}")
hsts = r.headers.get("Strict-Transport-Security", "")
check("HSTS 1 year + includeSubDomains + preload",
      "max-age=31536000" in hsts and "includeSubDomains" in hsts and "preload" in hsts, hsts)  # fmt: skip
check("X-Frame-Options DENY", r.headers.get("X-Frame-Options") == "DENY")
check("nosniff", r.headers.get("X-Content-Type-Options") == "nosniff")
check("CSP present with default-src 'none'",
      "default-src 'none'" in r.headers.get("Content-Security-Policy", ""),
      r.headers.get("Content-Security-Policy", ""))  # fmt: skip
check("Permissions-Policy present", bool(r.headers.get("Permissions-Policy")))
check("no version in Server header", not re.search(r"\d", r.headers.get("Server", "")),
      str(r.headers.get("Server")))  # fmt: skip

print("\n== DEBUG off, admin path, robots ==")
for path in ["/this-does-not-exist/", "/api/nope/", "/admin/", "/admin/login/", "/robots.txt"]:
    r = Jar().req("GET", path)
    check(f"GET {path} -> 404", r.status_code == 404, str(r.status_code))
    no_leak(f"GET {path}", r)
r = Jar().req("GET", f"/{ADMIN_URL}/login/")
check("admin login lives only at the secret ADMIN_URL (200)", r.status_code == 200, str(r.status_code))
r = requests.get(PROD + "/api/public/projects/", headers={**BASE, "Host": "evil.example"},
                 timeout=20)  # fmt: skip
check("unknown Host header -> 400 (ALLOWED_HOSTS)", r.status_code == 400, str(r.status_code))
no_leak("bad Host", r)

print("\n== error handling (malformed input) ==")
j = Jar()
token = j.csrf()
h = {"X-CSRFToken": token, "Content-Type": "application/json"}
for label, body in [("malformed JSON", b'{"email": '), ("JSON array", b"[1,2,3]"),
                    ("deep JSON", b"[" * 100000 + b"]" * 100000),
                    ("invalid UTF-8", b'{"email": "\xff\xfe"}'),
                    ("3 MB body", b'{"email": "' + b"a" * 3_000_000 + b'"}')]:  # fmt: skip
    r = j.req("POST", "/api/auth/login/", data=body, headers=h)
    check(f"login with {label} -> 4xx, never 500", 400 <= r.status_code < 500, str(r.status_code))
    no_leak(f"login with {label}", r)
j = Jar()  # fresh visitor: the five bodies above used up this IP's 5/min login budget
token = j.csrf()
r = j.req("POST", "/api/auth/login/", data=b"email=a", headers={"X-CSRFToken": token,
          "Content-Type": "application/x-www-form-urlencoded"})  # fmt: skip
check("form-encoded body to JSON API -> 415", r.status_code == 415, str(r.status_code))

print("\n== forced 500 (database unreachable) ==")
for path in ["/api/public/projects/", "/api/auth/me/"]:
    down = Jar()
    down.cookies["sessionid"] = "anysessionkeyforcesadatabaselookup"  # session load hits the DB
    r = down.req("GET", path, base=NODB)
    check(f"NODB GET {path} -> 500", r.status_code == 500, str(r.status_code))
    no_leak(f"NODB GET {path}", r)
    print(f"    body: {r.text[:120]!r}  content-type: {r.headers.get('Content-Type')}")
r = Jar().req("GET", "/healthz/", base=NODB)
print(f"NODB GET /healthz/ -> {r.status_code} {r.text[:80]!r}")
no_leak("NODB /healthz/", r)

print("\n== session cookies, rotation, logout ==")
alice = creds()["alice"]
j = Jar()
j.cookies["sessionid"] = "attackerfixatedsessionid0000000000"  # session fixation attempt
token = j.csrf()
csrf_raw = next((c for c in j.raw if c.startswith("csrftoken=")), "")
print("    Set-Cookie csrftoken:", re.sub(r"csrftoken=[^;]+", "csrftoken=<redacted>", csrf_raw))
r = j.req("POST", "/api/auth/login/", json={"email": alice["email"], "password": alice["password"]},
          headers={"X-CSRFToken": token})  # fmt: skip
check("login 200", r.status_code == 200, str(r.status_code))
sess_raw = next((c for c in r.set_cookies if c.startswith("sessionid=")), "")
print("    Set-Cookie sessionid:", re.sub(r"sessionid=[^;]+", "sessionid=<redacted>", sess_raw))
low = sess_raw.lower()
check("session cookie Secure", "; secure" in low)
check("session cookie HttpOnly", "; httponly" in low)
check("session cookie SameSite=Lax", "samesite=lax" in low)
check("csrf cookie Secure + SameSite=Lax",
      "; secure" in csrf_raw.lower() and "samesite=lax" in csrf_raw.lower())  # fmt: skip
first = j.cookies.get("sessionid", "")
check("session id rotated at login (fixated id not adopted)",
      bool(first) and first != "attackerfixatedsessionid0000000000")  # fmt: skip
check("authenticated: /api/auth/me/ 200", j.req("GET", "/api/auth/me/").status_code == 200)
new_token = j.csrf()
check("CSRF token rotated at login", new_token != token)

# A second login (another device) issues a different session.
other = Jar()
t2 = other.csrf()
other.req("POST", "/api/auth/login/", json={"email": alice["email"], "password": alice["password"]},
          headers={"X-CSRFToken": t2})  # fmt: skip
check("second device gets a different session id",
      other.cookies.get("sessionid") not in (None, first))  # fmt: skip

# Logout invalidates server-side: replaying the old cookie must fail.
stolen = first
r = j.req("POST", "/api/auth/logout/", headers={"X-CSRFToken": new_token})
check("logout 2xx", r.status_code in (200, 204), str(r.status_code))
replay = Jar()
replay.cookies["sessionid"] = stolen
r = replay.req("GET", "/api/auth/me/")
check("replaying the logged-out session cookie is rejected", r.status_code in (401, 403),
      str(r.status_code))  # fmt: skip

# Logout-all from a third session kills the second device's session.
third = Jar()
t3 = third.csrf()
third.req("POST", "/api/auth/login/", json={"email": alice["email"], "password": alice["password"]},
          headers={"X-CSRFToken": t3})  # fmt: skip
check("second device still logged in before logout-all",
      other.req("GET", "/api/auth/me/").status_code == 200)  # fmt: skip
r = third.req("POST", "/api/auth/logout-all/", headers={"X-CSRFToken": third.csrf()})
check("logout-all 2xx", r.status_code in (200, 204), str(r.status_code))
r = other.req("GET", "/api/auth/me/")
check("after logout-all the other device is logged out", r.status_code in (401, 403),
      str(r.status_code))  # fmt: skip
print("    me after logout-all:", json.dumps(r.json()) if r.content else "")
done()
