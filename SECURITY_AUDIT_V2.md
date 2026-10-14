# AdyraForge v2 — Security Audit (Phase 7)

**Date:** 2026-10-13, full re-run 2026-10-14
**Branch / code audited:** `v2/foundation` at `7e7a15c`. Every check below was re-run on that commit, and the raw output files were overwritten with that run. The final proof run is in `security/audit-v2/99-final-*.txt`.
**Method:** hostile, black-box and white-box, against the running stack.

- The dev stack in Docker.
- The backend booted with **production settings**: `DJANGO_ENV=production`, gunicorn, DEBUG off, real env validation.
- A **production frontend build** (`next build && next start`).

Every check names the script or command that ran it. The raw output is in [`security/audit-v2/`](security/audit-v2/) and the scripts are in [`security/scripts/`](security/scripts/). The live attack scripts use throwaway accounts (`audit.*@example.test`) with random passwords that exist only inside the dev container.

## Summary

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| H-1 | **High** | Every rate limit (login, contact, planner, password reset) could be bypassed by rotating `X-Forwarded-For` | **Fixed**, proven live before/after |
| M-1 | Medium | Deep JSON, or a JSON array instead of an object, caused 500s (RecursionError / AttributeError) | **Fixed** |
| M-2 | Medium | Public images stored byte-for-byte: PNG+PHP/JS polyglot served as-is; EXIF/GPS kept | **Fixed** |
| M-3 | Medium | Under production settings `/healthz/` returned 400 (DisallowedHost), so a correct deploy would never report healthy | **Fixed** |
| M-4 | Medium | Live `adyraforge.netlify.app` served repo files from `main` (`CLAUDE.md`, `backend/config/settings/base.py`, `docker-compose.yml`, `SECURITY_AUDIT_V1.md`). No secrets in them | **Fixed on production** by stopgap PR #3 (`e07a002`): Netlify publishes only `legacy/`. Every repo path now returns 404 |
| M-5 | Medium | Production stored public and private media on the container's local disk, which is ephemeral on Render | **Fixed** (`afe0d6c`): private S3-compatible bucket, files released only as 60-second presigned URLs after the ownership check; proven against a real S3 server |
| M-6 | Medium | No error monitoring (rule 14 names Sentry) | **Fixed in code** (Phase 8): Sentry on both apps, all data collection off + scrubbers. Activates once you set the DSNs |
| M-7 | Medium | Frontend CSP allows `'unsafe-inline'` scripts | **Accepted**, with reasons below |
| L-1 | Low | Signed download tokens appear in the gunicorn access log (URL path) | Accepted (5-min expiry, bound to the user) |
| L-2 | Low | Staff-only admin uploads are buffered to temp disk before the 25 MB check | Accepted (staff + OTP only) |
| L-3 | Low | `Server: gunicorn` header (no version) | Accepted |
| L-4 | Low | Turnstile verification raised a 500 on a non-object response instead of failing closed | **Fixed** |
| L-5 | Low | A production frontend build shipped an **empty site** when the API answered 404 for everything (wrong URL, service not deployed) or had no published projects | **Fixed** (`34ff275`): the build now fails in both cases, as it already did for an unreachable API |
| I-1 | Info | CSP `img-src` listed the API origin twice | **Fixed** |
| I-2 | Info | Session *deletion* cookie lacks `Secure` (Django `delete_cookie` default; the cookie is empty) | No action |

There are **no Critical findings**, and the only High finding is fixed. No secrets were found anywhere, so **no keys need rotating**.

---

## Findings in detail

### H-1: Throttles keyed on a client-controlled header (High, fixed)

**Cause.** `REST_FRAMEWORK["NUM_PROXIES"]` was unset. In that mode DRF's `get_ident()` uses the **entire raw `X-Forwarded-For` header** as the client identity. Any client can set that header, and a new value per request gets a fresh throttle bucket.

**Impact.** Unlimited password-reset email bombing, contact and planner spam (only Turnstile remained in the way), and unthrottled login guessing. Axes still capped guesses per account, because it used `REMOTE_ADDR`.

