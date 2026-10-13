# AdyraForge v2

Portfolio, lead engine and client portal for **AdyraForge**, a freelance web development brand under Adyra Group.
Project rules live in [CLAUDE.md](CLAUDE.md); read them before changing anything.

```
frontend/   Next.js 15 (App Router, TypeScript strict, Tailwind v4)        → Netlify
backend/    Django 5.2 + DRF, Python 3.12, PostgreSQL, session auth          → Render / Railway
ml/         recommender package (adyra_ml), imported by the backend
index.html  v1 static site (still what adyraforge.netlify.app serves; see "Deploying")
```

## Prerequisites

- Docker Desktop (Compose v2)
- Node 22 and Python 3.12, only needed to run tooling outside Docker
- Optional: `pip install pre-commit` for the git hooks

## First-time setup

```bash
cp .env.example .env
cp backend/.env.example backend/.env
```

Fill in both files. Nothing in them is ever committed (`.env*` is gitignored; only `*.env.example` is tracked).

- `.env` → `POSTGRES_PASSWORD`: `python -c "import secrets; print(secrets.token_hex(24))"`
- `backend/.env` → `SECRET_KEY`: `python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"`

## Run it

```bash
docker compose up -d --build --wait
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createcachetable
docker compose exec backend python manage.py seed_portfolio
```

