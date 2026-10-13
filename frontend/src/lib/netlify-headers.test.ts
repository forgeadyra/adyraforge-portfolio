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
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.adyraforge.com");
    vi.stubEnv("NEXT_PUBLIC_MEDIA_URL", "");
    vi.resetModules();
    const { default: config } = await import("../../next.config");
    expect(config.headers).toBeTypeOf("function");
    const [rule] = await (config.headers as NonNullable<typeof config.headers>)();
    const fromNext = Object.fromEntries((rule?.headers ?? []).map((h) => [h.key, h.value]));

    expect(netlifyHeaders()).toEqual(fromNext);
    expect(fromNext["Content-Security-Policy"]).toContain("upgrade-insecure-requests");
  });
});