**Proof (before).** [`11-xff-spoof-BEFORE-fix.txt`](security/audit-v2/11-xff-spoof-BEFORE-fix.txt): 0 of 4 limits held.

```
[FAIL] contact (5/hour): 6 requests with rotating X-Forwarded-For still hit 429  ->  codes=[201, 201, 201, 201, 201, 201]
[FAIL] password reset (3/hour): 4 requests with rotating X-Forwarded-For still hit 429  ->  codes=[202, 202, 202, 202]
```

**Fix** (`834f12d`). A new env var, `TRUSTED_PROXY_COUNT`, sets how many proxies to trust: 0 locally, 1 on Render. It drives:
- DRF `NUM_PROXIES`.
- A validated `apps.core.security.client_ip()`, used as `AXES_CLIENT_IP_CALLABLE` and for the stored IP hash.

All three now agree on one client IP. That IP is the N-th entry from the right of `X-Forwarded-For`, where the trusted proxy wrote it. Everything to its left is client-supplied and ignored.

Production **refuses to boot** unless `TRUSTED_PROXY_COUNT` is set explicitly (0–5). The setting matters in both directions:
- **Too low:** every visitor shares the proxy's IP, giving one global throttle and lockout DoS.
- **Too high:** IPs become spoofable.

**Proof (after).** [`11-xff-spoof-AFTER-fix.txt`](security/audit-v2/11-xff-spoof-AFTER-fix.txt): 4 of 4 limits hold (`[201]*5 + [429]` etc.).

New tests in `tests/test_client_ip.py` check:
- 0, 1 and 2 proxies.
- That DRF, axes and the hash agree.
- That a garbage header falls back to `REMOTE_ADDR`.
- That rotating the spoofed prefix still trips the contact throttle at both settings.

Added 2026-10-14 (`32d475a`, [`30-step1-client-ip-tests.txt`](security/audit-v2/30-step1-client-ip-tests.txt), 16/16 with the lockout tests):
- **(a)** behind one proxy, two real clients arriving from the same proxy address get **independent** throttle buckets and **independent** axes lockouts. An attacker locking out Alice from network A doesn't lock out Alice on network B.
- **(b)** rotating a forged leftmost `X-Forwarded-For` entry on every attempt **cannot escape** the lockout.
- The axes setting name was checked against the installed django-axes 8.3.1 source (`axes/helpers.py: get_client_ip_address` reads `AXES_CLIENT_IP_CALLABLE` first). django-ipware is not installed, so the `AXES_IPWARE_*` settings are inert.

`tests/test_settings_validation.py` checks that production refuses unset or invalid values.

### M-1: JSON bodies that crash the parser (Medium, fixed)

**Proof (before).**
- A 100 000-deep `[[[…]]]` sent to `/api/auth/login/` or `/api/leads/contact/` returned 500 with a `RecursionError`.
- `[1,2,3]` sent to the contact form returned 500 with an `AttributeError` (the honeypot check called `.get` on a list).

**Fix** (`9a75ccc`). `apps.core.parsers.SafeJSONParser` is now the only parser. It caps nesting at 20 levels and turns a `RecursionError` into a 400. The honeypot check and axes' username callable ignore bodies that aren't objects.

**Proof (after).** `tests/test_parser_hardening.py` covers 6 public endpoints at depths 21, 1 000 and 100 000. Under production settings, [`19-prod-probe.txt`](security/audit-v2/19-prod-probe.txt) shows: deep JSON, an array, invalid UTF-8, a 3 MB body and malformed JSON all return **400**; form-encoded data returns **415**. No 500s.

### M-2: Public image polyglots and EXIF (Medium, fixed)

**Proof (before).** [`04-uploads-BEFORE-fix.txt`](security/audit-v2/04-uploads-BEFORE-fix.txt): a real PNG with `<?php …?><script>…` appended after `IEND` was accepted and served back with the payload intact. EXIF metadata, including GPS, was also kept.

**Fix** (`ae8ef9e`).
- Public images (project covers, gallery, testimonial avatars, blog covers) are fully decoded, with a 40 MP decompression-bomb cap, and **re-encoded** without metadata. `exif_transpose` is applied and the ICC profile kept.
- Fake or truncated images are rejected.
- Private client documents are never altered: they stay byte-exact.

