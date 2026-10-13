"use client";

import { useEffect, useRef } from "react";

import { loadGsap, prefersReducedMotion } from "@/lib/motion";

const STEPS = [
  {
    title: "Discover",
    body: "A short call and the project planner pin down your goals, scope, budget and timeline.",
  },
  {
    title: "Design",
    body: "Wireframes and a visual direction you approve before any code is written.",
  },
  {
    title: "Build",
    body: "Development in small, reviewable steps. Progress, files and invoices live in your client portal.",
  },
  {
    title: "Launch",
    body: "Performance and accessibility checks, then go-live and handover.",
  },
];

/** Four-step process; the gold line fills as you scroll (scrubbed ScrollTrigger). */
export function ProcessTimeline() {
  const root = useRef<HTMLOListElement>(null);
  const line = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = root.current;
    if (!el || !line.current || prefersReducedMotion()) return;
    let revert: (() => void) | undefined;
    let cancelled = false;

    void loadGsap().then(({ gsap }) => {
      if (cancelled) return;
      const ctx = gsap.context(() => {
        gsap.fromTo(
          line.current,
          { scaleY: 0 },
          {
            scaleY: 1,
            ease: "none",
            transformOrigin: "top",
            scrollTrigger: { trigger: el, start: "top 70%", end: "bottom 60%", scrub: true },
          },
        );
        el.querySelectorAll("li").forEach((step) => {
          gsap.from(step, {
            opacity: 0,
            x: 16,
            duration: 0.6,
            scrollTrigger: { trigger: step, start: "top 85%", once: true },
          });
        });
      }, el);
      revert = () => ctx.revert();
    });

    return () => {
      cancelled = true;
      revert?.();
    };
  }, []);

  return (
    <div className="relative mt-12">
      <div aria-hidden="true" className="absolute bottom-2 left-[15px] top-2 w-px bg-ink/10" />
      <div
        ref={line}
        aria-hidden="true"
        className="absolute bottom-2 left-[15px] top-2 w-px origin-top bg-gold"
      />
      <ol ref={root} className="space-y-10">
        {STEPS.map((step, i) => (
          <li key={step.title} className="relative pl-12">
            <span
              aria-hidden="true"
              className="absolute left-0 top-0 flex h-8 w-8 items-center justify-center rounded-full border border-gold/60 bg-base font-display text-sm text-gold"
            >
              {i + 1}
            </span>
            <h3 className="font-display text-xl font-bold">
              <span className="sr-only">Step {i + 1}: </span>
              {step.title}
            </h3>
            <p className="mt-1 max-w-xl text-ink/80">{step.body}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}
