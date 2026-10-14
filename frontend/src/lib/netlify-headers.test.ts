import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { afterEach, describe, expect, it, vi } from "vitest";

// netlify.toml repeats the security headers from next.config.ts so Netlify's edge
// serves them on every response. This keeps the two copies identical.
function netlifyHeaders(): Record<string, string> {
  const toml = readFileSync(
    fileURLToPath(new URL("../../../netlify.toml", import.meta.url)),
    "utf8",
  );
  const block = toml.split("[headers.values]")[1]?.split(/\n\s*\n/)[0] ?? "";
  return Object.fromEntries(
    [...block.matchAll(/^\s*([A-Za-z-]+)\s*=\s*"(.*)"\s*$/gm)].map((m) => [m[1], m[2]]),
  );
}

describe("netlify.toml security headers", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("match next.config.ts production headers exactly", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("API_INTERNAL_URL", "https://adyraforge-api.onrender.com");
    vi.stubEnv("NEXT_PUBLIC_SITE_URL", "https://adyraforge.netlify.app");
    vi.stubEnv("NEXT_PUBLIC_MEDIA_URL", "https://adyraforge-media.s3.us-west-004.backblazeb2.com");
    vi.resetModules();
    const { default: config } = await import("../../next.config");
    expect(config.headers).toBeTypeOf("function");
    const [rule] = await (config.headers as NonNullable<typeof config.headers>)();
    const fromNext = Object.fromEntries((rule?.headers ?? []).map((h) => [h.key, h.value]));

    expect(netlifyHeaders()).toEqual(fromNext);
    expect(fromNext["Content-Security-Policy"]).toContain("upgrade-insecure-requests");
  });
});

function toml(): string {
  return readFileSync(fileURLToPath(new URL("../../../netlify.toml", import.meta.url)), "utf8");
}

/** The [[redirects]] blocks as key/value maps (enough TOML for this file). */
function redirects(): Record<string, string>[] {
  return toml()
    .split("[[redirects]]")
    .slice(1)
    .map((block) => block.split(/\n\s*\n|\n\[/)[0] ?? "")
    .map((block) =>
      Object.fromEntries(
        [...block.matchAll(/^\s*(\w+)\s*=\s*"?([^"\n]*)"?\s*$/gm)].map((m) => [m[1], m[2]]),
      ),
    );
}

describe("netlify.toml build", () => {
  it("never enables the offline build that renders empty pages", () => {
    // With this unset, an unreachable API, a 404 list endpoint or an empty project
    // list fails `next build` (src/lib/content.ts) instead of shipping an empty site.
    expect(toml()).not.toContain("NEXT_BUILD_WITHOUT_API");
  });

  it("names no site domain: moving to a custom domain is env-only", () => {
    expect(toml()).not.toMatch(/adyraforge\.com|NEXT_PUBLIC_SITE_URL\s*=|API_INTERNAL_URL\s*=/);
  });

  it("proxies /api/* to Render, forced and signed, so the browser stays same-origin", () => {
    const api = redirects().find((r) => r.from === "/api/*");
    expect(api).toBeDefined();
    expect(api?.to).toMatch(/^https:\/\/[a-z0-9-]+\.onrender\.com\/api\/:splat$/);
    expect(api?.status).toBe("200");
    expect(api?.force).toBe("true");
    // Without the signature Django can't tell Netlify's client-IP header from a forged one.
    expect(api?.signed).toBe("NETLIFY_PROXY_SIGNING_SECRET");
  });
});
