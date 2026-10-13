#!/usr/bin/env sh
# Grep everything a browser can receive from a production Next build for secrets,
# internal URLs, the admin path and source maps. Run from frontend/ after a build made
# with API_INTERNAL_URL=http://127.0.0.1:8000 and AUDIT_SERVER_ONLY_CANARY=canary-secret-7d1f0b.
shipped() {
  find .next/static -type f
  find .next/server/app -type f \( -name '*.html' -o -name '*.rsc' -o -name '*.body' \)
}
echo "browser-shipped files: $(shipped | wc -l)"
for pat in "canary-secret-7d1f0b" "AUDIT_SERVER_ONLY_CANARY" "127.0.0.1:8000" "API_INTERNAL_URL" \
  "backend:8000" "/admin/" "SECRET_KEY" "TURNSTILE_SECRET" "DATABASE_URL" "postgres://" \
  "EMAIL_HOST_PASSWORD" "BEGIN .*PRIVATE KEY" "sk_live_" "AKIA[0-9A-Z]{16}" "sourceMappingURL"; do
  n=$(shipped | tr '\n' '\0' | xargs -0 grep -lE -- "$pat" 2>/dev/null | wc -l)
  echo "grep -lE '$pat' <browser-shipped>  -> $n file(s)"
done
echo "source maps anywhere in .next:"; find .next -name '*.map'
echo "server-only canary anywhere in .next: $(grep -rl 'canary-secret-7d1f0b' .next | wc -l) file(s)"
