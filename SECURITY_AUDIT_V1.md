# AdyraForge v1 — Security Audit

**Date:** 2026-10-13
**Scope covered so far:** `forgeadyra/adyraforge-portfolio` (public GitHub repo, 4 commits, 1 branch), live site `https://adyraforge.netlify.app`
**Scope still pending:** the other project repos (not provided yet).

## Summary

| # | Severity | Finding |
|---|----------|---------|
| — | — | **No leaked secrets found.** No keys to rotate for this repo. |
| H1 | High | No `.gitignore` in a public repo whose root is deployed verbatim |
| M1 | Medium | Internal files (`CLAUDE.md`, `README.md`) are publicly served from the live site |
| M2 | Medium | Missing security headers: CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy |
| L1 | Low | Untracked backup files in the working tree (`index.local-*.html`) |
| L2 | Low | No `security.txt` |
| I1 | Info | npm audit / pip-audit: not applicable (no dependencies) |

There are no Critical findings.

---

## 1. Secrets scan (full git history)

| Tool | Command | Result |
|------|---------|--------|
| gitleaks 8.30.1 | `gitleaks detect --source . --log-opts="--all" --redact -v` | 4 commits, ~58 KB scanned. **No leaks found** |
| gitleaks (no-git) | on untracked `index.local-backup.html`, `index.local-original.html` | **No leaks found** |
| Manual grep | `git log --all -p` for key, token, password, `sk_`, `AIza`, `ghp_`, form-service IDs (Formspree, EmailJS, Web3Forms, Firebase, Supabase) | Only hits are the rule text in `CLAUDE.md`. No credentials |
| trufflehog 3.99.2 (Docker) | `trufflehog git file:///repo --results=verified,unverified,unknown` | 13 chunks / 58.6 KB. **0 verified, 0 unverified** |

The site has no `<form>`, no `fetch()`, and no third-party script tags. Its only external origins are Google Fonts and outbound links (GitHub, Fiverr, a demo on `phenomenal-belekoy-881bf4.netlify.app`). Nothing in it needs a key, which matches the empty scan.

The commit author email `forgeadyra@gmail.com` is public in history. It is also already shown on the site as a `mailto:` link, so this is not a leak. Mentioned only for awareness.

**Keys to rotate: none (for this repo).**

## 2. Exposed files on the live deploy

Probed: `/.env`, `/.env.local`, `/.env.production`, `/.git/config`, `/.git/HEAD`, `/.gitignore`, `/.DS_Store`, `/index.local-backup.html`, `/index.local-original.html`, `/netlify.toml`, `/_redirects`, `/_headers`, `/package.json`, `/package-lock.json`, `/index.html.bak`, `/backup.zip`, `/admin`, `/admin/`, `/wp-admin`, `/*.js.map`, `/robots.txt`, `/sitemap.xml`, `/.well-known/security.txt`.

- All of these return **404**, except:
- `/README.md` returns **200** (`text/markdown`)
- `/CLAUDE.md` returns **200** (`text/markdown`): the full v2 architecture and security plan
- The live `index.html` is byte-identical to the repo's `index.html` once CRLF line endings and a Netlify-injected HTML comment are ignored. Nothing unexpected is deployed.

## 3. Live response headers (`curl -I https://adyraforge.netlify.app/`)

| Header | Status |
|--------|--------|
| Strict-Transport-Security | ✅ `max-age=31536000; includeSubDomains; preload` (Netlify default on `*.netlify.app`) |
| HTTP → HTTPS redirect | ✅ 301 |
| Content-Security-Policy | ❌ missing |
| X-Frame-Options / `frame-ancestors` | ❌ missing (clickjacking) |
| X-Content-Type-Options | ❌ missing |
| Referrer-Policy | ❌ missing (browser default applies) |
| Permissions-Policy | ❌ missing |
| Cross-Origin-Opener-Policy | ❌ missing (nice-to-have) |

## 4. Dependency audit

There is no `package.json`, `package-lock.json` or `requirements*.txt` in this repo. It is a single hand-written `index.html` with no build step, so npm audit and pip-audit do not apply. The site loads no third-party JavaScript.

The inline script contains no `innerHTML`, `eval`, `document.write`, `insertAdjacentHTML`, `localStorage` or inline `on*=` handlers. All `target="_blank"` links have `rel="noopener noreferrer"`.

---

## Findings and exact fixes

### H1 — No `.gitignore` in a public, root-deployed repo (High)

**Risk:** Nothing is leaked today. But the repo is public and Netlify serves the repo root as-is. The first `.env`, `node_modules`, db dump or `*.bak` you create here would be committed to public GitHub and also served at `https://adyraforge.netlify.app/<file>`. v2 adds a Django backend with real secrets, so this is the most likely source of a future leak.

