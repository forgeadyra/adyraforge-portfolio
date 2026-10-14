/**
 * fetch() that waits for a sleeping API (Render's free instance spins down after 15
 * idle minutes and takes about a minute to wake).
 *
 * Network errors and 502/503/504 are retried with exponential backoff until the
 * budget is spent; any other status (including 404) returns at once, so callers
 * still fail fast on a wrong URL or missing content.
 */

export const RETRYABLE_STATUSES = new Set([502, 503, 504]);

export interface WakeOptions {
  /** Total time allowed for retries, in ms. 0 = a single attempt. */
  budgetMs: number;
  /** Per-attempt timeout, in ms. */
  attemptTimeoutMs: number;
  fetchImpl?: typeof fetch;
  sleep?: (ms: number) => Promise<void>;
  now?: () => number;
}

const realSleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

export async function wakeFetch(
  url: string,
  init: RequestInit,
  { budgetMs, attemptTimeoutMs, fetchImpl, sleep = realSleep, now = Date.now }: WakeOptions,
): Promise<Response> {
  const doFetch = fetchImpl ?? fetch;
  const deadline = now() + budgetMs;
  let delay = 2_000;
  for (;;) {
    let failure: unknown = null;
    try {
      const res = await doFetch(url, { ...init, signal: AbortSignal.timeout(attemptTimeoutMs) });
      if (!RETRYABLE_STATUSES.has(res.status)) return res;
      if (now() + delay > deadline) return res; // out of budget: let the caller report it
    } catch (err) {
      failure = err;
    }
    if (failure !== null && now() + delay > deadline) throw failure;
    await sleep(delay);
    delay = Math.min(delay * 2, 16_000);
  }
}
