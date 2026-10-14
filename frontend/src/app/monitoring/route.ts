import { parseDsn } from "@/lib/sentry-scrub";

/**
 * Same-origin Sentry tunnel: the browser posts envelopes here, so the CSP stays
 * connect-src 'self' and ad blockers don't drop error reports. Only envelopes for
 * OUR project are forwarded (an open tunnel would let anyone relay through us).
 */
const MAX_BYTES = 256 * 1024;

export const dynamic = "force-dynamic";

export async function POST(request: Request): Promise<Response> {
  const target = parseDsn(process.env.NEXT_PUBLIC_SENTRY_DSN);
  if (!target) return new Response(null, { status: 404 });

  const length = Number(request.headers.get("content-length") ?? "0");
  if (length > MAX_BYTES) return new Response(null, { status: 413 });
  const body = await request.text();
  if (body.length > MAX_BYTES) return new Response(null, { status: 413 });

  // An envelope's first line is a JSON header naming the DSN it is meant for.
  const newline = body.indexOf("\n");
  let header: { dsn?: string };
  try {
    header = JSON.parse(newline === -1 ? body : body.slice(0, newline)) as { dsn?: string };
  } catch {
    return new Response(null, { status: 400 });
  }
  const sent = parseDsn(header.dsn);
  if (!sent || sent.host !== target.host || sent.projectId !== target.projectId) {
    return new Response(null, { status: 403 });
  }

  const upstream = await fetch(`https://${target.host}/api/${target.projectId}/envelope/`, {
    method: "POST",
    headers: { "Content-Type": "application/x-sentry-envelope" },
    body,
  }).catch(() => null);
  return new Response(null, { status: upstream?.status ?? 502 });
}
