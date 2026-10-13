import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV === "development";

function apiOrigin(): string {
  const raw = process.env.NEXT_PUBLIC_API_URL;
  if (!raw) {
    if (isDev) return "http://localhost:8000";
    throw new Error("NEXT_PUBLIC_API_URL must be set for production builds.");
  }
  const url = new URL(raw);
  if (!isDev && url.protocol !== "https:") {
    throw new Error("NEXT_PUBLIC_API_URL must use https:// outside development.");
  }
  return url.origin;
}

// Only the origins the site actually uses. Fonts are self-hosted by next/font,
// so no Google domains are needed. 'unsafe-inline' for scripts is required by
// Next's inline hydration scripts unless every page is rendered dynamically
// with a per-request nonce (see README, "CSP").
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self'",
  `connect-src 'self' ${apiOrigin()}${isDev ? " ws://localhost:3000" : ""}`,
  "worker-src 'self' blob:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
  ...(isDev ? [] : ["upgrade-insecure-requests"]),
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

const nextConfig: NextConfig = {
  poweredByHeader: false,
  productionBrowserSourceMaps: false,
  reactStrictMode: true,
  // Linting runs as its own CI step with the project's flat config.
  eslint: { ignoreDuringBuilds: true },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
