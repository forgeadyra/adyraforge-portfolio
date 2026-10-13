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
| `DATABASE_URL` | `postgres://…` (Neon). Non-PostgreSQL is rejected in every environment. |
| `ADMIN_URL` | unguessable, 16+ chars, trailing slash |
| `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | `https://adyraforge.com` (https only, explicit) |
| `CACHE_URL` | optional; defaults to `dbcache://django_cache` |

Production refuses to boot (`ImproperlyConfigured`) if any of these is missing or insecure.

**Frontend.** `NEXT_PUBLIC_API_URL` must be `https://` for production builds; the build fails otherwise. Never put a secret in a `NEXT_PUBLIC_*` variable.

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

## How auth and CSRF work

- Django session cookie: HttpOnly, Secure, SameSite=Lax. No JWT, nothing in localStorage (ESLint blocks `localStorage`).
- The frontend gets a CSRF token from `GET /api/auth/csrf/` (JSON body), keeps it in memory, and sends it as `X-CSRFToken` on every unsafe request (`frontend/src/lib/api.ts`). The CSRF cookie itself is HttpOnly. After login or logout, call `api.resetCsrfToken()`, because Django rotates the token.
- The API client only accepts relative paths, so cookies are never sent to another origin.

## Deploying

> **Do not push this to `main` yet.** Netlify currently publishes the repo root (the v1 `index.html`). Pushing as-is would publish `backend/`, `CLAUDE.md`, `SECURITY_AUDIT_V1.md` and everything else at `adyraforge.netlify.app/...`. First change the Netlify site to base directory `frontend`, or move v1 elsewhere.

- Backend image: `docker build -f backend/Dockerfile --target prod .`. It runs `collectstatic` on start, then gunicorn on `$PORT`. Run `migrate` and `createcachetable` as the platform's release / pre-deploy command.
- `/healthz/` is exempt from the HTTPS redirect for platform health checks.

## Known follow-ups

- **Private file downloads.** `ProjectFile` and `Invoice.pdf` have no URL yet. The API phase adds an ownership-checked view issuing short-lived signed URLs. Production storage (private S3 bucket or Cloudinary authenticated assets) is still to be chosen.
- **Deleting a `ProjectFile` row leaves the stored file on disk.** Whether deletion should also erase the file, or keep it for records, is a data-retention decision for you.
- **Budget bands** in `leads.BudgetRange` are placeholders. Adjust them to your real pricing.

- **CSP on the frontend** allows `'unsafe-inline'` scripts, because Next's hydration scripts are inline. The strict alternative is a per-request nonce via middleware, which makes every page dynamic (no static/CDN caching). This is a performance-versus-security decision still to make.
- **Client IP behind a proxy.** django-axes uses `REMOTE_ADDR`, which on Render is the proxy. Before going live, configure trusted-proxy IP extraction, so lockouts are per client and not per proxy.
