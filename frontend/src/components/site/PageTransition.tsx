"use client";

import { LazyMotion, domAnimation, m, useReducedMotion } from "framer-motion";

/** Framer Motion enter transition for client-side navigations. */
export default function PageTransition({ children }: { children: React.ReactNode }) {
  const reduce = useReducedMotion();
  return (
    <LazyMotion features={domAnimation} strict>
      <m.div
        initial={reduce ? false : { opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: "easeOut" }}
      >
        {children}
      </m.div>
    </LazyMotion>
  );
}
