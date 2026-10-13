"use client";

import { useEffect, useState, type ComponentType, type ReactNode } from "react";

import { afterLoadIdle } from "@/lib/motion";

type Transition = ComponentType<{ children: ReactNode }>;

// Framer Motion is never part of the first page load. It's fetched after load +
// idle, and only client-side navigations (when it's already cached) animate.
// The first paint is therefore plain SSR HTML: nothing waits on JS for LCP.
let PageTransition: Transition | null = null;
let preload: Promise<void> | null = null;

function preloadTransition() {
  preload ??= afterLoadIdle()
    .then(() => import("@/components/site/PageTransition"))
    .then((mod) => {
      PageTransition = mod.default;
    });
}

export default function Template({ children }: { children: ReactNode }) {
  // Captured at mount: a template mounted after preload is a navigation.
  const [Motion] = useState<Transition | null>(() => PageTransition);

  useEffect(() => {
    preloadTransition();
  }, []);

  return Motion ? <Motion>{children}</Motion> : <>{children}</>;
}
