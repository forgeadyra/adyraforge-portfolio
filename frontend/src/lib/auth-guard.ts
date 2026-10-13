/**
 * Route-guard decisions for the portal. UX only: the API enforces every
 * permission itself, so nothing here is a security boundary.
 */

export type GuardResult = { kind: "allow" } | { kind: "redirect"; to: string };

/** Only same-site portal paths may be used as a post-login redirect target. */
export function safeNext(next: string | null | undefined): string {
  if (!next) return "/portal";
  // Reject absolute URLs, protocol-relative "//evil", backslash tricks and
  // anything outside the portal: no open redirects.
  if (!next.startsWith("/portal") || next.startsWith("//") || /[\\\s]/.test(next)) {
    return "/portal";
  }
  return next;
}

export function decide(
  meStatus: number | "error",
  role: string | undefined,
  path: string,
): GuardResult {
  if (meStatus === 200 && role === "client") return { kind: "allow" };
  if (meStatus === 200) return { kind: "redirect", to: "/" }; // staff use the admin, not the portal
  // 401/403, API down, timeout: fail closed to the login page.
  return { kind: "redirect", to: `/login?next=${encodeURIComponent(safeNext(path))}` };
}
