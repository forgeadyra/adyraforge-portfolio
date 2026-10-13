import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV === "development";
const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1"]);

function originOf(raw: string | undefined, name: string, fallback: string): URL {
  if (!raw) {
    if (isDev || process.env.NEXT_BUILD_WITHOUT_API === "1") return new URL(fallback);
    throw new Error(`${name} must be set for production builds.`);
  }
  const url = new URL(raw);
  // Plain http is only acceptable for a local API (e.g. a local production test).
  if (url.protocol !== "https:" && !LOCAL_HOSTS.has(url.hostname)) {
    throw new Error(`${name} must use https:// (got ${url.origin}).`);
  }
  return url;
}

const api = originOf(
  process.env.NEXT_PUBLIC_API_URL,
  "NEXT_PUBLIC_API_URL",
  "http://localhost:8000",
);
// Public media (project covers/gallery): Cloudinary/S3 in production, the API in dev.
const media = process.env.NEXT_PUBLIC_MEDIA_URL
  ? originOf(process.env.NEXT_PUBLIC_MEDIA_URL, "NEXT_PUBLIC_MEDIA_URL", api.origin)
  : api;
const TURNSTILE = "https://challenges.cloudflare.com";
const secureOnly = api.protocol === "https:";

// Only the origins the site actually uses. Fonts are self-hosted by next/font.
// 'unsafe-inline' for scripts is required by Next's inline hydration scripts
// unless every page is rendered dynamically with a nonce (README, "CSP").
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline' ${TURNSTILE}${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  `img-src 'self' data: blob: ${api.origin} ${media.origin}`,
  "font-src 'self'",
  `connect-src 'self' ${api.origin} ${TURNSTILE}${isDev ? " ws://localhost:3000" : ""}`,
  `frame-src ${TURNSTILE}`,
  "worker-src 'self' blob:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
  ...(secureOnly && !isDev ? ["upgrade-insecure-requests"] : []),
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
  images: { remotePatterns: [remote(api), remote(media)], formats: ["image/avif", "image/webp"] },
  // Linting runs as its own CI step with the project's flat config.
  eslint: { ignoreDuringBuilds: true },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
