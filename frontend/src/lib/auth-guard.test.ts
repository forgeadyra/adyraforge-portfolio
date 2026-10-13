import { describe, expect, it } from "vitest";

import { decide, safeNext } from "./auth-guard";

describe("safeNext", () => {
  it.each([
    ["/portal/projects/3", "/portal/projects/3"],
    ["/portal?tab=files", "/portal?tab=files"],
    [null, "/portal"],
    ["", "/portal"],
    ["https://evil.example/portal", "/portal"],
    ["//evil.example/portal", "/portal"],
    ["/\\evil.example", "/portal"],
    ["/portal\\@evil", "/portal"],
    ["/admin", "/portal"],
    ["javascript:alert(1)", "/portal"],
  ])("%s -> %s", (input, expected) => {
    expect(safeNext(input)).toBe(expected);
  });
});

describe("decide", () => {
  it("lets signed-in clients through", () => {
    expect(decide(200, "client", "/portal")).toEqual({ kind: "allow" });
  });

  it.each([401, 403, 500, "error" as const])("sends %s to login with a safe next", (status) => {
    expect(decide(status, undefined, "/portal/projects/7")).toEqual({
      kind: "redirect",
      to: "/login?next=%2Fportal%2Fprojects%2F7",
    });
  });

  it("does not trust a role claim without a 200", () => {
    expect(decide(403, "client", "/portal").kind).toBe("redirect");
  });

  it("keeps staff out of the client portal", () => {
    expect(decide(200, "admin", "/portal")).toEqual({ kind: "redirect", to: "/" });
  });
});
