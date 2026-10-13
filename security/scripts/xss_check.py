"""Server-side half of the XSS check: rendered HTML must never contain the payloads unescaped.

(The browser half, which loads each page and reads window.__xss, is run separately.)
"""

import re

import requests
from audit_common import API, FRONTEND, check, creds, done

RAW_MARKERS = [
    '<script>window.__xss="script"</script>',
    "<img src=x onerror=",
    "<svg onload=",
    "</script><script>window.__xss",
]


def scan(label: str, html: str) -> None:
    hits = [m for m in RAW_MARKERS if m in html]
    check(f"{label}: no unescaped payload", not hits, f"found {hits}" if hits else "")
    # JSON-LD must escape "<" so the payload can't close the <script> element.
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        check(f"{label}: JSON-LD has no raw '<'", "<" not in block, block[:80] if "<" in block else "")


for path in ["/", "/work", "/work/xss-probe", "/services"]:
    r = requests.get(FRONTEND + path, timeout=60)
    check(f"GET {path} renders", r.status_code == 200, str(r.status_code))
    scan(f"frontend {path}", r.text)
    if path == "/work/xss-probe":
        check("payload is present but escaped (&lt;script&gt;)", "&lt;script&gt;" in r.text)

# Django admin (staff + OTP) renders leads/testimonials with autoescaping.
c = creds()
s = requests.Session()
page = s.get(API + "/admin/login/", timeout=10).text
token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page).group(1)
staff = c["staff"]
r = s.post(API + "/admin/login/", data={
    "csrfmiddlewaretoken": token, "username": staff["email"], "password": staff["password"],
    "otp_device": staff["device"], "otp_token": staff["otp_tokens"][0], "next": "/admin/",
}, allow_redirects=False, timeout=15)  # fmt: skip
check("admin login (OTP) for admin render check", r.status_code == 302, str(r.status_code))
for path in ["leads/lead/?q=xss", "portfolio/testimonial/", "portfolio/project/?q=xss"]:
    html = s.get(f"{API}/admin/{path}", timeout=15).text
    scan(f"admin /{path}", html)
done()