**Proof (after).** [`04-uploads-AFTER-fix.txt`](security/audit-v2/04-uploads-AFTER-fix.txt): 13/13 pass, and the stored polyglot is 69 bytes with `payload present=False`. `tests/test_image_sanitizing.py` (6 tests) covers the rest.

### M-3: Health check broken under production settings (Medium, fixed)

**Found** while booting the production container. `docker inspect` showed it stuck at `unhealthy`. The log showed `DisallowedHost: Invalid HTTP_HOST header: '127.0.0.1:8000'`, because `CommonMiddleware` validates the Host header on every request, including the probe.

**Fix** (`72089c1`). `HealthCheckMiddleware` answers `GET`/`HEAD /healthz/` before host validation. It touches no database and returns no data. The header-only middlewares (XFO, CSP, Permissions-Policy) now run before it, so the probe response keeps the full header set. Host validation still applies to every other path and method (tested).

**Proof.** Both production containers report `healthy`. `tests/test_security_headers.py` has two new tests.

### M-4: Live site serves repository files (Medium, fixed on production 2026-10-14)

`adyraforge.netlify.app` publishes the repo root of `main` (since the v1 → v2 merge). [`21-live-netlify-exposure.txt`](security/audit-v2/21-live-netlify-exposure.txt) shows **200** today for:
- `/CLAUDE.md`
- `/SECURITY_AUDIT_V1.md`
- `/backend/config/settings/base.py`
- `/docker-compose.yml`

No secret is exposed (gitleaks on full history is clean), but this hands an attacker the architecture and security design. **Merging `v2/foundation` into `main` before fixing this would also publish `security/` and this report.**

**Fix (stopgap, approved and merged):** PR #3 (`e07a002`) moves the v1 `index.html` to `legacy/`, which holds the whole v1 site since it has no local assets. A root `netlify.toml` publishes only that folder, with no build step and basic security headers. It was verified on the PR's deploy preview before merging, then on production ([`21-live-netlify-exposure.txt`](security/audit-v2/21-live-netlify-exposure.txt)):
- `/CLAUDE.md`, `/README.md`, `/SECURITY_AUDIT_V1.md`, `/backend/config/settings/base.py`, `/docker-compose.yml`, `/.github/...`, `/netlify.toml` and `/.env` all return **404**;
- `/` still serves the v1 homepage (same title, same 52 273 bytes as before).

The v2 PR replaces this with its own `netlify.toml` (base `frontend`) when it merges.

### M-5: Media on ephemeral disk in production (Medium, fixed)

**Cause.** `production.py` used `FileSystemStorage` for public media and private client files. Render wipes the container filesystem on every deploy, so client files and invoices would have been lost.

**Fix** (`afe0d6c`). Both now live in S3-compatible buckets (Cloudflare R2 recommended, or AWS S3), via django-storages.
- **Private bucket** (`STORAGES["private"]`): no public access. The signed download view keeps its per-user token and ownership check. Only after both pass does it answer `302` to a presigned URL valid for **60 s**, with `Content-Disposition: attachment` and `Referrer-Policy: no-referrer`.
- **Media bucket:** public images only.
- Production refuses to boot without both buckets and credentials, or with one bucket used for both.
- Cloudinary was not chosen: it blocks PDF/ZIP delivery by default, and invoices are PDFs.

**Proof.**
- All existing ownership, download and upload tests pass unchanged (223 in [`31-step2-storage-tests.txt`](security/audit-v2/31-step2-storage-tests.txt)).
- `tests/test_private_bucket.py` runs the real `S3Storage` against moto. It checks that uploads are UUID-named with no public grants, the owner gets a 60 s presigned attachment, Bob's link never yields a bucket URL for Alice, and anonymous users get 403 with no redirect.
- A **live run against a real S3 server** (SeaweedFS, SigV4 enforced) is in [`31-private-bucket-live.txt`](security/audit-v2/31-private-bucket-live.txt), **12/12**:
  - anonymous object GET and bucket listing → 403;
  - the presigned URL returns the exact bytes as an attachment;
  - a tampered signature, a stretched `X-Amz-Expires` and an expired URL → 403;
  - the full Django flow (owner link → 302 → file; another client → 404, no bucket URL).

