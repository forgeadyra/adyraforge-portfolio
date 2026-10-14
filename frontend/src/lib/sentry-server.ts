import * as Sentry from "@sentry/nextjs";

import { DATA_COLLECTION, scrubBreadcrumb, scrubEvent } from "@/lib/sentry-scrub";

// Server error monitoring for the Next.js Node runtime only (imported from
// instrumentation.ts behind a NEXT_RUNTIME check, so the edge bundle never contains it).
// Off unless NEXT_PUBLIC_SENTRY_DSN is set. No cookies, headers, bodies, tokens or users.
const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;

export function initServerSentry(): void {
  if (!dsn) return;
  Sentry.init({
    dsn,
    environment: process.env.NODE_ENV,
    dataCollection: DATA_COLLECTION,
    tracesSampleRate: 0,
    beforeSend: (event) => scrubEvent(event),
    beforeBreadcrumb: (crumb) => scrubBreadcrumb(crumb),
  });
}

export function captureServerRequestError(
  ...args: Parameters<typeof Sentry.captureRequestError>
): void {
  if (dsn) Sentry.captureRequestError(...args);
}
