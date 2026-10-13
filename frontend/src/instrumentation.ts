import type { captureRequestError } from "@sentry/nextjs";

// Next.js instrumentation hooks. The NEXT_RUNTIME test is a build-time constant, so
// webpack drops the Sentry import from the edge (middleware) bundle entirely.
export async function register(): Promise<void> {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    const { initServerSentry } = await import("@/lib/sentry-server");
    initServerSentry();
  }
}

export async function onRequestError(
  ...args: Parameters<typeof captureRequestError>
): Promise<void> {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    const { captureServerRequestError } = await import("@/lib/sentry-server");
    captureServerRequestError(...args);
  }
}