### M-6: No error monitoring (Medium, fixed in code)

Errors were logged to stdout with full detail server-side ([`19-prod-probe.txt`](security/audit-v2/19-prod-probe.txt)), but nothing alerted anyone.

Phase 8 added Sentry to both apps. It's off until `SENTRY_DSN` (Render) and `NEXT_PUBLIC_SENTRY_DSN` (Netlify) are set.

The current SDKs (sentry-sdk 2.72, @sentry/nextjs 11) **collect user info, cookies, headers, bodies, query params and stack-frame variables by default**, and a partial `data_collection` setting keeps the rest of those defaults. So both apps pass a complete all-off `data_collection`, and a second-layer scrubber removes cookies, bodies, IPs, auth/CSRF headers, query strings and invite/reset/download tokens.

Tests:
- `tests/test_monitoring.py` includes an **unmocked** `sentry_sdk.init` that asserts the SDK's own resolved settings, and runs with deprecation warnings as errors.
- `frontend/src/lib/sentry-scrub.test.ts`.

The browser SDK loads lazily (initial JS unchanged at 104 kB shared) and sends through a same-origin tunnel that forwards only to our project. Sentry is kept out of the edge middleware bundle (34.6 kB).

### M-7: Frontend CSP allows `'unsafe-inline'` scripts (Medium, accepted)

Next.js App Router injects inline bootstrap scripts. A nonce-based CSP forces every page to render dynamically, which removes ISR and static rendering and breaks the LCP budget (2.1–2.3 s measured).

**Mitigations, verified:**
- React escapes all output.
- The only `dangerouslySetInnerHTML` is JSON-LD, which escapes `<` ([`05-xss-server.txt`](security/audit-v2/05-xss-server.txt): "JSON-LD has no raw '<'").
- Rich text is sanitised with nh3.
- `object-src 'none'`, `base-uri 'self'`, `form-action 'self'`, `frame-ancestors 'none'`.
- No third-party scripts except Cloudflare Turnstile.

**Revisit** if Next ships hash-based CSP for static pages.

### Low and info

