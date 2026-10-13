# AdyraForge v2 — Project Rules

## What this is
Portfolio + lead engine + client portal for AdyraForge, a solo freelance web development brand
under Adyra Group, founded by Forge. Its job is to turn visitors into paying clients.
Every feature must serve that. Performance and trust beat spectacle.

## Architecture (do not change without asking)
- monorepo:
  - /frontend  → Next.js 15 (App Router, TypeScript, Tailwind CSS, React Three Fiber + drei,
                 GSAP + ScrollTrigger, Framer Motion, Lenis smooth scroll)
  - /backend   → Django 5 + Django REST Framework, Python 3.12
  - /ml        → recommender code (scikit-learn), imported by the backend as a package
- Database: PostgreSQL (Neon in prod, Docker Postgres locally). SQLite is forbidden, even in dev.
- ONE backend framework: Django. Do not add Flask, FastAPI or Express.
- Domains: frontend at adyraforge.com, API at api.adyraforge.com (same-site, so cookies work).
- Hosting: frontend on Netlify, backend on Render (or Railway), media on Cloudinary or S3.
- Local dev via docker-compose (postgres, backend, frontend).

## Roles
- Visitor (anonymous): public pages, contact form, project planner, recommendations.
- Client (authenticated, created by admin invite only — no public sign-up):
  sees ONLY their own projects, milestones, files, messages, invoices.
- Admin (Forge): everything, via custom dashboard + Django admin.

## Security non-negotiables (apply to every line of code)
1. No secret ever in code, commits, logs, or client bundles. Use django-environ; keep a
   committed `.env.example` with placeholder values only. `.env*` is in .gitignore.
   Only variables prefixed NEXT_PUBLIC_ may reach the browser, and none of them may be secret.
2. DEBUG=False by default; it is True only when DJANGO_ENV=development.
   SECRET_KEY, ALLOWED_HOSTS, DATABASE_URL, CORS/CSRF origins all come from env.
   The app must refuse to boot in production if SECRET_KEY is missing or default.
3. Passwords hashed with Argon2 (argon2-cffi), PBKDF2 as fallback. Never store or log plaintext.
4. Auth = Django session auth with HttpOnly, Secure, SameSite=Lax cookies + CSRF protection.
   No JWT in localStorage. Ever.
5. Every API view declares permission_classes explicitly. Default is IsAuthenticated —
   public endpoints opt out deliberately with AllowAny and a comment explaining why.
6. Object-level authorization on every client resource: querysets are filtered by
   request.user in get_queryset(), never just hidden in the UI. Accessing another
   client's object returns 404, not 403.
7. Admin hardening: Django admin moved to an unguessable path from env (ADMIN_URL),
   TOTP 2FA via django-otp for staff, django-axes lockout on failed logins.
8. Rate limiting: DRF throttles (anon + user + scoped) and stricter scopes on login,
   password reset, contact form and planner. 429 responses with Retry-After.
9. Input: DRF serializers validate every field (types, lengths, choices). Rich text is
   sanitized with nh3. Uploads: allowlisted MIME + extension, size cap, renamed to UUID,
   stored outside the web root / on Cloudinary, served via signed URLs for private files.
10. Forms: honeypot field + Cloudflare Turnstile on contact and planner. Server-side verify.
11. Headers (backend): SECURE_SSL_REDIRECT, HSTS (1 year, include subdomains, preload),
    SESSION/CSRF_COOKIE_SECURE, X-Content-Type-Options, Referrer-Policy, X-Frame-Options DENY,
    Content-Security-Policy via django-csp, Permissions-Policy.
    Headers (frontend): same set in netlify.toml / next.config headers, with a CSP that
    allows only the domains actually used.
12. CORS: django-cors-headers with an explicit allowlist from env. Never CORS_ALLOW_ALL_ORIGINS.
13. ORM only. No raw SQL with string formatting. If raw SQL is unavoidable, parameterize.
14. Errors: generic messages to users, details only in server logs (Sentry). No stack traces
    in responses. Do not log passwords, tokens, cookies or full request bodies.
15. Dependencies pinned (requirements via pip-tools, package-lock.json committed).
    Remove anything unused. No packages with known CVEs.

## Code quality
- Python: ruff + black, type hints, pytest-django. Frontend: ESLint, Prettier, strict TS.
- Every endpoint gets tests, including a test that a client CANNOT read another client's data.
- Small commits with clear messages. Never commit generated secrets, .env, db dumps, or node_modules.
- If a requirement is ambiguous or a rule above conflicts with a request, STOP and ask me.
  Do not guess on anything touching auth, payments, or data deletion.
- Never claim something is done or secure without running the check that proves it.

## Design language
- Brand: black and gold. Base #0A0A0B, surface #141416, gold #D4AF37, warm gold #F5C66A,
  text #F4F1EA, muted #8A8578, accent for links/focus #E8B04B. Gold is an accent, not a fill.
- Type: a sharp display face (e.g. "Clash Display" or "Syne") + "Inter" for body.
- Motion: purposeful. Respect prefers-reduced-motion everywhere (disable 3D + parallax).
- Performance budget (mobile, 4G): LCP < 2.5s, CLS < 0.1, INP < 200ms, initial JS < 200KB gz.
  3D scenes lazy-load after first paint, pause when off-screen, and fall back to a static
  image on low-end devices / no WebGL.
- Accessibility: WCAG 2.2 AA, keyboard navigable, visible focus, alt text, semantic HTML.
