import { describe, expect, it } from "vitest";

import { DATA_COLLECTION, parseDsn, scrubBreadcrumb, scrubEvent, scrubUrl } from "./sentry-scrub";

describe("scrubUrl", () => {
  it("removes tokens from invite, reset and download URLs and query strings", () => {
    expect(scrubUrl("https://adyraforge.netlify.app/invite/abc.DEF-123")).toBe(
      "https://adyraforge.netlify.app/invite/[Filtered]",
    );
    expect(scrubUrl("https://adyraforge.netlify.app/reset-password/MQ/c4a-9f2e1?x=1")).toBe(
      "https://adyraforge.netlify.app/reset-password/[Filtered]/[Filtered]?[Filtered]",
    );
    expect(scrubUrl("https://adyraforge.netlify.app/api/files/eyJ.sig/")).toBe(
      "https://adyraforge.netlify.app/api/files/[Filtered]/",
    );
    expect(scrubUrl("https://adyraforge.netlify.app/work/medicare-plus")).toBe(
      "https://adyraforge.netlify.app/work/medicare-plus",
    );
  });
});

describe("scrubEvent", () => {
  it("drops cookies, headers, bodies and user, and scrubs breadcrumbs", () => {
    const event = {
      request: {
        url: "https://adyraforge.netlify.app/invite/secret-token",
        cookies: { sessionid: "s3cr3t" },
        headers: { Cookie: "sessionid=s3cr3t" },
        data: { password: "hunter2hunter2" },
        query_string: "token=abc",
      },
      user: { email: "a@example.com", ip_address: "203.0.113.9" },
      breadcrumbs: [
        { category: "console", message: "password=hunter2hunter2" },
        { category: "fetch", data: { url: "/api/files/eyJ.sig/" } },
      ],
    };
    const flat = JSON.stringify(scrubEvent(event));
    for (const secret of [
      "s3cr3t",
      "hunter2",
      "a@example.com",
      "203.0.113.9",
      "secret-token",
      "eyJ",
    ]) {
      expect(flat).not.toContain(secret);
    }
  });

  it("keeps breadcrumbs without data untouched", () => {
    expect(scrubBreadcrumb({ category: "navigation" })).toEqual({ category: "navigation" });
  });
});

describe("parseDsn", () => {
  it("accepts a real-shaped DSN and rejects anything else", () => {
    expect(parseDsn("https://abc123@o42.ingest.sentry.io/4507")).toEqual({
      host: "o42.ingest.sentry.io",
      projectId: "4507",
    });
    expect(parseDsn(undefined)).toBeNull();
    expect(parseDsn("http://abc@o42.ingest.sentry.io/1")).toBeNull();
    expect(parseDsn("https://o42.ingest.sentry.io/1")).toBeNull();
    expect(parseDsn("not a url")).toBeNull();
  });
});

describe("DATA_COLLECTION", () => {
  it("turns every collection category off", () => {
    const values = JSON.stringify(DATA_COLLECTION);
    expect(values).not.toContain("true");
    expect(DATA_COLLECTION.httpBodies).toEqual([]);
    for (const key of [
      "userInfo",
      "cookies",
      "httpHeaders",
      "urlQueryParams",
      "stackFrameVariables",
    ]) {
      expect(DATA_COLLECTION).toHaveProperty(key, false);
    }
  });
});
