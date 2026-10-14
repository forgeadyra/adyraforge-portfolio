# Deploying AdyraForge v2 (free tier, no custom domain)

Production is **https://adyraforge.netlify.app**, and nothing else is browser-facing.

```
browser ──► adyraforge.netlify.app ──(/api/*, signed proxy)──► adyraforge-api.onrender.com ──► Neon (TLS)
                 │  pages: Next.js on Netlify                         Django + gunicorn (free)
                 └─ build / ISR / middleware call the Render URL directly (API_INTERNAL_URL)
media: Backblaze B2 (public bucket for images, private bucket for client files)
```

**You enter every secret yourself, in the dashboards. Never in git, never in chat.** Values in angle brackets are placeholders. Dashboard labels drift over time; if a menu name differs slightly, look for the nearest equivalent.

Accounts you need (all free, no card): **Neon**, **Backblaze B2**, **Render**, **Netlify** (exists), **Cloudflare** (for Turnstile), a **Google account** with 2-Step Verification (Gmail), **UptimeRobot**, and **GitHub** (exists).

## 0. Order of work

1. Generate the three shared secrets (§1).
2. Neon (§2), then Backblaze B2 (§3), Gmail (§4) and Turnstile (§5).
3. The first migration and admin user, run from your machine (§6).
4. Render (§7). The API must be live **before** the v2 PR merges: Netlify's build reads content from it and fails, by design, if it can't.
5. GitHub secrets (§8), then Netlify env vars (§9).
6. Merge the v2 PR (#2). Netlify builds `main` and the site goes live.
7. UptimeRobot (§10), then the smoke checks (§11).

## 1. Generate the shared secrets (on your machine)

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```
→ **SECRET_KEY** (Render only).

```bash
python -c "import secrets; print('ops-' + secrets.token_urlsafe(18) + '/')"
```
→ **ADMIN_URL** (Render only). Keep it in your password manager. It must never appear in robots.txt, the frontend or docs.

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```
→ **NETLIFY_PROXY_SIGNING_SECRET**. Use the **same value** in Render *and* Netlify. Netlify signs every proxied `/api` request with it, and Django only believes Netlify's client-IP header when the signature checks out.

## 2. Neon (PostgreSQL)

1. https://console.neon.tech → **New Project**. Name `adyraforge`, Postgres **16**, region **AWS Asia Pacific (Singapore)** (next to Render's `singapore`). Database name: `neondb`.
2. **Dashboard → Connect.** Pick role `neondb_owner` and turn **Connection pooling OFF** (direct host, not `-pooler`). Copy the URL. It already ends in `?sslmode=require`, which production insists on. This is the **owner URL**.
3. **SQL Editor**, connected as `neondb_owner`. Paste [`deploy/neon_app_role.sql`](deploy/neon_app_role.sql), replace `REPLACE-IN-EDITOR-ONLY` with a strong new password, and **Run**. Don't save that password anywhere but your password manager. The last result row must show only `f`.
   - This creates `adyraforge_app`, which can read and write rows but can't create, alter, drop or truncate tables, or create roles.
   - Create it with SQL, as here; roles created in the console join `neon_superuser`.
4. **Connect** again, this time with role `adyraforge_app` and pooling **OFF**. This is the **app URL**. Use the password you just set.
5. **Backups.** Neon keeps point-in-time history automatically. Check **Settings → Storage** (or *History retention*) for your plan's window; the free plan's window is short. For longer retention, take the monthly off-site dump in §13.

Where each URL goes:

| URL | Goes to | Used for |
|---|---|---|
| owner URL | GitHub secret `NEON_OWNER_DATABASE_URL`, and §6 on your machine | migrations only |
| app URL | Render `DATABASE_URL`, and GitHub secret `NEON_APP_DATABASE_URL` | the running API; the daily `clearsessions` |

## 3. Backblaze B2 (storage, no card needed)

1. https://www.backblaze.com/sign-up/cloud-storage → create the account and verify your email.
2. **B2 Cloud Storage → Buckets → Create a Bucket.** Do this twice:
   - `adyraforge-private` (names are global: add a suffix if taken). **Files in Bucket: Private.** Default encryption: Enable.
   - `adyraforge-media`. **Files in Bucket: Public.** If B2 asks you to verify something before allowing a public bucket, do it.
3. On each bucket card, note the **Endpoint**, e.g. `s3.us-west-004.backblazeb2.com`. The region is the part after `s3.`, here `us-west-004`.
4. For **each** bucket: **Lifecycle Settings → Keep only the last version of the file.** B2 keeps every version by default, so deleted files would still count against the 10 GB.
5. **Application Keys → Add a New Application Key.** Name `adyraforge-render`, **Allow access to Bucket(s): All**, **Type of Access: Read and Write**. Copy the **keyID** and the **applicationKey**; the key is shown once.
   - B2 can scope a key to one bucket or to all buckets, and the API needs both. So keep this B2 account for these two buckets only.
6. Values for Render:

   | Render variable | Value |
   |---|---|
   | `PRIVATE_BUCKET` / `MEDIA_BUCKET` | your two bucket names |
   | `STORAGE_ENDPOINT_URL` | `https://s3.<region>.backblazeb2.com` |
   | `STORAGE_REGION` | `<region>`, e.g. `us-west-004` |
   | `STORAGE_ACCESS_KEY_ID` / `STORAGE_SECRET_ACCESS_KEY` | the keyID / the applicationKey |
   | `MEDIA_URL` | `https://<MEDIA_BUCKET>.s3.<region>.backblazeb2.com/` |

   And for Netlify: `NEXT_PUBLIC_MEDIA_URL` = the same origin, without the trailing slash.
7. Check that the private bucket really is private. In a browser, open `https://adyraforge-private.s3.<region>.backblazeb2.com/x`. It must answer with an error (AccessDenied or NoSuchKey), never a listing.

## 4. Gmail app password (outgoing mail)

1. https://myaccount.google.com/security → **2-Step Verification** must be **On**.
2. https://myaccount.google.com/apppasswords → App name `AdyraForge Render` → **Create**. Copy the 16-letter password (spaces don't matter).
3. That's Render's `EMAIL_HOST_PASSWORD`. The rest is already in `render.yaml`:
   - host `smtp.gmail.com`, port 587, TLS;
   - user and sender `forgeadyra@gmail.com`;
   - lead alerts to `forgeadyra@gmail.com`.

   Revoke the app password from the same page if it ever leaks.

## 5. Cloudflare Turnstile (bot check on contact and planner)

1. https://dash.cloudflare.com → **Turnstile → Add widget**. No domain on Cloudflare is needed.
2. Widget name `AdyraForge`. **Hostname: `adyraforge.netlify.app`.** Widget mode **Managed** → **Create**.
3. **Site key** → Netlify `NEXT_PUBLIC_TURNSTILE_SITE_KEY` (public). **Secret key** → Render `TURNSTILE_SECRET_KEY`.
   - The API also checks that each passed challenge reports hostname `adyraforge.netlify.app` (taken from `FRONTEND_URL`).

## 6. First migration and admin user (on your machine, once)

Render's free instance has no shell. Before the v2 PR merges, the migration workflow can't be run from GitHub either: it only appears in Actions once it's on `main`. So run these from the repo, with Docker up. The URLs are only ever typed into your own terminal.

```bash
docker compose run --rm -e DJANGO_ENV=maintenance -e DATABASE_URL="<owner URL>" -e SECRET_KEY="<any 50+ random chars>" backend sh -c "python manage.py migrate --noinput && python manage.py createcachetable"
```

```bash
docker compose run --rm -e DJANGO_ENV=maintenance -e DATABASE_URL="<app URL>" -e SECRET_KEY="<any 50+ random chars>" backend python manage.py createsuperuser
```

Then add your TOTP device the same way: the README's "Admin account and 2FA" command, using the `DJANGO_ENV=maintenance` / app-URL prefix shown above.

The `maintenance` settings need only the database URL and a throwaway key. They serve nothing: no allowed hosts, no URLs.

## 7. Render (API, free instance)

1. https://dashboard.render.com → **New → Blueprint** → connect GitHub → repo `forgeadyra/adyraforge-portfolio`.
   - **Branch: `v2/foundation`** for the launch. Switch it to `main` after the merge (§12).
2. Render reads [`render.yaml`](render.yaml) and shows **adyraforge-api (Free)**. Fill in every empty (`sync: false`) value:

   | Variable | Value |
   |---|---|
   | `SECRET_KEY`, `ADMIN_URL`, `NETLIFY_PROXY_SIGNING_SECRET` | from §1 |
   | `DATABASE_URL` | the Neon **app URL** (§2.4) |
   | `EMAIL_HOST_PASSWORD` | the Gmail app password (§4) |
   | `TURNSTILE_SECRET_KEY` | the Turnstile secret key (§5) |
   | `PRIVATE_BUCKET`, `MEDIA_BUCKET`, `MEDIA_URL`, `STORAGE_ACCESS_KEY_ID`, `STORAGE_SECRET_ACCESS_KEY` | from §3 |
   | `SENTRY_DSN` | optional (§14) |

   Also **edit** the two B2 example values in `render.yaml`, `STORAGE_REGION` and `STORAGE_ENDPOINT_URL`, to your bucket's region.

   Preset in `render.yaml`, no action needed:
   - `DJANGO_ENV=production`
   - `TRUSTED_PROXY_COUNT=1`
   - `ALLOWED_HOSTS=adyraforge-api.onrender.com`
   - `FRONTEND_URL`, `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS` = `https://adyraforge.netlify.app`
   - the Gmail SMTP host, port, TLS, user and sender
   - `LEAD_NOTIFY_EMAIL`, `WEB_CONCURRENCY=2`

   Leave **`SESSION_COOKIE_DOMAIN` unset**: cookies are host-only on `adyraforge.netlify.app`.
3. **Apply.** The first deploy builds the Docker image; the log must show `pip install --require-hashes` succeeding.
   - A missing or weak value stops the boot with `ImproperlyConfigured: Refusing to start in production`, naming the variable (never its value). Fix it, then **Manual Deploy**.
4. Note the service URL at the top of the service page.
   - **If it isn't exactly `https://adyraforge-api.onrender.com`** (the name was taken), change it in three places: Render `ALLOWED_HOSTS`, the `to =` line of the `/api/*` rule in `netlify.toml`, and Netlify's `API_INTERNAL_URL`.
5. Check `https://adyraforge-api.onrender.com/api/health` → `{"status": "ok"}`. The first request after idle takes about a minute: the free instance was asleep.
6. **Settings → Deploy Hook** → copy the URL. It's a secret; it goes to GitHub in §8.

## 8. GitHub (secrets for the Actions)

Repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Value | Used by |
|---|---|---|
| `NEON_OWNER_DATABASE_URL` | Neon owner URL | `deploy-backend.yml`: `migrate` + `createcachetable`, then the deploy hook |
| `NEON_APP_DATABASE_URL` | Neon app URL | `maintenance.yml`: daily `clearsessions` (03:30 UTC) |
| `RENDER_DEPLOY_HOOK_URL` | Render deploy hook | `deploy-backend.yml` |

Also: **Settings → Code security → Dependabot alerts** and **Dependabot security updates** → Enable. (`.github/dependabot.yml` already opens weekly update PRs.)

## 9. Netlify (frontend)

1. https://app.netlify.com → site **adyraforge** → **Site configuration → Build & deploy**. The production branch is `main`. [`netlify.toml`](netlify.toml) sets everything else:
   - base `frontend`, publish `.next`, Node 22;
   - the Next.js runtime;
   - the signed `/api/*` proxy;
   - the security headers.
2. **Site configuration → Environment variables → Add a variable.** Scopes: **All**; contexts: **All**. Mark the secret one as *Contains secret values*.

   | Variable | Value |
   |---|---|
   | `API_INTERNAL_URL` | `https://adyraforge-api.onrender.com` (the Render URL from §7.4) |
   | `NEXT_PUBLIC_SITE_URL` | `https://adyraforge.netlify.app` |
   | `NEXT_PUBLIC_MEDIA_URL` | `https://<MEDIA_BUCKET>.s3.<region>.backblazeb2.com` |
   | `NEXT_PUBLIC_TURNSTILE_SITE_KEY` | Turnstile site key (§5) |
   | `NETLIFY_PROXY_SIGNING_SECRET` | same value as on Render (§1). **Its scopes must include Runtime**, or the proxy can't sign |
   | `NEXT_PUBLIC_SENTRY_DSN` | optional (§14) |

3. HTTPS is automatic on `*.netlify.app`.
4. Deploy previews of PR #2 also build against the API. Public pages work there, but **logging in only works on `adyraforge.netlify.app`**: the API trusts that one origin for CSRF and signatures.

## 10. UptimeRobot (keeps the free API awake and tells you when it's down)

https://uptimerobot.com → **Add New Monitor**:

| Type | Friendly name | URL | Interval |
|---|---|---|---|
| HTTP(s) | AdyraForge site | `https://adyraforge.netlify.app/` | 5 min |
| Keyword (exists: `ok`) | AdyraForge API | `https://adyraforge.netlify.app/api/health` | 5 min |

The API monitor goes through Netlify's proxy to Render. Pinging every 5 minutes keeps the free instance from sleeping, which takes 15 idle minutes. That matters because **Netlify's proxy gives up after 26 seconds** and a cold start takes about 60, so the first browser call after a sleep would fail.

A free instance awake around the clock uses about 744 of Render's 750 free hours per month, so keep it the only free Render service in the workspace. Add your email as the alert contact.

## 11. Smoke checks against production

```bash
bash security/scripts/prod_smoke.sh
```

It checks:
- HTTPS and every security header on the site and through `/api`;
- that no repo or build-internal file is served;
- `/admin/` → 404 on both the site and Render;
- generic JSON errors and deep-JSON → 400;
- CORS and host-only cookies;
- that forged client-IP headers never reset a rate limit, whether sent through Netlify or straight to Render;
- that the Sentry tunnel refuses foreign projects.

It exits non-zero on any failure.

Then by hand:
- securityheaders.com and SSL Labs on `adyraforge.netlify.app`;
- a portal login: the cookie must be host-only, `Secure; HttpOnly; SameSite=Lax`;
- one real contact submission: Turnstile passes, the lead appears in the admin at `https://adyraforge-api.onrender.com/<ADMIN_URL>`, and the email arrives;
- a file download: it must redirect to a `…backblazeb2.com` URL that expires;
- Lighthouse mobile on `/`.

## 12. Launch, merge, and after

1. Render is live (§7), §11's API checks pass against the Render URL, and PR #2's Netlify deploy preview builds. **Then** merge PR #2.
2. Netlify builds `main` and publishes v2. This replaces the `legacy/` stopgap.
3. `deploy-backend.yml` runs on the merge: it migrates, then triggers Render.
   - In Render, switch the Blueprint/service branch to **`main`**. Keep **Auto-Deploy off**: deploys come from the hook, after migrations.
4. **Actions → Maintenance → Run workflow** once by hand, to see `clearsessions` succeed.

**Moving to a custom domain later is env-only:**
- Render: `FRONTEND_URL`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`.
- Netlify: `NEXT_PUBLIC_SITE_URL`.
- The Turnstile widget hostname.

## 13. Backups and the restore drill

- **Neon point-in-time restore** within the history window (§2.5).
- **Off-site dump** (optional, monthly):
  ```bash
  pg_dump --format=custom "<owner URL>" > adyraforge.dump
  ```
  Encrypt it (e.g. `age`) before it leaves your machine and store it privately. It contains client personal data: never commit it.

**Restore drill** (quarterly, and before any risky migration):
1. Neon → **Branches → Create branch** → *From a point in time*, about an hour ago.
2. Copy that branch's **direct** owner URL, and use it locally only:
   ```bash
   docker compose run --rm -e DJANGO_ENV=maintenance -e DATABASE_URL="<branch URL>" -e SECRET_KEY="<any 50+ chars>" backend python manage.py showmigrations --plan
   ```
   ```bash
   docker compose run --rm -e DJANGO_ENV=maintenance -e DATABASE_URL="<branch URL>" -e SECRET_KEY="<any 50+ chars>" backend python manage.py shell -c "from apps.leads.models import Lead; from apps.clients.models import ClientProject, Invoice; print(Lead.objects.count(), ClientProject.objects.count(), Invoice.objects.count())"
   ```
3. Compare the counts with production (Django admin), and spot-check one recent lead and invoice.
4. **To actually restore:** make the branch primary in Neon, or point Render's `DATABASE_URL` and the two GitHub secrets at it, then redeploy.
5. Delete the drill branch and record the drill:

| Date | Restored to | Time to usable data (RTO) | Data age (RPO) | Result / notes |
|---|---|---|---|---|
| _first drill after launch_ | | | | |

## 14. Sentry (optional)

Create two projects, **django** and **nextjs**. Put the DSNs in Render `SENTRY_DSN` and Netlify `NEXT_PUBLIC_SENTRY_DSN`.
- All data collection is off in code, plus scrubbers (`apps/core/monitoring.py`, `frontend/src/lib/sentry-scrub.ts`).
- In each project's **Settings → Security & Privacy**, also enable *Data Scrubber*, *Use Default Scrubbers* and *Prevent Storing of IP Addresses*.

## 15. Rollback

- **API:** Render → **Deploys** → a previous deploy → **Rollback**. Migrations so far are additive.
- **Frontend:** Netlify → **Deploys** → a previous deploy → **Publish deploy**.
- **Database:** §13 restore to a branch, then swap the URLs.
