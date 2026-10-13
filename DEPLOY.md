# Deploying AdyraForge v2

The API runs on Render (Docker) at `api.adyraforge.com`, the database on Neon, and the frontend on Netlify at `adyraforge.com`. Same-site domains keep the session cookie working.

**Secrets never go in git or chat.** Enter them in the Render and Netlify dashboards. Every value below is a placeholder.

## 0. Blockers before go-live

| Blocker | Why | Status |
|---|---|---|
| Media storage (SECURITY_AUDIT_V2 **M-5**) | Production uses the container disk, and Render wipes it on every deploy, so client files and invoices would be lost | Needs a choice: **Cloudinary** (authenticated assets) or **S3** (private bucket + presigned URLs) |
| Netlify publishes the repo root (**M-4**) | `adyraforge.netlify.app` serves `CLAUDE.md`, settings source, etc. from `main` today | `fix/netlify-publish-v1-only` is ready; this repo's `netlify.toml` (base `frontend`) replaces it at cutover |
| Error monitoring (**M-6**) | Nobody is alerted on 500s | Optional for launch; needs a Sentry DSN |

## 1. Neon (database)

1. Create a project in a region near the Render region. `render.yaml` assumes `singapore`, so pick AWS `ap-southeast-1`.
2. Copy the **direct** (non-pooled) connection string with `?sslmode=require`. The app keeps connections open (`CONN_MAX_AGE=60`), which is incompatible with PgBouncer transaction pooling.
3. Turn on Neon's point-in-time restore or scheduled backups.

## 2. Render (API)

1. **New → Blueprint**, pick this repo, and confirm `render.yaml`. It creates `adyraforge-api` with `autoDeploy: false`.
2. Fill in the `sync: false` variables in the dashboard. Generate the two random values locally and paste them straight into Render:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(64))"
   ```
   (SECRET_KEY: 86 chars. Render's own `generateValue` is too short for the boot check.)
   ```bash
   python -c "import secrets; print('ops-' + secrets.token_urlsafe(18) + '/')"
   ```
   (ADMIN_URL. Keep it in your password manager. It must never appear in robots.txt, the frontend or docs.)
3. Deploy. The build log must show `pip install --require-hashes` succeeding. Pre-deploy runs `migrate` and `createcachetable`; on a free instance, run them once from **Shell**.
4. In the Render **Shell**:
   ```bash
   python manage.py check --deploy --fail-level WARNING
   ```
   ```bash
   python manage.py createsuperuser
   ```
   Then add your TOTP device as described in README → "Admin account and 2FA".
5. **Settings → Custom domain:** `api.adyraforge.com`. At your DNS provider, add the CNAME Render shows. Wait for the certificate.
6. Optional: a Render cron job that runs `python manage.py clearsessions` daily.

## 3. Netlify (frontend)

The API must be live first: ISR pages fetch from it at build time.

1. Site settings → Build & deploy: the repo's `netlify.toml` sets base directory `frontend`, publish `.next`, Node 22.
2. Environment variables (UI): `NEXT_PUBLIC_TURNSTILE_SITE_KEY` (public site key). Optionally `API_INTERNAL_URL=https://api.adyraforge.com`. Nothing secret.
3. Deploy, then add the custom domain `adyraforge.com` (plus `www` redirect) and enable HTTPS.
4. In Cloudflare Turnstile, add `adyraforge.com` to the widget's allowed hostnames.

## 4. Verify after deploy

These are the items SECURITY_AUDIT_V2 could not verify locally.

```bash
curl -sSI https://api.adyraforge.com/api/public/projects/
```
Expect HSTS preload, CSP `default-src 'none'`, XFO DENY, nosniff, and no stack traces.

```bash
curl -sSI https://adyraforge.com/
```
Expect the CSP from `next.config.ts` and HSTS.

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://api.adyraforge.com/admin/
```
Must print `404`.

```bash
for p in /prerender-manifest.json /server/middleware-manifest.json /cache/.previewinfo /BUILD_ID /CLAUDE.md /backend/config/settings/base.py; do printf "%s %s\n" "$(curl -s -o /dev/null -w '%{http_code}' https://adyraforge.com$p)" "$p"; done
```
Every line must start with `404`. Next's build manifests hold its preview-mode signing keys, and none of these files may be public.

```bash
for i in 1 2 3 4 5 6; do curl -s -o /dev/null -w "%{http_code} " -X POST https://api.adyraforge.com/api/auth/password/reset/ -H "Content-Type: application/json" -H "X-Forwarded-For: 198.51.100.$i" -d '{"email":"nobody@example.invalid"}'; done; echo
```
The **proxy check** (H-1). Expect `202 202 202 429 429 429`: the limit is 3/hour per real client IP, and the forged header changes every time without resetting it. If you see six 202s, `TRUSTED_PROXY_COUNT` is too high. Fix it before launch. Run this once from home and once from a phone hotspot: each network must get its own 3 requests. If the second network starts at 429, the count is too low, and every visitor would be sharing one bucket.

Then check by hand:
- securityheaders.com and SSL Labs on both domains, then submit `adyraforge.com` to hstspreload.org once you're sure every subdomain is HTTPS-only.
- Log in to the portal at `adyraforge.com/login`. The session cookie must be `Domain=.adyraforge.com; Secure; HttpOnly; SameSite=Lax`.
- One real contact-form submission: Turnstile passes, the lead appears in the admin, and the notification email arrives over TLS.
- Lighthouse mobile on `/` and a case study: LCP < 2.5 s, CLS < 0.1.

## 5. Rollback

- **API:** Render → Deploys → pick the previous deploy → *Rollback*. Migrations are additive so far; check before rolling back past one.
- **Frontend:** Netlify → Deploys → previous deploy → *Publish deploy*.
- **Database:** Neon point-in-time restore to a branch, then swap `DATABASE_URL`.
