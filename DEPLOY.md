# Deploying AdyraForge v2

The API runs on Render (Docker, gunicorn, whitenoise) at `api.adyraforge.com`, the database on Neon, and the frontend on Netlify at `adyraforge.com`.

**You enter every secret yourself, in the Render / Netlify / Neon dashboards. Never in git, never in chat.** Everything below is a placeholder.

## 0. Before you start

| Blocker | Why | Status |
|---|---|---|
| **Media storage** (SECURITY_AUDIT_V2 M-5) | Production keeps uploads on the container disk, and Render wipes it on every deploy. Client files and invoices would be lost | **Needs your choice:** Cloudinary (authenticated assets) or S3 (private bucket + presigned URLs). Until then, upload no client files in production |
| **Live repo exposure** (M-4) | `adyraforge.netlify.app` serves `CLAUDE.md`, settings source, etc. from `main` today | This repo's `netlify.toml` (base `frontend`) fixes it at cutover. `fix/netlify-publish-v1-only` fixes it sooner. Both need a push to `main`, which needs your OK |

Order: **Neon → Render → DNS for `api.` → Netlify → DNS for apex → Sentry / UptimeRobot → smoke checks.** The frontend build fetches content from the live API, so the API must be up first.

## 1. Neon (PostgreSQL)

