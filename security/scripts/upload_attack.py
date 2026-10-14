"""Hostile uploads through the real Django admin (password + OTP), private and public fields.

Private: ProjectFile.file (client documents). Public: Testimonial.avatar (image).
Rejected = the admin form re-renders with an error (200) and nothing is stored.
"""

import io
import json
import re
import struct
import zlib

import requests
from audit_common import API, CREDS_PATH, check, creds, done

ADMIN = API + "/admin/"  # dev ADMIN_URL
c = creds()


def png_bytes(payload: bytes = b"") -> bytes:
    """A real 1x1 PNG, optionally with data appended after IEND (classic polyglot)."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    raw = zlib.compress(b"\x00\xd4\xaf\x37")
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    img = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", raw) + chunk(b"IEND", b"")
    return img + payload


PHP = b"<?php system($_GET['c']); ?>"
JS = b"<script>alert(document.domain)</script>"
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def admin_session() -> requests.Session:
    s = requests.Session()
    page = s.get(ADMIN + "login/", timeout=10).text
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page).group(1)
    staff = c["staff"]
    otp = staff["otp_tokens"].pop()  # static backup codes are single-use: persist the pop
    with open(CREDS_PATH, "w", encoding="utf-8") as fh:
        json.dump(c, fh)
    r = s.post(ADMIN + "login/", data={
        "csrfmiddlewaretoken": token, "username": staff["email"], "password": staff["password"],
        "otp_device": staff["device"], "otp_token": otp, "next": "/admin/",
    }, timeout=15, allow_redirects=False)  # fmt: skip
    if r.status_code != 302:
        raise SystemExit(f"admin login failed: {r.status_code}")
    return s


def submit(s: requests.Session, add_path: str, fields: dict, file_field: str, name: str,
           content: bytes, ctype: str) -> requests.Response:  # fmt: skip
    page = s.get(ADMIN + add_path, timeout=10).text
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page).group(1)
    return s.post(ADMIN + add_path, data={"csrfmiddlewaretoken": token, **fields},
                  files={file_field: (name, io.BytesIO(content), ctype)},
                  timeout=60, allow_redirects=False)  # fmt: skip


s = admin_session()
doc_fields = {"client_project": str(c["alice"]["project"]), "description": "upload audit"}

print("== private client documents (ProjectFile) ==")
attacks = [
    ("shell.php", PHP, "application/x-php", "PHP script"),
    ("shell.pdf.php", PDF + PHP, "application/pdf", "PDF magic but .php extension"),
    ("contract.php.pdf", PHP, "application/pdf", "PHP content named .pdf"),
    ("evil.svg", b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)">' + JS + b"</svg>",
     "image/svg+xml", "SVG with script"),  # fmt: skip
    ("innocent.png", b"<!doctype html><html>" + JS + b"</html>", "image/png", "HTML renamed .png"),
    ("gifar.gif", b"GIF89a" + PHP, "image/gif", "GIF/PHP polyglot (GIF not allowed)"),
    ("note.pdf\x00.php", PHP, "application/pdf", "null byte in filename"),
    ("huge.pdf", PDF + b"0" * (26 * 1024 * 1024), "application/pdf", "26 MB (> 25 MB cap)"),
]
for name, content, ctype, label in attacks:
    r = submit(s, "clients/projectfile/add/", doc_fields, "file", name, content, ctype)
    rejected = r.status_code == 200 and "errorlist" in r.text
    reason = re.search(r'<ul class="errorlist[^>]*"><li>([^<]+)', r.text)
    check(f"rejected: {label} ({name!r})", rejected,
          f"{r.status_code} {reason.group(1) if reason else ''}")  # fmt: skip

r = submit(s, "clients/projectfile/add/", doc_fields, "file", "../../../etc/passwd.pdf", PDF,
           "application/pdf")  # fmt: skip
check("control: real PDF with traversal filename is accepted (302)", r.status_code == 302,
      str(r.status_code))  # fmt: skip

print("\n== public image (Testimonial.avatar) ==")
fields = {"author_name": "Upload Audit", "quote": "audit", "order": "0"}
for name, content, label in [
    ("avatar.svg", b'<svg xmlns="http://www.w3.org/2000/svg">' + JS + b"</svg>", "SVG avatar"),
    ("avatar.png", b"<html>" + JS, "HTML as .png"),
]:
    r = submit(s, "portfolio/testimonial/add/", fields, "avatar", name, content, "image/png")
    check(f"rejected: {label}", r.status_code == 200 and "errorlist" in r.text, str(r.status_code))

r = submit(s, "portfolio/testimonial/add/", fields, "avatar", "poly.png",
           png_bytes(PHP + JS), "image/png")  # fmt: skip
print(f"real PNG + appended PHP/JS polyglot -> {r.status_code} (302 = stored)")
if r.status_code == 302:
    listing = s.get(ADMIN + "portfolio/testimonial/?q=Upload+Audit", timeout=10).text
    pk = re.search(r"portfolio/testimonial/(\d+)/change/", listing).group(1)
    change = s.get(ADMIN + f"portfolio/testimonial/{pk}/change/", timeout=10).text
    url = re.search(r'href="([^"]*testimonials/[^"]+)"', change).group(1)
    stored = requests.get(url if url.startswith("http") else API + url, timeout=10)
    print("stored at:", url)
    check("stored public image no longer contains the PHP/JS payload",
          PHP not in stored.content and JS not in stored.content,
          f"{len(stored.content)} bytes, payload present={PHP in stored.content}")  # fmt: skip
    check("stored file name is a UUID, not the uploaded name", "poly" not in url, url)
    s.post(ADMIN + f"portfolio/testimonial/{pk}/delete/",
           data={"csrfmiddlewaretoken": s.cookies.get("csrftoken"), "post": "yes"}, timeout=10)  # fmt: skip
done()
