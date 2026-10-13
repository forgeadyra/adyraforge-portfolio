"use client";

import { useEffect, useRef, type ReactNode } from "react";

import { loadGsap, prefersReducedMotion } from "@/lib/motion";

/**
 * Fades/slides children in as they scroll into view (GSAP ScrollTrigger).
 * Content is fully visible without JS and for reduced-motion users.
 */
export function Reveal({
  children,
  as: Tag = "div",
  className,
  stagger = 0.08,
}: {
  children: ReactNode;
  as?: "div" | "ul" | "ol" | "section";
  className?: string;
  stagger?: number;
}) {
  const ref = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || prefersReducedMotion()) return;
    let revert: (() => void) | undefined;
    let cancelled = false;

    void loadGsap().then(({ gsap }) => {
      if (cancelled) return;
      const ctx = gsap.context(() => {
        gsap.from(el.children, {
          opacity: 0,
          y: 24,
          duration: 0.7,
          ease: "power3.out",
          stagger,
          scrollTrigger: { trigger: el, start: "top 85%", once: true },
        });
      }, el);
      revert = () => ctx.revert();
    });

    return () => {
      cancelled = true;
      revert?.();
    };
  }, [stagger]);

  return (
    <Tag ref={ref as never} className={className}>
      {children}
    </Tag>
  );
}
