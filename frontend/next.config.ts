import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV === "development";
const OFFLINE = process.env.NEXT_BUILD_WITHOUT_API === "1";
// Plain http is only acceptable for local services (dev, Docker, a local `next start`).
const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "backend"]);

function originOf(raw: string | undefined, name: string, fallback: string): URL {
  if (!raw) {
    if (isDev || OFFLINE) return new URL(fallback);
    throw new Error(`${name} must be set for production builds.`);
  }
  const url = new URL(raw);
  if (url.protocol !== "https:" && !LOCAL_HOSTS.has(url.hostname)) {
    throw new Error(`${name} must use https:// (got ${url.origin}).`);
  }
  return url;
}

// Server-side only: where the Next server (build, ISR, middleware) and the /api
// proxy below reach Django. Production: the Render origin. The browser never sees
// it: browser calls are same-origin /api/* (Netlify proxies them in production).
const api = originOf(process.env.API_INTERNAL_URL, "API_INTERNAL_URL", "http://localhost:8000");
// The site's own public origin (metadata, sitemap, JSON-LD). Env-only, so moving to
// a custom domain later changes no code.
const site = originOf(
  process.env.NEXT_PUBLIC_SITE_URL,
  "NEXT_PUBLIC_SITE_URL",
  "http://localhost:3000",
);
// Public media bucket (Backblaze B2). Locally, Django serves /media from the API.
const media = originOf(process.env.NEXT_PUBLIC_MEDIA_URL, "NEXT_PUBLIC_MEDIA_URL", api.origin);

// B2 serves public files from several hosts (f00N.backblazeb2.com and
// <bucket>.s3.<region>.backblazeb2.com), so production allows the provider's domain.
// netlify.toml repeats this exact CSP (a test keeps them identical), which is why it
// is a fixed value and not derived from the bucket's URL.
const B2_MEDIA = "https://*.backblazeb2.com";
function mediaSource(u: URL): string {
  if (LOCAL_HOSTS.has(u.hostname)) return u.origin;
  if (u.protocol === "https:" && u.hostname.endsWith(".backblazeb2.com")) return B2_MEDIA;
  throw new Error(
    `NEXT_PUBLIC_MEDIA_URL (${u.origin}) is not a Backblaze B2 host: update the media ` +
      "CSP source in next.config.ts and netlify.toml together.",
  );
}

const TURNSTILE = "https://challenges.cloudflare.com";

// Only the origins the site actually uses. Fonts are self-hosted by next/font.
// API calls and the Sentry tunnel are same-origin ('self'). 'unsafe-inline' for
// scripts is required by Next's inline hydration scripts unless every page is
// rendered dynamically with a nonce (README, "CSP").
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline' ${TURNSTILE}${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  `img-src 'self' data: blob: ${mediaSource(media)}`,
  "font-src 'self'",
  `connect-src 'self' ${TURNSTILE}${isDev ? " ws://localhost:3000" : ""}`,
  `frame-src ${TURNSTILE}`,
  "worker-src 'self' blob:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
  ...(site.protocol === "https:" && !isDev ? ["upgrade-insecure-requests"] : []),
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains; preload" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
  {
    key: "Permissions-Policy",
    value:
      "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=(), interest-cohort=()",
  },
];

const remote = (u: URL) => ({
  protocol: u.protocol.replace(":", "") as "http" | "https",
  hostname: u.hostname,
  ...(u.port ? { port: u.port } : {}),
  pathname: "/**",
});

const nextConfig: NextConfig = {
  poweredByHeader: false,
  productionBrowserSourceMaps: false,
  reactStrictMode: true,
  images: { remotePatterns: [remote(media)], formats: ["image/avif", "image/webp"] },
  // Linting runs as its own CI step with the project's flat config.
  eslint: { ignoreDuringBuilds: true },
  // Django URLs end in "/": never let Next strip it before the /api proxy below.
  skipTrailingSlashRedirect: true,
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
  async rewrites() {
    // Same-origin /api for dev and a local `next start`. On Netlify the netlify.toml
    // signed proxy rule answers /api/* first, so this never runs there.
    return [{ source: "/api/:path(.*)", destination: `${api.origin}/api/:path` }];
  },
};

export default nextConfig;
