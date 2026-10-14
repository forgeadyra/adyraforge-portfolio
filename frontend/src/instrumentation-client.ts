import { afterLoadIdle } from "@/lib/motion";
import { DATA_COLLECTION, scrubBreadcrumb, scrubEvent } from "@/lib/sentry-scrub";

// Browser error monitoring. Off unless NEXT_PUBLIC_SENTRY_DSN is set (a DSN is a
// public identifier, not a secret). The SDK is fetched after load + idle, so it adds
// nothing to the initial bundle or LCP; errors before that moment are not reported.
const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;

if (dsn) {
  void afterLoadIdle()
    .then(() => import("@sentry/nextjs"))
    .then((Sentry) => {
      Sentry.init({
        dsn,
        tunnel: "/monitoring", // same origin: CSP stays connect-src 'self'
        environment: process.env.NODE_ENV,
        dataCollection: DATA_COLLECTION, // nothing personal (Sentry 11 defaults collect it)
        tracesSampleRate: 0, // errors only
        beforeSend: (event) => scrubEvent(event),
        beforeBreadcrumb: (crumb) => scrubBreadcrumb(crumb),
      });
    })
    .catch(() => undefined); // monitoring must never break the page
}
