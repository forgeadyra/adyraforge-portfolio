"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

import { afterLoadIdle, loadGsap, prefersReducedMotion } from "@/lib/motion";

type LenisInstance = InstanceType<typeof import("lenis").default>;

/** Lenis smooth scrolling, driven by GSAP's ticker so ScrollTrigger stays in sync. */
export function SmoothScroll() {
  const lenisRef = useRef<LenisInstance | null>(null);
  const pathname = usePathname();

  useEffect(() => {
    if (prefersReducedMotion()) return;
    let disposed = false;
    let tick: ((time: number) => void) | null = null;

    void afterLoadIdle()
      .then(() => Promise.all([import("lenis"), loadGsap()]))
      .then(([{ default: Lenis }, { gsap, ScrollTrigger }]) => {
        if (disposed) return;
        const lenis = new Lenis({ lerp: 0.12 });
        lenis.on("scroll", ScrollTrigger.update);
        tick = (time: number) => lenis.raf(time * 1000);
        gsap.ticker.add(tick);
        gsap.ticker.lagSmoothing(0);
        lenisRef.current = lenis;
      });

    return () => {
      disposed = true;
      void loadGsap().then(({ gsap }) => tick && gsap.ticker.remove(tick));
      lenisRef.current?.destroy();
      lenisRef.current = null;
    };
  }, []);

  // New page starts at the top.
  useEffect(() => {
    lenisRef.current?.scrollTo(0, { immediate: true });
  }, [pathname]);

  return null;
}
