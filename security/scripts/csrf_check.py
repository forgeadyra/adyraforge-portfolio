"""CSRF: authenticated state-changing requests without a valid token must fail."""

from audit_common import API, api_session, check, creds, done

c = creds()
s, token = api_session(c["alice"]["email"], c["alice"]["password"])
thread = f"{API}/api/portal/projects/{c['alice']['project']}/messages/"
cross_site = {"Origin": "https://evil.example", "Referer": "https://evil.example/attack"}

r = s.post(thread, json={"body": "csrf probe (no token)"}, timeout=10)
check("POST message without X-CSRFToken -> 403", r.status_code == 403, f"{r.status_code} {r.text[:80]}")

r = s.post(thread, json={"body": "csrf probe (bad token)"},
           headers={"X-CSRFToken": "x" * 64}, timeout=10)  # fmt: skip
check("POST message with forged token -> 403", r.status_code == 403, str(r.status_code))

r = s.post(thread, json={"body": "csrf probe"}, headers={"X-CSRFToken": token, **cross_site},
           timeout=10)  # fmt: skip
check("POST with valid token but evil Origin -> 403", r.status_code == 403, str(r.status_code))

r = s.post(f"{API}/api/auth/logout-all/", timeout=10)
check("POST logout-all without token -> 403", r.status_code == 403, str(r.status_code))

r = s.post(f"{API}/api/auth/password/change/", json={"current_password": "x", "new_password": "y"},
           timeout=10)  # fmt: skip
check("POST password change without token -> 403", r.status_code == 403, str(r.status_code))

r = s.post(thread, data="body=form-encoded+csrf", timeout=10,
           headers={"Content-Type": "application/x-www-form-urlencoded"})  # fmt: skip
check("HTML-form style POST (no JSON, no token) -> rejected", r.status_code in {403, 415},
      str(r.status_code))  # fmt: skip

r = s.post(thread, json={"body": "legitimate message (csrf audit)"},
           headers={"X-CSRFToken": token}, timeout=10)  # fmt: skip
check("control: same POST with valid token -> 201", r.status_code == 201, str(r.status_code))
done()
