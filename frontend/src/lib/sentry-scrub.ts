/**
 * PII / secret scrubbing for Sentry events and breadcrumbs (CLAUDE.md rule 14).
 * Invite, password-reset and signed-download URLs carry bearer tokens in the path.
 */

const TOKEN_PATHS: [RegExp, string][] = [
  [/\/invite\/[^/?#]+/g, "/invite/[Filtered]"],
  [/\/reset-password\/[^/?#]+\/[^/?#]+/g, "/reset-password/[Filtered]/[Filtered]"],
  [/\/api\/files\/[^/?#]+/g, "/api/files/[Filtered]"],
];

export function scrubUrl(url: string): string {
  let out = url.replace(/\?.*$/, (q) => (q.length > 1 ? "?[Filtered]" : q));
  for (const [pattern, replacement] of TOKEN_PATHS) out = out.replace(pattern, replacement);
  return out;
}

type Json = Record<string, unknown>;

/** beforeSend: drop cookies, headers, bodies, user identity; scrub every URL. */
export function scrubEvent<T extends object>(event: T): T {
  const e = event as unknown as Json;
  const request = e.request as Json | undefined;
  if (request) {
    delete request.cookies;
    delete request.data;
    delete request.headers;
    delete request.query_string;
    if (typeof request.url === "string") request.url = scrubUrl(request.url);
  }
  delete e.user;
  const breadcrumbs = e.breadcrumbs as Json[] | undefined;
  if (Array.isArray(breadcrumbs)) e.breadcrumbs = breadcrumbs.map((b) => scrubBreadcrumb(b));
  return event;
}

/** beforeBreadcrumb: keep navigation/fetch shape, never token-bearing URLs or console text. */
export function scrubBreadcrumb<T extends object>(crumb: T): T {
  const c = crumb as unknown as Json;
  if (c.category === "console") c.message = "[Filtered]";
  const data = c.data as Json | undefined;
  if (data) {
    for (const key of ["url", "from", "to"]) {
      if (typeof data[key] === "string") data[key] = scrubUrl(data[key] as string);
    }
  }
  return crumb;
}

/** Parse "https://<key>@<host>/<projectId>" into the pieces the tunnel checks. */
export function parseDsn(dsn: string | undefined): { host: string; projectId: string } | null {
  if (!dsn) return null;
  try {
    const u = new URL(dsn);
    const projectId = u.pathname.replace(/^\//, "");
    if (u.protocol !== "https:" || !u.username || !/^\d+$/.test(projectId)) return null;
    return { host: u.host, projectId };
  } catch {
    return null;
  }
}

/**
 * Sentry 11 collects user info, cookies, headers, bodies, query params and stack-frame
 * variables BY DEFAULT. Everything off; the scrubbers above are a second layer.
 */
export const DATA_COLLECTION = {
  userInfo: false,
  cookies: false,
  httpHeaders: false,
  httpBodies: [],
  urlQueryParams: false,
  graphQL: { document: false, variables: false },
  genAI: { inputs: false, outputs: false },
  databaseQueryData: false,
  queues: false,
  stackFrameVariables: false,
};