**Fix:** add a `.gitignore` at the repo root. For v2, also add a gitleaks pre-commit hook and a gitleaks CI job so a leak is blocked before it is pushed.

```gitignore
# secrets
.env
.env.*
!.env.example
*.pem
*.key
# deps / builds
node_modules/
.next/
out/
__pycache__/
*.pyc
.venv/
# data / backups
*.sql
*.dump
*.sqlite3
*.bak
*.local-*.html
# OS / editor
.DS_Store
Thumbs.db
.vscode/
.idea/
```

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.30.1
    hooks:
      - id: gitleaks
```

### M1 — `CLAUDE.md` and `README.md` are publicly served (Medium)

**Risk:** `https://adyraforge.netlify.app/CLAUDE.md` gives anyone your planned stack, hosting, auth design and admin-hardening approach. It contains no secrets, and the plan is sound even when known. Still, there's no reason to publish the defender's checklist, and a root-published deploy will serve every future repo file the same way.

**Fix (pick one; option A is preferred and carries into v2):**

A. Move the site into its own publish directory:
```
public/index.html      ← git mv index.html public/index.html
netlify.toml           ← publish = "public"
```
```toml
[build]
  publish = "public"
```

B. Keep the layout and block the files with redirects in `netlify.toml`:
```toml
[[redirects]]
  from = "/CLAUDE.md"
  to = "/404"
  status = 404
  force = true
[[redirects]]
  from = "/README.md"
  to = "/404"
  status = 404
  force = true
```

Afterwards, check that `curl -s -o /dev/null -w "%{http_code}" https://adyraforge.netlify.app/CLAUDE.md` returns `404`.

### M2 — Missing security headers (Medium)

**Fix:** add these headers to `netlify.toml`. The CSP below is tailored to this exact page: one inline `<script>` (allowed by hash, not `unsafe-inline`), one `<style>` block plus one `style=""` attribute, Google Fonts, and no images or iframes.

```toml
[[headers]]
  for = "/*"
  [headers.values]
    Content-Security-Policy = "default-src 'none'; script-src 'sha256-sBX9/GdI1BEvH2B3nLM0c+kVHqA8p397buA2CjrrPN8='; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'; upgrade-insecure-requests"
    X-Frame-Options = "DENY"
    X-Content-Type-Options = "nosniff"
    Referrer-Policy = "strict-origin-when-cross-origin"
    Permissions-Policy = "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()"
    Cross-Origin-Opener-Policy = "same-origin"
```

Notes:
- **The script hash changes whenever the inline script changes.** Recompute it after each edit, or move the script to `/main.js` and use `script-src 'self'`. Moving it is the better long-term option.
- `'unsafe-inline'` in `style-src` covers the single `style=""` attribute. Move that rule into the `<style>` block and hash it to drop `'unsafe-inline'` entirely.
- Load the page with DevTools open after deploying. Any CSP violation appears in the console.

Verify with `curl -sI https://adyraforge.netlify.app/`, then confirm A+ at securityheaders.com.

### L1 — Backup files in the working tree (Low)

`index.local-backup.html` and `index.local-original.html` are identical, untracked, and contain no secrets. They aren't deployed (both 404), but one `git add .` without a `.gitignore` would publish them. Once you've confirmed you don't need them, delete them or move them outside the repo. The `.gitignore` in H1 also covers them.

### L2 — No `security.txt` (Low)

Add `/.well-known/security.txt` (RFC 9116) so researchers know how to reach you:
```
Contact: mailto:forgeadyra@gmail.com
Expires: 2027-10-13T00:00:00.000Z
Preferred-Languages: en
```

---

## Coverage gaps (to close before calling this audit complete)

1. ~~trufflehog not run~~: done via Docker. Clean.
2. **pip-audit not installed.** It isn't needed for this repo, but will be for the other repos and the v2 backend: `pip install pip-audit`.
3. **Other repos not yet provided.** Each needs the same treatment: gitleaks plus trufflehog on full history, npm audit / pip-audit, and live-deploy probes where deployed.
4. Not checked: the Netlify dashboard (deploy previews, environment variables, form submissions, collaborators) and GitHub settings (2FA, deploy keys, Actions secrets).

## Leaked-secret policy (for every repo)

For any secret found: **rotate or revoke it at the provider first**, then scrub history with `git filter-repo`, then force-push and ask GitHub support to purge cached views. Removing a secret from history alone is not a fix; assume it was scraped the moment it was pushed. History is not rewritten until rotation is confirmed.
