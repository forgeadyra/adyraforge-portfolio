# AdyraForge v2 — Security Audit (Phase 7)

**Date:** 2026-10-13
**Branch / code audited:** `v2/foundation`. Fixes are committed (`9a75ccc` … `ab15334`). The final proof run is in `security/audit-v2/99-final-*.txt`.
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
| M-4 | Medium | Live `adyraforge.netlify.app` serves repo files from `main` (`CLAUDE.md`, `backend/config/settings/base.py`, `docker-compose.yml`, `SECURITY_AUDIT_V1.md`). No secrets in them | **Open: fix ready, needs your approval to push** |
| M-5 | Medium | Production stores public and private media on the container's local disk, which is ephemeral on Render | **Open: Phase 8 decision (Cloudinary or S3)** |
| M-6 | Medium | No error monitoring (rule 14 names Sentry) | **Fixed in code** (Phase 8): Sentry on both apps, all data collection off + scrubbers. Activates once you set the DSNs |
| M-7 | Medium | Frontend CSP allows `'unsafe-inline'` scripts | **Accepted**, with reasons below |
| L-1 | Low | Signed download tokens appear in the gunicorn access log (URL path) | Accepted (5-min expiry, bound to the user) |
| L-2 | Low | Staff-only admin uploads are buffered to temp disk before the 25 MB check | Accepted (staff + OTP only) |
| L-3 | Low | `Server: gunicorn` header (no version) | Accepted |
| L-4 | Low | Turnstile verification raised a 500 on a non-object response instead of failing closed | **Fixed** |
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

### M-4: Live site serves repository files (Medium, open, needs approval)

`adyraforge.netlify.app` publishes the repo root of `main` (since the v1 → v2 merge). [`21-live-netlify-exposure.txt`](security/audit-v2/21-live-netlify-exposure.txt) shows **200** today for:
- `/CLAUDE.md`
- `/SECURITY_AUDIT_V1.md`
- `/backend/config/settings/base.py`
- `/docker-compose.yml`

No secret is exposed (gitleaks on full history is clean), but this hands an attacker the architecture and security design. **Merging `v2/foundation` into `main` before fixing this would also publish `security/` and this report.**

The fix is ready on local branch `fix/netlify-publish-v1-only` (`8ba6908`): publish only `site-v1/` with safe headers. It needs a push to `main`, which is an outward action, so **I have not done it without your OK.** In Phase 8 the Netlify site switches to building `frontend/` (base directory `frontend`), which removes the problem for good.

### M-5: Media on ephemeral disk in production (Medium, open)

`config/settings/production.py` uses `FileSystemStorage` for `MEDIA_ROOT` and `PRIVATE_MEDIA_ROOT`. On Render, the container filesystem is wiped on every deploy, so client files and invoices would be lost. Rule 9 calls for Cloudinary or S3 with signed URLs for private files.

This is a Phase 8 blocker and needs your choice of provider. Credentials go in the Render dashboard; never paste them in chat.

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
| A02 | Cryptographic Failures | Cookie flags under production settings | `sessionid` and `csrftoken`: `Secure; HttpOnly; SameSite=Lax` | [`19-prod-probe.txt`](security/audit-v2/19-prod-probe.txt) |
| | | HTTPS: plain-http request | 301 to `https://`; HSTS `max-age=31536000; includeSubDomains; preload` on API and frontend | [`19`](security/audit-v2/19-prod-probe.txt), [`18`](security/audit-v2/18-headers-frontend.txt) |
| | | Password hashing | Argon2 first, PBKDF2 fallback (`settings/base.py`); SMTP must be TLS or SSL (boot validation) | `test_accounts.py`, `test_settings_validation.py` |
| A03 | Injection | **XSS**: payloads (`<script>`, `<img onerror>`, `<svg onload>`, `</script>` breakout, `javascript:`, template injection) seeded into every rendered text field: project, service, technology, testimonial, lead, client message | Server HTML 22/22 escaped. **Real browser**: `window.__xss` stayed `null` on `/`, `/work`, `/work/xss-probe`, `/services` and the client portal thread | [`05-xss-server.txt`](security/audit-v2/05-xss-server.txt), [`06-xss-browser.txt`](security/audit-v2/06-xss-browser.txt) |
| | | SQL: ORM only; semgrep `p/django`, bandit, ruff `S` | 0 SQL findings; no raw SQL in code | [`10`](security/audit-v2/10-semgrep.txt), [`12`](security/audit-v2/12-bandit.txt), [`13`](security/audit-v2/13-ruff-security.txt) |
| A04 | Insecure Design | Rate-limit floods on login, contact, planner, password reset | 429 + `Retry-After` on every endpoint; axes locks after 5 failures | [`03-rate-limits.txt`](security/audit-v2/03-rate-limits.txt) |
| | | Rate-limit **bypass** via `X-Forwarded-For` | **Was vulnerable (H-1), fixed** | [`11-*`](security/audit-v2/) |
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
| | | Alerting | **Missing (M-6)** | |
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
| semgrep 1.95.0 | `--config p/django --config p/nextjs --config p/secrets` at `834f12d` | 71 rules, 208 files, **0 findings** | [`10`](security/audit-v2/10-semgrep.txt) |
| gitleaks 8.30.1 | full history | No leaks | [`99-final-gitleaks.txt`](security/audit-v2/) |
| deptry 0.25.1 | on `requirements/*.in` | 7 hits, all string-loaded (settings, CLI) | [`14`](security/audit-v2/14-deptry.txt) |
| depcheck 1.4.7 | `frontend/` | 3 hits, all config-loaded | [`07`](security/audit-v2/07-depcheck.txt) |
| Bundle grep | every file a browser can receive from the production build | 0 hits for a server-only canary secret, the internal API URL, the admin path, secret names, key patterns, `sourceMappingURL`. Positive control finds the public API URL in 12 files | [`17`](security/audit-v2/17-bundle-grep.txt) |

## What I could not verify (honestly)

1. **Neon role behaviour, and Sentry delivery.** The least-privilege role scheme was rehearsed on local Postgres 16 ([`23-least-privilege-db.txt`](security/audit-v2/23-least-privilege-db.txt)), not on Neon. It assumes that roles created with SQL do not join `neon_superuser`; the verification `SELECT` in `deploy/neon_app_role.sql` checks this on the real database. Event delivery to Sentry is untested until DSNs exist (DEPLOY.md §5 has the test).
2. **The real Render proxy.** `TRUSTED_PROXY_COUNT=1` assumes Render's load balancer appends exactly one `X-Forwarded-For` entry and strips nothing else. That's tested with simulated headers, not against Render. **After the first deploy:** send two requests with a forged `X-Forwarded-For` from one machine. The contact throttle must count them together, and `Lead.ip_hash` must match for both.
3. **The production Docker image itself.** Building the `prod` target failed on this network: PyPI read timeouts at ~180 kB/s (`docker build --target prod`). The production-mode probes ran the **dev image** with production settings and the prod image's exact gunicorn command; the dev image has the same hash-pinned `base.txt` packages plus dev tools. The prod image's differences (root-owned read-only code, no dev tools) are not exercised. Render builds it on deploy; check that the build log is green.
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
- **Health:** `/api/health` added for UptimeRobot, served by the same pre-host-validation middleware as `/healthz/`.
- **Dependencies:** Dependabot runs weekly for pip, npm and GitHub Actions.
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