- **L-1: tokens in the access log.** Signed download URLs carry the token in the path, so `--access-logfile -` records it. Tokens expire in 5 minutes and only work for the user they were issued to (the IDOR sweep shows Alice replaying Bob's link gets 404). Accepted.
- **L-2: upload buffering.** Django streams large uploads to a temp file before the model validator rejects anything over 25 MB. Only staff with OTP can upload. Accepted. Revisit if clients ever get uploads.
- **L-3: `Server: gunicorn`.** No version is shown. Render may override it. Accepted.
- **L-4: Turnstile non-object response.** A JSON array, string or null from `siteverify` raised a 500 instead of rejecting. Fixed in `ab15334`. A new parametrized test fails 3/5 on the old code and passes now.
- **I-1: duplicate CSP origin.** `img-src` listed the API origin twice when no separate media origin was set. Fixed in `4c7e263`.
- **I-2: deletion cookie.** When Django deletes an invalid session cookie, it sends `Max-Age=0` without `Secure`. The value is empty, so nothing leaks.

---

## OWASP Top 10 (2021): check by check

| # | Category | Concrete check | Result | Evidence |
|---|----------|----------------|--------|----------|
| A01 | Broken Access Control | **IDOR sweep**: Alice requested every one of Bob's objects (project, message, file, invoice, downloads, thread) with GET/PUT/PATCH/DELETE/POST, list filters with Bob's project id, and replayed Bob's signed links | 36/36 pass. Every foreign id → **404**; lists exclude Bob's rows; Bob's data unchanged | [`01-idor-sweep.txt`](security/audit-v2/01-idor-sweep.txt) |
| | | Unit tests: cross-client isolation, anonymous → 403 on every protected route and method, admin API needs staff+OTP | Pass | `test_portal_isolation.py`, `test_access_control.py` in the final pytest run |
| | | Admin path `/admin/` and `/admin/login/` under production settings | **404**; admin only at the secret `ADMIN_URL` | [`19-prod-probe.txt`](security/audit-v2/19-prod-probe.txt) |
| | | CSRF: no token, forged token, valid token + evil Origin, form POST | All rejected (403/415); control 201 | [`02-csrf.txt`](security/audit-v2/02-csrf.txt) |
| | | Private files in the bucket: anonymous access, link replay by another client, tampered/expired presigned URLs | All refused; only the owner, after the ownership check, gets a 60 s URL | [`31-private-bucket-live.txt`](security/audit-v2/31-private-bucket-live.txt) |
| A02 | Cryptographic Failures | Cookie flags under production settings | `sessionid` and `csrftoken`: `Secure; HttpOnly; SameSite=Lax` | [`19-prod-probe.txt`](security/audit-v2/19-prod-probe.txt) |
| | | HTTPS: plain-http request | 301 to `https://`; HSTS `max-age=31536000; includeSubDomains; preload` on API and frontend | [`19`](security/audit-v2/19-prod-probe.txt), [`18`](security/audit-v2/18-headers-frontend.txt) |
| | | Password hashing | Argon2 first, PBKDF2 fallback (`settings/base.py`); SMTP must be TLS or SSL (boot validation) | `test_accounts.py`, `test_settings_validation.py` |
| A03 | Injection | **XSS**: payloads (`<script>`, `<img onerror>`, `<svg onload>`, `</script>` breakout, `javascript:`, template injection) seeded into every rendered text field: project, service, technology, testimonial, lead, client message | Server HTML 22/22 escaped. **Real browser**: `window.__xss` stayed `null` on `/`, `/work`, `/work/xss-probe`, `/services` and the client portal thread | [`05-xss-server.txt`](security/audit-v2/05-xss-server.txt), [`06-xss-browser.txt`](security/audit-v2/06-xss-browser.txt) |
| | | SQL: ORM only; semgrep `p/django`, bandit, ruff `S` | 0 SQL findings; no raw SQL in code | [`10`](security/audit-v2/10-semgrep.txt), [`12`](security/audit-v2/12-bandit.txt), [`13`](security/audit-v2/13-ruff-security.txt) |
| A04 | Insecure Design | Rate-limit floods on login, contact, planner, password reset | 429 + `Retry-After` on every endpoint; axes locks after 5 failures | [`03-rate-limits.txt`](security/audit-v2/03-rate-limits.txt) |
| | | Rate-limit **bypass** via `X-Forwarded-For` | **Was vulnerable (H-1), fixed** | [`11-*`](security/audit-v2/) |
| | | Behind one proxy: two real clients throttled and locked out independently; forged leftmost entry can't escape | Pass | [`30-step1-client-ip-tests.txt`](security/audit-v2/30-step1-client-ip-tests.txt) |
| | | Honeypot + Turnstile fail closed | Covered by tests, incl. Cloudflare unreachable and non-object responses | `test_public_forms.py` |
| A05 | Security Misconfiguration | `manage.py check --deploy --fail-level WARNING` with production settings | **0 issues**; DEBUG=False; 29-char admin path | [`20-check-deploy.txt`](security/audit-v2/20-check-deploy.txt) |
| | | Headers, API (production settings) | HSTS, nosniff, XFO DENY, Referrer-Policy, COOP, Permissions-Policy, CSP `default-src 'none'`; no `X-Powered-By` | [`19-prod-probe.txt`](security/audit-v2/19-prod-probe.txt) |
| | | Headers, frontend (production build) | Same set + CSP limited to self, the API origin and Turnstile; no `X-Powered-By` | [`18-headers-frontend.txt`](security/audit-v2/18-headers-frontend.txt) |
| | | Forced 500s (database unreachable), 404s, bad Host header | Generic JSON (`{"detail": "Server error."}`, `Not found.`, `Bad request.`); a regex for traceback, paths, `psycopg`, `settings` finds **nothing** | [`19-prod-probe.txt`](security/audit-v2/19-prod-probe.txt) |
| | | robots.txt | Frontend robots does not mention the admin path; API has no robots (404) | [`18`](security/audit-v2/18-headers-frontend.txt), [`19`](security/audit-v2/19-prod-probe.txt) |
| | | Health check under production settings | **Was broken (M-3), fixed** | `72089c1` |
| A06 | Vulnerable Components | `pip-audit --strict` on `base.txt` and `dev.txt` | No known vulnerabilities | [`15-pip-audit.txt`](security/audit-v2/15-pip-audit.txt) |
| | | `npm audit` | 0 vulnerabilities | [`09-npm-audit.txt`](security/audit-v2/09-npm-audit.txt) |
| | | Unused dependencies: `deptry` (backend), `depcheck` (frontend) | All hits triaged as string-loaded or config-loaded; nothing to remove | [`14`](security/audit-v2/14-deptry.txt), [`07`](security/audit-v2/07-depcheck.txt) |
| A07 | Identification & Auth Failures | Session fixation: planted `sessionid` before login | Not adopted; new id issued; CSRF token rotated | [`19-prod-probe.txt`](security/audit-v2/19-prod-probe.txt) |
| | | Logout invalidation: replay the old cookie | 403 | same |
| | | Logout-all from another device | Other session → 403 | same |
| | | Brute force: axes 5 failures / 30 min per username+IP | Locked, even for the right password; no wildcard CORS on the lockout | [`03-rate-limits.txt`](security/audit-v2/03-rate-limits.txt) |
| | | Admin 2FA | Admin login needs a password + OTP device token (used by the upload attack) | [`04-uploads-AFTER-fix.txt`](security/audit-v2/04-uploads-AFTER-fix.txt) |
| A08 | Software & Data Integrity | Uploads: `.php`, `.pdf.php`, PHP named `.pdf`, SVG with script, HTML as `.png`, GIF/PHP polyglot, null byte in name, 26 MB, path traversal | All rejected; traversal name stored as a UUID | [`04-uploads-AFTER-fix.txt`](security/audit-v2/04-uploads-AFTER-fix.txt) |
| | | Public image polyglot / EXIF | **Was vulnerable (M-2), fixed** | [`04-*`](security/audit-v2/) |
| | | Dependencies pinned with hashes (`--require-hashes`), `package-lock.json` committed | Yes | `backend/Dockerfile`, `requirements/*.txt` |
| A09 | Logging & Monitoring | 500s logged server-side; access log free of passwords, cookies and session ids | Confirmed (0 matches) | [`19-prod-probe.txt`](security/audit-v2/19-prod-probe.txt) |
| | | Alerting | Sentry wired on both apps (M-6), errors only, all data collection off; activates once the DSNs are set | `test_monitoring.py`, `sentry-scrub.test.ts` |
| A10 | SSRF | Outbound HTTP calls in the backend | One: Turnstile `siteverify`, a constant https URL. No user-controlled URL is ever fetched (bandit B310 triaged) | [`12-bandit.txt`](security/audit-v2/12-bandit.txt) |

## OWASP API Security Top 10 (2023): check by check

| # | Category | Check | Result |
|---|----------|-------|--------|
| API1 | Broken Object Level Authorization | IDOR sweep (above) + unit tests | 36/36; foreign objects → 404 for every method |
| API2 | Broken Authentication | Session flags, fixation, rotation, logout, logout-all, axes, throttles (incl. bypass) | All pass after the H-1 fix |
| API3 | Broken Object Property Level Authorization | [`22-mass-assignment.txt`](security/audit-v2/22-mass-assignment.txt): created a message with smuggled `client_project` (Bob's), `sender`, `id`, `created_at`, `read_at`; PATCHed `body`/`client_project` via the read-marker; PATCH/PUT `/api/auth/me/` with `role`, `is_staff`, `is_superuser`, `email` | 11/11: extra fields ignored, message stays in Alice's project, nothing reaches Bob, `/me` is read-only (405). Serializers expose explicit field lists only |
| API4 | Unrestricted Resource Consumption | Throttles + 429; JSON depth cap; `DATA_UPLOAD_MAX_MEMORY_SIZE` (3 MB → 400); 25 MB file cap; 40 MP image cap; page size 50 | Pass |
| API5 | Broken Function Level Authorization | Client → `/api/admin/leads/` | 403; admin API needs staff + OTP (`test_access_control.py`) |
| API6 | Unrestricted Access to Sensitive Business Flows | Contact/planner: honeypot + Turnstile (server-verified, fails closed) + 5/h and 10/h per real IP | Pass |
| API7 | SSRF | No user-supplied URL is fetched | Pass |
| API8 | Security Misconfiguration | check --deploy, headers, CORS allowlist (evil Origin gets no ACAO), errors, DEBUG | Pass |
| API9 | Improper Inventory Management | JSON renderer only (no browsable API, no public schema); unknown `/api/*` → 404; one versionless API surface | Pass |
| API10 | Unsafe Consumption of APIs | Turnstile response handling | **Was a 500 on unexpected shapes (L-4), fixed** |

## Static analysis and supply chain

| Tool | Command | Result | Raw |
|------|---------|--------|-----|
| bandit 1.9.4 | `bandit -r backend ml -x backend/tests` | 0 High; 1 Medium + 2 Low, all triaged false positives | [`12`](security/audit-v2/12-bandit.txt) |
| ruff (S rules) | `ruff check --select S . ../ml` | All checks passed | [`13`](security/audit-v2/13-ruff-security.txt) |
| semgrep 1.95.0 | `--config p/django --config p/nextjs --config p/secrets` at `7e7a15c` | 71 rules, 244 files, **0 findings** | [`10`](security/audit-v2/10-semgrep.txt) |
| gitleaks 8.30.1 | full history (68 commits) | No leaks | [`08`](security/audit-v2/08-gitleaks.txt) |
| deptry 0.25.1 | on `requirements/*.in` | 8 hits, all string-loaded (settings incl. `STORAGES`, CLI) | [`14`](security/audit-v2/14-deptry.txt) |
| depcheck 1.4.7 | `frontend/` | 4 hits, all config-loaded (incl. the Netlify runtime plugin) | [`07`](security/audit-v2/07-depcheck.txt) |
| Bundle grep | every file a browser can receive from the production build | 0 hits for a server-only canary secret, the internal API URL, the admin path, secret names, key patterns, `sourceMappingURL`. Positive control finds the public API URL in 12 files | [`17`](security/audit-v2/17-bundle-grep.txt) |

## What I could not verify (honestly)

1. **Cloudflare R2 itself, and Render's blueprint parser.** The bucket behaviour was proven on a real S3-compatible server (SeaweedFS), with the production `S3Storage` options, not on R2 or AWS. MinIO, the usual choice, no longer publishes free images: both registries refused the pull. DEPLOY.md §1b has the one-line anonymous-access check to run on the real bucket. Also, `render.yaml` parses as valid YAML with the intended services, cron and env group, but Render's own validation (including `sync: false` inside `envVarGroups`) only happens in the Blueprint preview.
2. **Neon role behaviour, and Sentry delivery.** The least-privilege role scheme was rehearsed on Postgres 16 ([`23`](security/audit-v2/23-least-privilege-db.txt), and end to end on the prod image in [`24`](security/audit-v2/24-prod-image-rehearsal.txt)), not on Neon itself. It assumes that roles created with SQL do not join `neon_superuser`; the verification `SELECT` in `deploy/neon_app_role.sql` checks this on the real database. Event delivery to Sentry is untested until DSNs exist (DEPLOY.md §5 has the test).
3. **The real Render proxy.** `TRUSTED_PROXY_COUNT=1` assumes Render's load balancer appends exactly one `X-Forwarded-For` entry and strips nothing else. That's tested with simulated headers, not against Render. **After the first deploy:** send two requests with a forged `X-Forwarded-For` from one machine. The contact throttle must count them together, and `Lead.ip_hash` must match for both.
4. **The securityheaders.com / SSL Labs grade.** v2 isn't public yet, so I captured the same headers locally with curl. Re-run both scanners against `adyraforge.com` and `api.adyraforge.com` after deploy, including the TLS config and the HSTS preload submission.
5. **Netlify-served headers and files.** The frontend headers come from `next.config.ts`. On Netlify, the Next.js runtime should apply them, but I haven't checked that on a deployed site. Also unchecked: that build internals under `.next/` are not publicly reachable (`prerender-manifest.json` and `middleware-manifest.json` hold Next's preview-mode signing keys). DEPLOY.md §4 has the curl checks for both.
6. **Real Turnstile and SMTP.** Both are mocked or use test keys locally. The first real contact submission and invite email after deploy is the test.
7. **Cookie scope across `adyraforge.com` ↔ `api.adyraforge.com`.** This depends on `SESSION_COOKIE_DOMAIN` and real DNS. Verify the portal login on the deployed domains.
8. **Admin pages in a real browser.** The XSS check of Django admin pages was server-side HTML only. Admin output is autoescaped by Django templates.
9. **Load and DoS** beyond per-IP throttles were not tested. The dependency scans are point-in-time.

## Phase 8 hardening (added with the deploy work)

- **Database:**
  - Production refuses a `DATABASE_URL` without `sslmode=require|verify-ca|verify-full` (`tests/test_settings_validation.py`).
  - The running app uses a least-privilege role that cannot run DDL. Migrations run in the release command with a separate owner URL ([`23-least-privilege-db.txt`](security/audit-v2/23-least-privilege-db.txt)).
- **Frontend:** the `netlify.toml` headers + CSP are identical to `next.config.ts`, enforced by a test that fails on any drift (mutation-checked). Netlify publishes only `frontend/`.
- **Health:** `/api/health` added for UptimeRobot, and now the Render health check, served by the same pre-host-validation middleware as `/healthz/`.
- **Storage:** private bucket with presigned URLs (M-5, above).
- **Sessions:** a daily `clearsessions` cron in `render.yaml` (rehearsed on the prod image as the app role in [`24`](security/audit-v2/24-prod-image-rehearsal.txt)).
- **Honest content:** MediCare Plus and mėntality are concepts and never featured as client work; the home page's selected work shows only client projects (verified in the browser). Migration `0005` corrects existing databases once ([`32-step3-seed-honesty.txt`](security/audit-v2/32-step3-seed-honesty.txt)).
- **Legacy:** the v1 site moved to `legacy/`; `netlify.toml` declares the pinned Next.js runtime and publishes only `frontend/`.
- **Dependencies:** Dependabot runs weekly for pip, npm and GitHub Actions.
- **Real production image, end to end** ([`24-prod-image-rehearsal.txt`](security/audit-v2/24-prod-image-rehearsal.txt)). The `prod` Dockerfile stage now builds; earlier, PyPI timeouts had blocked it.
  - Against a TLS Postgres 16, the Render release command migrated as the owner.
  - The image then ran as the non-root `app` user with read-only code, connected as `adyraforge_app` over **TLSv1.3**, and reported healthy via the Docker health check.
  - `prod_probe.py` passed **50/50** against it ([`19-prod-probe.txt`](security/audit-v2/19-prod-probe.txt)). Re-run on 2026-10-14 at `7e7a15c`: again 50/50, with the private storage resolving to `S3Storage` (presigned, 60 s).
- **Production checks:** [`security/scripts/prod_smoke.sh`](security/scripts/prod_smoke.sh) covers headers, exposure, errors, CORS, cookies, the proxy rate limit and the tunnel; run it against the deployed domains.

## Reproducing

```bash
docker compose cp security/scripts/. backend:/tmp/audit/
docker compose exec -w /tmp/audit backend python audit_fixtures.py   # throwaway accounts
docker compose exec -w /tmp/audit backend python idor_sweep.py       # likewise csrf_check, ratelimit_flood,
                                                                     # xff_spoof, upload_attack, mass_assign
docker compose exec -w /tmp/audit backend python xss_seed.py --cleanup  # after the XSS run
```

`prod_probe.py` needs two containers started with production env (see its docstring). `bundle_grep.sh` runs from `frontend/` after a production build.