1. **Create the project** in AWS `ap-southeast-1` (Singapore), next to the Render region in `render.yaml`. Postgres 16. Database name: `neondb` (default) or your choice.
2. **SSL is mandatory.** Neon only accepts TLS. The app also refuses to boot in production unless `DATABASE_URL` has `sslmode=require` (or `verify-ca` / `verify-full`). Use the **direct** connection string, not the `-pooler` host: Django keeps connections open (`CONN_MAX_AGE=60`), which doesn't work with PgBouncer transaction pooling.
3. **Two roles.**
   - The **owner** role (Neon's default, e.g. `neondb_owner`) runs migrations only. Its URL becomes `MIGRATION_DATABASE_URL`, read only by the release command.
   - The **app** role `adyraforge_app` is created by [`deploy/neon_app_role.sql`](deploy/neon_app_role.sql). It can read and write rows, and cannot create, alter, drop or truncate tables or create roles. Its URL becomes `DATABASE_URL`.

   Open the Neon **SQL Editor** (connected as the owner), paste the file, replace `REPLACE-IN-EDITOR-ONLY` with a strong password, and run it. Create this role with SQL, not in the console: console-created roles join `neon_superuser`. The final `SELECT` must show only `f`.

   This exact scheme was rehearsed on Postgres 16 ([`security/audit-v2/23-least-privilege-db.txt`](security/audit-v2/23-least-privilege-db.txt)): owner migrations succeed; the app role does CRUD, cache and sessions; and `CREATE TABLE`, `DROP`, `ALTER`, `TRUNCATE` and `CREATE ROLE` are all refused.
4. **Backups.** Neon keeps point-in-time history automatically. In **Settings → Storage → History retention**, set the longest your plan allows (7 days on Launch). For anything older, see "Off-site dump" in §9.

## 2. Render (API)

1. **New → Blueprint** → this repo → it reads [`render.yaml`](render.yaml). This creates the `adyraforge-api` Docker service on the paid Starter plan, which is needed for the release command.
   - Build: `backend/Dockerfile`, last stage `prod`. Hash-pinned dependencies, read-only code, non-root user.
   - Start: `collectstatic` (whitenoise serves static files), then `gunicorn config.wsgi --workers $WEB_CONCURRENCY`.
   - **Release command** (`preDeployCommand`): `migrate` then `createcachetable`, as the owner. A failed migration aborts the deploy, and the old version keeps serving.
   - **Health check:** `/healthz/` (answered before Host validation, no DB).
   - `autoDeploy: false`: you deploy deliberately.
2. **Environment variables.** Already set by `render.yaml` (no action):

   | Variable | Value |
   |---|---|
   | `DJANGO_ENV` | `production` |
   | `TRUSTED_PROXY_COUNT` | `1` (Render's proxy; see SECURITY_AUDIT_V2 H-1) |
   | `ALLOWED_HOSTS` | `api.adyraforge.com` |
   | `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `FRONTEND_URL` | `https://adyraforge.com` |
   | `SESSION_COOKIE_DOMAIN` | `.adyraforge.com` |
   | `EMAIL_PORT` / `EMAIL_USE_TLS` | `587` / `True` |
   | `WEB_CONCURRENCY` | `2` |

   **You enter these** in the dashboard:

   | Variable | What to put | How to get it |
   |---|---|---|
   | `SECRET_KEY` | 86 random chars | `python -c "import secrets; print(secrets.token_urlsafe(64))"`. Render's "Generate" value is too short for the boot check |
   | `ADMIN_URL` | e.g. `ops-<random>/` | `python -c "import secrets; print('ops-' + secrets.token_urlsafe(18) + '/')"`. Keep it in your password manager |
   | `DATABASE_URL` | `postgresql://adyraforge_app:<pw>@<ep-…>.ap-southeast-1.aws.neon.tech/neondb?sslmode=require` | Neon → Connection details, role `adyraforge_app`, **direct** host |
   | `MIGRATION_DATABASE_URL` | same, with the owner role | Neon → Connection details, owner role |
   | `TURNSTILE_SECRET_KEY` | Turnstile secret key | Cloudflare → Turnstile → your widget (hostnames: `adyraforge.com`) |
   | `EMAIL_HOST` | `smtp.zoho.in` or `smtp.zoho.com` (your Zoho region) | Zoho Mail → SMTP settings |
   | `EMAIL_HOST_USER` | the mailbox address | |
   | `EMAIL_HOST_PASSWORD` | a Zoho **app-specific** password | Zoho → Security → App passwords |
   | `DEFAULT_FROM_EMAIL` | `AdyraForge <hello@adyraforge.com>` | |
   | `LEAD_NOTIFY_EMAIL` | where new-lead alerts go | |
   | `SENTRY_DSN` | the Django project's DSN | §5 (optional, recommended) |

   A missing or weak required value stops the boot with `ImproperlyConfigured`. The log names the variable, never its value.
3. **Deploy.** The build log must show `pip install --require-hashes` succeeding; the release log shows the migrations.
4. **Render Shell:**
   ```bash
   python manage.py check --deploy --fail-level WARNING
   ```
   ```bash
   python manage.py createsuperuser
   ```
   Then add your TOTP device (README → "Admin account and 2FA"). The admin is only at `https://api.adyraforge.com/<ADMIN_URL>`.
5. **Settings → Custom Domains:** add `api.adyraforge.com`, create the DNS record from §4, and wait for the certificate.
6. Optional: a Render Cron Job running `python manage.py clearsessions` daily.

## 3. Netlify (frontend)

1. Point the site at this repo. [`netlify.toml`](netlify.toml) sets base directory `frontend`, `npm run build`, publish `.next` and Node 22, so **only `frontend/` is ever served**. It also sets:
   - the security headers + CSP for every path, kept identical to `next.config.ts` by `frontend/src/lib/netlify-headers.test.ts`;
   - the `www` → apex redirect.
2. **Environment variables** (Site configuration → Environment). All public, none secret:

   | Variable | Value |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | `https://api.adyraforge.com` (already in `netlify.toml`) |
   | `NEXT_PUBLIC_SITE_URL` | `https://adyraforge.com` (already in `netlify.toml`) |
   | `NEXT_PUBLIC_TURNSTILE_SITE_KEY` | Turnstile **site** key |
   | `NEXT_PUBLIC_SENTRY_DSN` | the Next.js project's DSN (§5). A DSN identifies a project; it is not a secret |

3. Deploy, then **Domain management:** add `adyraforge.com` (primary) and `www.adyraforge.com`. Use **HTTPS → Verify DNS / Provision certificate**. Netlify forces HTTPS once the certificate exists.
4. Media origin: when §0's storage decision is made, add that CDN origin to `img-src` in both `next.config.ts` and `netlify.toml`. The parity test keeps them in step.

## 4. DNS

At your registrar, or move the zone to Netlify DNS:

| Host | Type | Value | Notes |
|---|---|---|---|
| `adyraforge.com` | `A` | `75.2.60.5` (Netlify load balancer) | Or ALIAS/ANAME to `<site>.netlify.app` if supported |
| `www` | `CNAME` | `<site>.netlify.app` | Redirected to apex by `netlify.toml` |
| `api` | `CNAME` | `adyraforge-api.onrender.com` (exact host from Render) | Render issues the certificate |
| `adyraforge.com` | `CAA` | `0 issue "letsencrypt.org"` | Optional. Both Netlify and Render use Let's Encrypt |

**Force HTTPS:**
- Netlify: automatic once the certificate is issued.
- Render: redirects http → https.
- Django: `SECURE_SSL_REDIRECT` + HSTS (1 year, subdomains, preload).

Submit to hstspreload.org only after a week of everything working on HTTPS. Preload is hard to undo.

## 5. Sentry (both apps)

1. Create two projects: **django** (`adyraforge-api`) and **nextjs** (`adyraforge-web`). Put the DSNs in Render `SENTRY_DSN` and Netlify `NEXT_PUBLIC_SENTRY_DSN`.
2. What the code already does (tested):
   - **Backend** (`apps/core/monitoring.py`): errors only. `data_collection` turns *every* category off: user, cookies, headers, bodies, query params, stack-frame variables (they can hold passwords). `scrub_event` then strips cookies, bodies, IPs, auth/CSRF headers, query strings and signed-download tokens.
   - **Frontend:**
     - The browser SDK is loaded lazily after first paint (0 bytes added to initial JS) and sends through the same-origin `/monitoring` tunnel, which only forwards to *your* project.
     - The Node server reports request errors. The edge middleware stays Sentry-free.
     - Same all-off `dataCollection`, plus scrubbing of invite/reset/download tokens from URLs and breadcrumbs.
3. In **each Sentry project → Settings → Security & Privacy**, turn on *Data Scrubber*, *Use Default Scrubbers* and *Prevent Storing of IP Addresses*. Belt and braces.
4. Test: from the Render shell,
   ```bash
   python manage.py shell -c "import sentry_sdk; sentry_sdk.capture_message('deploy test'); sentry_sdk.flush()"
   ```
   It should appear in Sentry with no user, IP or cookies.

## 6. UptimeRobot

| Monitor | Type | URL | Check |
|---|---|---|---|
| Site | HTTPS | `https://adyraforge.com/` | status 200 |
| API | Keyword | `https://api.adyraforge.com/api/health` | keyword `"ok"` present |

5-minute interval, alert contact = your email. `/api/health` returns `{"status": "ok"}` without touching the database, so it measures the app, not Neon. Neon's own status page covers the database.

## 7. Dependabot

[`.github/dependabot.yml`](.github/dependabot.yml) opens weekly (Monday) PRs for pip (`backend/`, regenerating the hashed `requirements/*.txt`), npm (`frontend/`) and GitHub Actions. Also enable **Settings → Code security → Dependabot alerts + security updates** in the repo. Merge only green PRs: CI runs pytest, `check --deploy`, pip-audit, npm audit and the build.

## 8. Smoke checks against production

```bash
bash security/scripts/prod_smoke.sh
```

This checks:
- HTTPS redirects and www → apex.
- Every security header on both domains.
- That the frontend serves no repo or build-internal files (`CLAUDE.md`, settings, `.env`, Next manifests that hold preview keys, source maps).
- Page renders, `/api/health`, `/admin/` → 404, generic JSON errors, deep-JSON → 400, CORS allowlist, cookie flags.
- The proxy rate-limit check: forged `X-Forwarded-For` must not reset the limit.
- That the Sentry tunnel refuses foreign projects.

It exits non-zero on any failure.

Then by hand: securityheaders.com and SSL Labs on both domains; one real portal login (cookie `Domain=.adyraforge.com; Secure; HttpOnly; SameSite=Lax`); one real contact submission (Turnstile passes, the lead appears in admin, the email arrives); Lighthouse mobile on `/` (LCP < 2.5 s).

## 9. Backups and the restore drill

**What protects the data:**
- Neon point-in-time restore within the history window (§1.4).
- Optionally, an **off-site dump**: a monthly `pg_dump --format=custom` with the owner URL, encrypted (e.g. `age`) before it leaves your machine and stored privately. It contains client personal data, so never commit it (rule: no db dumps in git).

**Restore drill** (quarterly, and before any risky migration). Goal: prove you can get data back, and measure how long it takes.

1. Neon → **Branches → Create branch** → *From a point in time*: pick a timestamp ~1 hour ago.
2. Copy the branch's **direct** connection string (owner role) for the drill only. Use it locally, never in Render:
   ```bash
   docker compose run --rm -e DJANGO_ENV=development -e DATABASE_URL="<branch-url>?sslmode=require" backend python manage.py showmigrations --plan
   ```
   ```bash
   docker compose run --rm -e DJANGO_ENV=development -e DATABASE_URL="<branch-url>?sslmode=require" backend python manage.py shell -c "from apps.leads.models import Lead; from apps.clients.models import ClientProject, Invoice; print(Lead.objects.count(), ClientProject.objects.count(), Invoice.objects.count())"
   ```
3. Compare the counts with production (Django admin) and spot-check one recent lead and invoice.
4. **To actually restore:** run the release command against the branch with `MIGRATION_DATABASE_URL`, set it as the primary branch in Neon (or point Render's two DB URLs at it), and redeploy.
5. **Delete the drill branch.** Record the drill:

| Date | Restored to | Time to usable data (RTO) | Data age (RPO) | Result / notes |
|---|---|---|---|---|
| _first drill after launch_ | | | | |

## 10. Rollback

- **API:** Render → Deploys → previous deploy → *Rollback*. Migrations so far are additive; check before rolling back past one.
- **Frontend:** Netlify → Deploys → previous deploy → *Publish deploy*.
- **Database:** §9 restore to a branch, then swap the URLs.
