"use client";

/** Shared, lazily loaded GSAP + ScrollTrigger (never part of the initial bundle). */

export function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

let idlePromise: Promise<void> | null = null;

/** Resolves after the load event plus an idle slot: nothing decorative competes with LCP. */
export function afterLoadIdle(): Promise<void> {
  idlePromise ??= new Promise((resolve) => {
    const idle = () =>
      typeof window.requestIdleCallback === "function"
        ? window.requestIdleCallback(() => resolve(), { timeout: 3000 })
        : window.setTimeout(resolve, 1500);
    if (document.readyState === "complete") idle();
    else window.addEventListener("load", idle, { once: true });
  });
  return idlePromise;
}

let gsapPromise: Promise<{
  gsap: typeof import("gsap").gsap;
  ScrollTrigger: typeof import("gsap/ScrollTrigger").ScrollTrigger;
}> | null = null;

export function loadGsap() {
  gsapPromise ??= afterLoadIdle()
    .then(() => Promise.all([import("gsap"), import("gsap/ScrollTrigger")]))
    .then(([{ gsap }, { ScrollTrigger }]) => {
      gsap.registerPlugin(ScrollTrigger);
      return { gsap, ScrollTrigger };
    });
  return gsapPromise;
}