`seed_portfolio` loads the real services and projects (L'Atelier de Gastronomie, MediCare Plus, mėntality, Nexus, Aether). It is idempotent and never overwrites admin edits; `--force` resets the seeded fields. It deliberately seeds **no** result metrics, client names or testimonials. Add those in the admin once confirmed. mėntality stays unpublished until it has case-study copy.

| Service  | URL                                      |
| -------- | ---------------------------------------- |
| Frontend | http://localhost:3000                    |
| API      | http://localhost:8000/healthz/           |
| Admin    | http://localhost:8000/`$ADMIN_URL`       |
| Postgres | 127.0.0.1:5432 (bound to localhost only) |

`createcachetable` is required: DRF throttle counters live in the database cache, so they are shared across workers.

### Admin account and 2FA

The admin always requires a TOTP code (django-otp), in development too. To bootstrap your first login:

```bash
docker compose exec backend python manage.py createsuperuser
docker compose exec backend python manage.py addstatictoken you@example.com
```

`addstatictoken` prints a single-use backup code. Log in with your email, password and that code. Then add a TOTP device under **OTP_TOTP → TOTP devices** and scan it with your authenticator app. Failed logins are locked out by django-axes after 5 attempts per email+IP for 1 hour. To unlock: `manage.py axes_reset`.

Clients are created by you in the admin (invite only, no public sign-up). A user created without a password cannot log in until one is set.

## Checks (same as CI)

Backend, inside the container (real PostgreSQL, never SQLite):

```bash
docker compose exec -e DJANGO_ENV=test backend pytest
docker compose exec backend ruff check --config pyproject.toml . ../ml
docker compose exec backend black --config pyproject.toml --check . ../ml
docker compose exec backend pip-audit --strict --cache-dir /tmp/pip-audit -r requirements/base.txt
```

Production settings check (pass real-looking values; nothing is read from `backend/.env` for these):

```bash
docker compose exec -e DJANGO_ENV=production -e SECRET_KEY="<50+ random chars>" -e ALLOWED_HOSTS=api.adyraforge.com -e ADMIN_URL=<unguessable-path>/ -e CORS_ALLOWED_ORIGINS=https://adyraforge.com -e CSRF_TRUSTED_ORIGINS=https://adyraforge.com backend python manage.py check --deploy --fail-level WARNING
```

Frontend:

```bash
cd frontend
npm ci
npm run lint
npm run typecheck
npm run format:check
npm test
NEXT_PUBLIC_API_URL=https://api.adyraforge.com npm run build
npm audit --audit-level=high
```

Git hooks (gitleaks, ruff, black, eslint, prettier): `pre-commit install`.

### Dependencies

- Python: edit `backend/requirements/*.in`, then recompile with hashes inside Python 3.12:
  `docker run --rm -v "$PWD/backend/requirements:/req" -w /req python:3.12-slim sh -c "pip install -q pip-tools && pip-compile --generate-hashes --strip-extras --allow-unsafe -o base.txt base.in && pip-compile --generate-hashes --strip-extras --allow-unsafe -o dev.txt dev.in"`
- Node: exact versions in `package.json`, and `package-lock.json` is committed. `overrides.postcss` forces the patched postcss inside Next 15. Remove it once Next ships a fixed version. `eslint-config-next` is deliberately not used: its `braces` dependency has an advisory with no patched release.

## Environment variables

**Backend.** All come from the process environment. `backend/.env` is loaded only by `manage.py`, for local convenience; the WSGI entry point used in production never reads files.

| Variable | Production requirement |
| --- | --- |
| `DJANGO_ENV` | `production`. Unset or unknown also means production (fail closed). |
| `SECRET_KEY` | 50+ chars, not a placeholder, not `django-insecure…` |
| `ALLOWED_HOSTS` | e.g. `api.adyraforge.com`, no wildcards |
| `DATABASE_URL` | `postgres://…?sslmode=require` (Neon), as the least-privilege `adyraforge_app` role (`deploy/neon_app_role.sql`). Non-PostgreSQL is rejected everywhere; production also rejects a URL without `sslmode=require`/`verify-*`. |
| `MIGRATION_DATABASE_URL` | Neon URL for the database owner. Used only by the release command (`migrate`, `createcachetable`); the running app never sees it. |
| `ADMIN_URL` | unguessable, 16+ chars, trailing slash |
| `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | `https://adyraforge.com` (https only, explicit) |
| `FRONTEND_URL` | `https://adyraforge.com` (used in emailed invite/reset links) |
| `EMAIL_HOST`, `EMAIL_PORT` (587), `EMAIL_USE_TLS` (True), `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | SMTP (Zoho). All required in production, with exactly one of TLS/SSL. Development always uses the console backend. |
| `DEFAULT_FROM_EMAIL`, `LEAD_NOTIFY_EMAIL` | sender address, and where lead notifications go |
| `TURNSTILE_SECRET_KEY` | real Cloudflare Turnstile secret (Cloudflare's test keys rejected) |
| `TRUSTED_PROXY_COUNT` | reverse proxies that append to `X-Forwarded-For`: `1` on Render, `0` with no proxy. Must be set explicitly. Too low = every visitor shares one throttle/lockout bucket; too high = spoofable client IPs. |
| `SESSION_COOKIE_DOMAIN` | `.adyraforge.com`, so Next middleware on adyraforge.com sees the session cookie |
| `CACHE_URL` | optional; defaults to `dbcache://django_cache` |
| `SENTRY_DSN` | optional. Error monitoring with all data collection off and an extra scrubber (`apps/core/monitoring.py`). |

Production refuses to boot (`ImproperlyConfigured`) if any of these is missing or insecure.

**Frontend.** `NEXT_PUBLIC_API_URL` must be `https://` for production builds; the build fails otherwise. Never put a secret in a `NEXT_PUBLIC_*` variable. `NEXT_PUBLIC_SENTRY_DSN` (optional) enables Sentry in the browser (lazy-loaded after first paint, tunnelled through `/monitoring`) and the Node server; a DSN is a public identifier, not a secret.

## Public site

Pages: Home, Work (`/work`, filter by industry and technology), case studies (`/work/[slug]`), Services, Project planner, About, Contact, and a 404. Content comes from the read-only `GET /api/public/*` endpoints with ISR (`revalidate` 1h). If a background revalidation fails, the last good page keeps being served.

- **No invented content.** Every project has `kind` = `client` or `concept`. Concept work always carries a visible **Concept** badge and is never presented as client work. The **Built to perform** strip shows real Lighthouse mobile scores from admin fields, only for projects with all four scores and a measurement date (hidden otherwise). `results_note` lets a case study state limitations honestly. Service prices appear only once entered in the admin. Testimonials stay hidden until real ones are published. Case-study sections without content aren't rendered.
- **3D hero** (React Three Fiber, faceted AF monogram, bloom, gold rim light) loads only on desktop-class devices (fine pointer, ≥1024px, not low-memory or Save-Data, WebGL2), after `load` plus idle. It pauses when off-screen or the tab is hidden. Phones, reduced-motion and no-WebGL get the SVG poster (`HeroPoster`, same silhouette).
- **Motion:** Lenis, GSAP ScrollTrigger reveals and the process timeline, and Framer Motion page transitions all load after `load` plus idle. Framer never loads on the first page view. Everything is off under `prefers-reduced-motion`.
- **SEO:** per-page metadata and canonicals, generated Open Graph images (site and each case study), JSON-LD (Organization, Person, CreativeWork with `<` escaped), `sitemap.xml`, and `robots.txt` (portal and token pages disallowed).

### Lighthouse (production build, Lighthouse 12.8.2)

Mobile (default: simulated slow 4G, 4× CPU), median of runs:

| Page | Perf | A11y | BP | SEO | LCP | CLS | TBT | JS before load |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Home | 98 | 100 | 100 | 100 | 2.3 s | 0.001 | 70 ms | 127 KB |
| Work | 97 | 100 | 100 | 100 | 2.3 s | 0 | 110 ms | 125 KB |
| Case study | 98 | 100 | 100 | 100 | 2.3 s | 0 | 60 ms | 124 KB |
| Services | 98 | 100 | 100 | 100 | 2.1 s | 0.001 | 70 ms | 117 KB |
| Contact | 98 | 100 | 100 | 100 | 2.3 s | 0 | 70 ms | 120 KB |
| Planner | 98 | 100 | 100 | 100 | 2.3 s | 0 | 70 ms | 134 KB |
| About | 99 | 100 | 100 | 100 | 2.1 s | 0.002 | 50 ms | 116 KB |

Desktop home, with the 3D scene loaded: Perf 94, LCP 0.5 s, CLS 0, TBT 200 ms. The 3D adds about 450 KB of JS after load, and one ~230 ms main-thread task when the scene initialises.

To reproduce: `npm run build` with `NEXT_PUBLIC_API_URL`, `API_INTERNAL_URL` and `NEXT_PUBLIC_SITE_URL` set, run `npx next start -p 3001` with the same variables, then `npx lighthouse@12.8.2 http://localhost:3001/`.

## Data model

| App | Models |
| --- | --- |
| `core` | `AuditLog` (append-only: logins, failed logins, logouts, every admin add/change/delete, with an IP hash), shared upload validators, private storage |
| `portfolio` | `Service`, `Technology`, `Project` (+ `ProjectImage` gallery), `Testimonial`, `BlogPost` |
| `leads` | `Lead` (pipeline new → contacted → proposal → won, or lost from any open stage; enforced on save), `PlannerSubmission` |
| `clients` | `ClientProfile`, `ClientProject`, `Milestone`, `ProjectFile`, `Message`, `Invoice` |
| `recommender` | no models yet; glue for `ml/adyra_ml` |

Rules the models enforce:

- **Ownership.** Every client model has `Model.objects.for_user(user)`. API views must start from it. Clients see only their own rows, never draft invoices; staff see all; anonymous and inactive users see nothing.
- **No cascading deletes into money.** `ClientProject` and `Invoice` are `PROTECT`ed. Deleting a user with projects or invoices is refused, not cascaded.
- **IPs.** Only an HMAC-SHA256 keyed with `SECRET_KEY` is stored (`apps.core.security.hash_ip`), never the raw address.
- **Uploads.** Content type is detected from magic bytes (never trusted from the client), the extension must match, size is capped (images 5 MB, PDFs 10 MB, client files 25 MB), and files are stored as `<uuid>.<ext>`. SVG and HTML are always rejected. Client files and invoices go to `PRIVATE_MEDIA_ROOT` (outside the web root), and their storage refuses to produce URLs.
- **Rich text** (blog bodies) is sanitised with nh3 on every save. Messages and case-study text are plain text.

## How auth works

**No public registration.** You create a client (Django admin → Client profiles → Add, or `POST /api/admin/clients/invite/`). The system emails a signed invite link that works once and expires after 72 hours. The client sets a password (Django validators, minimum 12 characters) and signs in.

| Endpoint | Who | Notes |
| --- | --- | --- |
| `GET /api/auth/csrf/` | anyone | CSRF token in the body; cookie is HttpOnly |
| `POST /api/auth/login/` | anyone | throttled 5/min; axes locks email+IP for 30 min after 5 failures (wrong OTP codes count); staff with a device must send `otp_token` |
| `POST /api/auth/logout/` | signed in | deletes the session server-side |
| `POST /api/auth/logout-all/` | signed in | bumps `session_version`, invalidating every session on every device |
| `GET /api/auth/me/` | signed in | own profile only |
| `POST /api/auth/password/change/` | signed in | keeps this session, signs out all others |
| `POST /api/auth/password/reset/` | anyone | always the same 202 response; email sent off-thread so timing doesn't leak account existence |
| `POST /api/auth/password/reset/confirm/` | token | 1 hour, single-use |
| `POST /api/auth/invite/accept/` | token | 72 hours, single-use |
| `/api/portal/{projects,messages,files,invoices}/` | clients | `owned_by(request.user)`; another client's id is **404** for every method |
| `GET /api/portal/{files,invoices}/{id}/download/` | clients | returns a 5-minute signed URL bound to the user |
| `/api/admin/{leads,clients}/` | OTP-verified staff | staff without OTP get 403 |
| `POST /api/leads/contact/`, `POST /api/leads/planner/` | anyone | throttled, honeypot, server-side Turnstile |

Sessions: login rotates the session key and CSRF token, and sessions last at most 2 weeks. The portal frontend (`/portal/*`) is guarded by Next middleware calling `/api/auth/me/`, but that's UX only. Every permission is enforced by the API.

### CSRF and cookies

- Django session cookie: HttpOnly, Secure, SameSite=Lax. No JWT, nothing in localStorage (ESLint blocks `localStorage`).
- The frontend gets a CSRF token from `GET /api/auth/csrf/` (JSON body), keeps it in memory, and sends it as `X-CSRFToken` on every unsafe request (`frontend/src/lib/api.ts`). The CSRF cookie itself is HttpOnly. After login or logout, call `api.resetCsrfToken()`, because Django rotates the token.
- The API client only accepts relative paths, so cookies are never sent to another origin.

## Deploying

> **Do not push this to `main` yet.** Netlify currently publishes the repo root (the v1 `index.html`). Pushing as-is would publish `backend/`, `CLAUDE.md`, `SECURITY_AUDIT_V1.md` and everything else at `adyraforge.netlify.app/...`. First change the Netlify site to base directory `frontend`, or move v1 elsewhere.

- Step-by-step runbook: [`DEPLOY.md`](DEPLOY.md). Render blueprint: [`render.yaml`](render.yaml). Netlify build for v2: [`netlify.toml`](netlify.toml) (base directory `frontend`).
- Backend image: `docker build -f backend/Dockerfile --target prod .`. It runs `collectstatic` on start, then gunicorn on `$PORT`. Run `migrate` and `createcachetable` as the platform's release / pre-deploy command.
- `/healthz/` is answered before Host validation and the HTTPS redirect, so platform probes by container IP work.

## Known follow-ups

- **Content to fill in (admin):** service "starting from" prices (INR and USD), Lighthouse scores per live project, case-study problem text, result metrics and results notes, screenshots and cover images, testimonials, and the mėntality copy (it stays unpublished until then).
- **L'Atelier de Gastronomie's live URL is gone.** `phenomenal-belekoy-881bf4.netlify.app` returned Netlify's 404 page on 2026-10-13, so the seed marks it `not_live` with no link. The v1 site still links to it.
- **3D init on desktop** is one ~230 ms task about a second after load. If real-user INP data shows clicks landing in it, load the scene on first pointer movement instead of on idle.
- **Admin dashboard frontend.** The OTP-gated `/api/admin/*` endpoints exist; the custom dashboard UI doesn't yet. The Django admin works today.
- **Revoked sessions linger as rows** until they expire (they can no longer authenticate). Schedule `manage.py clearsessions` daily in production.

- **Private file storage in production.** Downloads already go through ownership-checked, 5-minute signed links (`apps/clients/downloads.py`), served from local private storage. Before launch, choose a private S3 bucket or Cloudinary authenticated assets and swap that module for presigned URLs.
- **Deleting a `ProjectFile` row leaves the stored file on disk.** Whether deletion should also erase the file, or keep it for records, is a data-retention decision for you.
- **Budget bands** in `leads.BudgetRange` are placeholders. Adjust them to your real pricing.

- **CSP on the frontend** allows `'unsafe-inline'` scripts, because Next's hydration scripts are inline. The strict alternative is a per-request nonce via middleware, which makes every page dynamic (no static/CDN caching). This is a performance-versus-security decision still to make.
