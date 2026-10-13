import { describe, expect, it, vi } from "vitest";

import { ApiError, createApiClient } from "./api";

type Call = { url: string; init: RequestInit };

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function setup(responder: (call: Call) => Response) {
  const calls: Call[] = [];
  const fetchImpl = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const call = { url: String(url), init: init ?? {} };
    calls.push(call);
    return responder(call);
  }) as unknown as typeof fetch;
  const client = createApiClient({ baseUrl: "https://api.example.test/", fetchImpl });
  return { client, calls };
}

function first<T>(items: T[]): T {
  const [item] = items;
  if (item === undefined) throw new Error("expected at least one item");
  return item;
}

const header = (c: Call, name: string) => (c.init.headers as Record<string, string>)[name];

describe("api client", () => {
  it("sends cookies and no CSRF header on GET", async () => {
    const { client, calls } = setup(() => json(200, { ok: true }));
    await expect(client.get("/api/auth/me/")).resolves.toEqual({ ok: true });
    expect(calls).toHaveLength(1);
    expect(first(calls).url).toBe("https://api.example.test/api/auth/me/");
    expect(first(calls).init.credentials).toBe("include");
    expect(header(first(calls), "X-CSRFToken")).toBeUndefined();
  });

  it("fetches the CSRF token once and sends it on unsafe methods", async () => {
    const { client, calls } = setup(({ url }) =>
      url.endsWith("/api/auth/csrf/") ? json(200, { csrfToken: "tok-1" }) : json(201, { id: 1 }),
    );
    await client.post("/api/things/", { name: "a" });
    await client.patch("/api/things/1/", { name: "b" });

    const csrfCalls = calls.filter((c) => c.url.endsWith("/api/auth/csrf/"));
    expect(csrfCalls).toHaveLength(1);
    expect(first(csrfCalls).init.credentials).toBe("include");

    const writes = calls.filter((c) => !c.url.endsWith("/api/auth/csrf/"));
    for (const w of writes) {
      expect(header(w, "X-CSRFToken")).toBe("tok-1");
      expect(header(w, "Content-Type")).toBe("application/json");
      expect(w.init.credentials).toBe("include");
    }
    expect(first(writes).init.body).toBe(JSON.stringify({ name: "a" }));
  });

  it("refreshes a rejected CSRF token and retries once", async () => {
    let token = 0;
    let attempts = 0;
    const { client } = setup(({ url }) => {
      if (url.endsWith("/api/auth/csrf/")) return json(200, { csrfToken: `tok-${++token}` });
      attempts += 1;
      return attempts === 1
        ? json(403, { detail: "CSRF Failed: CSRF token incorrect." })
        : json(200, { ok: true });
    });
    await expect(client.post("/api/x/")).resolves.toEqual({ ok: true });
    expect(token).toBe(2);
  });

  it("does not retry forever on repeated CSRF failures", async () => {
    const { client } = setup(({ url }) =>
      url.endsWith("/api/auth/csrf/")
        ? json(200, { csrfToken: "t" })
        : json(403, { detail: "CSRF Failed" }),
    );
    await expect(client.post("/api/x/")).rejects.toMatchObject({ status: 403 });
  });

  it("raises ApiError with the server's detail", async () => {
    const { client } = setup(() => json(404, { detail: "Not found." }));
    const err = await client.get("/api/missing/").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 404, detail: "Not found." });
  });

  it("refuses absolute or protocol-relative URLs so cookies never leave the API", async () => {
    const { client, calls } = setup(() => json(200, {}));
    await expect(client.get("https://evil.example/steal")).rejects.toThrow(/relative/);
    await expect(client.get("//evil.example/steal")).rejects.toThrow(/relative/);
    expect(calls).toHaveLength(0);
  });
});
