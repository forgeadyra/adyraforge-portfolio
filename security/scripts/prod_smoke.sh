#!/usr/bin/env bash
# Phase 7 header + smoke checks against the DEPLOYED sites. curl only.
#   bash security/scripts/prod_smoke.sh
#   FRONT=https://x.netlify.app RENDER=https://y.onrender.com bash security/scripts/prod_smoke.sh
# Topology: the browser only talks to FRONT; FRONT proxies /api/* (signed) to RENDER.
# API checks therefore run through FRONT/api; RENDER is probed directly only to make
# sure it adds nothing a browser should rely on (admin hidden, forged IPs ignored).
# Read-only apart from honeypot form posts (nothing is stored) and password-reset
# POSTs for an address that does not exist (no email is sent). They use up this
# machine's per-IP budget on those endpoints for an hour.
set -u
FRONT="${FRONT:-https://adyraforge.netlify.app}"
RENDER="${RENDER:-https://adyraforge-api.onrender.com}"
API="$FRONT"
ORIGIN="${ORIGIN:-$FRONT}"
fails=0

check() { # label, condition-result(0/1), detail
  if [ "$2" -eq 0 ]; then echo "[PASS] $1${3:+  ->  $3}"; else echo "[FAIL] $1${3:+  ->  $3}"; fails=$((fails + 1)); fi
}
code() { curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$@"; }
hdrs() { curl -sS -D - -o /dev/null --max-time 20 "$@" | tr -d '\r'; }
has() { grep -qiF -- "$2" <<<"$1"; echo $?; }

echo "== $(date -u +%Y-%m-%dT%H:%MZ)  FRONT=$FRONT (API via $FRONT/api)  RENDER=$RENDER"

echo; echo "== HTTPS everywhere"
for host in "$FRONT" "$RENDER"; do
  plain="http://${host#*://}/"
  loc=$(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' --max-time 20 "$plain")
  [[ "$loc" =~ ^30[1278]\ https:// ]]; check "$plain redirects to https" $? "$loc"
done

echo; echo "== Frontend security headers ($FRONT/)"
h=$(hdrs "$FRONT/"); echo "$h" | grep -iE "^(content-security-policy|strict-transport|x-frame|x-content-type|referrer-policy|permissions-policy|cross-origin-opener|x-powered-by|server):" | sed 's/^/    /'
check "CSP default-src 'self'" "$(has "$h" "default-src 'self'")"
check "CSP frame-ancestors 'none'" "$(has "$h" "frame-ancestors 'none'")"
check "CSP object-src 'none'" "$(has "$h" "object-src 'none'")"
check "CSP upgrade-insecure-requests" "$(has "$h" "upgrade-insecure-requests")"
check "HSTS 1y + subdomains + preload" "$(has "$h" "max-age=31536000; includeSubDomains; preload")"
check "X-Frame-Options DENY" "$(has "$h" "x-frame-options: DENY")"
check "nosniff" "$(has "$h" "x-content-type-options: nosniff")"
check "Referrer-Policy" "$(has "$h" "referrer-policy: strict-origin-when-cross-origin")"
check "Permissions-Policy" "$(has "$h" "permissions-policy: accelerometer=()")"
check "COOP same-origin" "$(has "$h" "cross-origin-opener-policy: same-origin")"
grep -qi "^x-powered-by:" <<<"$h"; [ $? -ne 0 ]; check "no X-Powered-By" $?

echo; echo "== Frontend pages render"
for p in / /work /services /about /contact /planner /login /robots.txt /sitemap.xml; do
  c=$(code "$FRONT$p"); [ "$c" = 200 ]; check "GET $p 200" $? "$c"
done
c=$(code "$FRONT/portal"); [[ "$c" =~ ^30[278]$ ]]; check "anonymous /portal redirects to login" $? "$c"
robots=$(curl -s --max-time 20 "$FRONT/robots.txt")
grep -qi "admin\|ops-" <<<"$robots"; [ $? -ne 0 ]; check "robots.txt does not reveal an admin path" $?

echo; echo "== Nothing internal is served by the frontend"
for p in /CLAUDE.md /SECURITY_AUDIT_V1.md /SECURITY_AUDIT_V2.md /README.md /docker-compose.yml \
  /backend/config/settings/base.py /security/scripts/audit_common.py /.env /.git/config \
  /netlify.toml /package.json /prerender-manifest.json /server/middleware-manifest.json \
  /cache/.previewinfo /BUILD_ID /_next/static/chunks/main.js.map; do
  c=$(code "$FRONT$p"); [ "$c" = 404 ]; check "GET $p -> 404" $? "$c"
done

echo; echo "== API security headers through the proxy ($API/api/public/projects/)"
h=$(hdrs "$API/api/public/projects/"); echo "$h" | grep -iE "^(content-security-policy|strict-transport|x-frame|x-content-type|referrer-policy|permissions-policy|cross-origin-opener|x-powered-by|server):" | sed 's/^/    /'
[[ "$(head -1 <<<"$h")" =~ \ 200 ]]; check "API 200" $? "$(head -1 <<<"$h")"
check "CSP default-src 'none'" "$(has "$h" "default-src 'none'")"
check "HSTS 1y + subdomains + preload" "$(has "$h" "max-age=31536000; includeSubDomains; preload")"
check "X-Frame-Options DENY" "$(has "$h" "x-frame-options: DENY")"
check "nosniff" "$(has "$h" "x-content-type-options: nosniff")"
check "Permissions-Policy" "$(has "$h" "permissions-policy:")"
grep -qiE "^server:.*[0-9]" <<<"$h"; [ $? -ne 0 ]; check "no version in Server header" $?

echo; echo "== API health, admin, errors"
b=$(curl -s --max-time 20 "$API/api/health"); [ "$b" = '{"status": "ok"}' ]; check "GET /api/health" $? "$b"
c=$(code "$RENDER/healthz/"); [ "$c" = 200 ]; check "Render GET /healthz/ 200 (platform health check)" $? "$c"
for p in /admin/ /admin/login/ /django-admin/; do
  c=$(code "$RENDER$p"); [ "$c" = 404 ]; check "Render GET $p -> 404" $? "$c"
  c=$(code "$FRONT$p"); [ "$c" = 404 ]; check "Site GET $p -> 404 (admin is never proxied)" $? "$c"
done
b=$(curl -s --max-time 20 "$API/api/does-not-exist/"); [ "$b" = '{"detail": "Not found."}' ]; check "unknown API path: generic JSON 404" $? "$b"
b=$(curl -s --max-time 20 -X POST "$API/api/auth/login/" -H 'Content-Type: application/json' --data-binary "$(printf '[%.0s' $(seq 1 5000))$(printf ']%.0s' $(seq 1 5000))")
grep -q "nested too deeply" <<<"$b"; check "deep JSON -> 400, no traceback" $? "${b:0:80}"
grep -qiE "traceback|site-packages|File \"/" <<<"$b"; [ $? -ne 0 ]; check "no stack trace in error body" $?

echo; echo "== CORS and cookies"
h=$(hdrs -H "Origin: https://evil.example" "$API/api/auth/csrf/")
grep -qi "^access-control-allow-origin:" <<<"$h"; [ $? -ne 0 ]; check "evil Origin gets no ACAO" $?
h=$(hdrs -H "Origin: $ORIGIN" "$API/api/auth/csrf/")
check "own Origin allowed with credentials" "$(has "$h" "access-control-allow-origin: $ORIGIN")"
cookie=$(grep -i "^set-cookie: csrftoken=" <<<"$h" | sed -E 's/csrftoken=[^;]+/csrftoken=<redacted>/')
echo "    $cookie"
check "csrftoken cookie Secure" "$(has "$cookie" "; Secure")"
check "csrftoken cookie SameSite=Lax" "$(has "$cookie" "SameSite=Lax")"
check "csrftoken cookie HttpOnly" "$(has "$cookie" "HttpOnly")"
grep -qi "domain=" <<<"$cookie"; [ $? -ne 0 ]; check "csrftoken cookie is host-only (first-party to $FRONT)" $?

echo; echo "== Client IP behind Netlify + Render (H-1): forged headers never reset a limit"
codes=""
for i in 1 2 3 4; do
  codes="$codes $(code -X POST "$FRONT/api/auth/password/reset/" -H 'Content-Type: application/json' \
    -H "X-Forwarded-For: 198.51.100.$((RANDOM % 250 + 1))" -d '{"email":"nobody@example.invalid"}')"
done
[[ "$codes" =~ 429$ ]]; check "via site, rotating X-Forwarded-For: 4th password reset -> 429" $? "$codes"
BOT='{"name":"n","email":"n@example.invalid","project_type":"other","message":"m","website":"http://spam.example","turnstile_token":"t"}'
codes=""
for i in 1 2 3 4 5 6; do
  codes="$codes $(code -X POST "$FRONT/api/leads/contact/" -H 'Content-Type: application/json' \
    -H "X-Nf-Client-Connection-Ip: 192.0.2.$i" -d "$BOT")"
done
[[ "$codes" =~ 429$ ]]; check "via site, forged X-Nf-Client-Connection-Ip: 6th contact -> 429 (Netlify overwrites it)" $? "$codes"
codes=""
for i in $(seq 1 11); do
  codes="$codes $(code -X POST "$RENDER/api/leads/planner/" -H 'Content-Type: application/json' \
    -H "X-Nf-Client-Connection-Ip: 192.0.2.$i" -H "X-Forwarded-For: 203.0.113.$i" \
    -d '{"project_type":"web_app","website":"http://spam.example","turnstile_token":"t"}')"
done
[[ "$codes" =~ 429$ ]]; check "direct to Render, forged Netlify + XFF headers: 11th planner -> 429" $? "$codes"

echo; echo "== Sentry tunnel accepts only our project"
c=$(code -X POST "$FRONT/monitoring" -H 'Content-Type: text/plain' \
  --data-binary $'{"dsn":"https://k@o999.ingest.sentry.io/999"}\n{}')
[[ "$c" =~ ^(403|404)$ ]]; check "foreign DSN refused (403, or 404 if Sentry is off)" $? "$c"

echo; echo "$fails failure(s)"
exit $((fails > 0))
