import { describe, expect, it } from "vitest";

import { wakeFetch } from "./wake-fetch";

/** A fake clock: sleeping advances time instantly. */
function clock() {
  let t = 0;
  const slept: number[] = [];
  return {
    now: () => t,
    sleep: async (ms: number) => {
      slept.push(ms);
      t += ms;
    },
    slept,
  };
}

function fakeFetch(...outcomes: (number | Error)[]) {
  const calls: string[] = [];
  const impl = (async (url: string) => {
    calls.push(url);
    const next = outcomes.shift() ?? 200;
    if (next instanceof Error) throw next;
    return new Response(next === 200 ? "[]" : "", { status: next });
  }) as unknown as typeof fetch;
  return { impl, calls };
}

const BUILD = { budgetMs: 90_000, attemptTimeoutMs: 70_000 };

describe("wakeFetch", () => {
  it("waits for a sleeping API: retries 503 and network errors, then succeeds", async () => {
    const c = clock();
    const f = fakeFetch(new TypeError("fetch failed"), 503, 502, 200);
    const res = await wakeFetch("https://api/x", {}, { ...BUILD, fetchImpl: f.impl, ...c });
    expect(res.status).toBe(200);
    expect(f.calls).toHaveLength(4);
    expect(c.slept).toEqual([2_000, 4_000, 8_000]); // exponential backoff
  });

  it("never retries a 404: a wrong URL still fails fast", async () => {
    const c = clock();
    const f = fakeFetch(404);
    const res = await wakeFetch("https://api/x", {}, { ...BUILD, fetchImpl: f.impl, ...c });
    expect(res.status).toBe(404);
    expect(f.calls).toHaveLength(1);
    expect(c.slept).toEqual([]);
  });

  it("gives up after about 90 seconds and reports the last failure", async () => {
    const c = clock();
    const f = fakeFetch(...Array.from({ length: 50 }, () => new TypeError("fetch failed")));
    await expect(
      wakeFetch("https://api/x", {}, { ...BUILD, fetchImpl: f.impl, ...c }),
    ).rejects.toThrow("fetch failed");
    const waited = c.slept.reduce((a, b) => a + b, 0);
    expect(waited).toBeLessThanOrEqual(90_000);
    expect(waited).toBeGreaterThanOrEqual(60_000); // long enough for a ~60 s cold start
  });

  it("returns a persistent 503 once the budget is spent", async () => {
    const c = clock();
    const f = fakeFetch(...Array.from({ length: 50 }, () => 503));
    const res = await wakeFetch("https://api/x", {}, { ...BUILD, fetchImpl: f.impl, ...c });
    expect(res.status).toBe(503);
  });

  it("makes a single attempt at runtime (budget 0)", async () => {
    const c = clock();
    const f = fakeFetch(503);
    const res = await wakeFetch(
      "https://api/x",
      {},
      { budgetMs: 0, attemptTimeoutMs: 8_000, fetchImpl: f.impl, ...c },
    );
    expect(res.status).toBe(503);
    expect(f.calls).toHaveLength(1);
  });
});
