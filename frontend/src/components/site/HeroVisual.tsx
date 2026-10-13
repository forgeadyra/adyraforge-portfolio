"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";

import { afterLoadIdle } from "@/lib/motion";

import { HeroPoster } from "./HeroPoster";

const HeroScene = dynamic(() => import("./HeroScene"), { ssr: false });

type NavigatorExtras = Navigator & {
  deviceMemory?: number;
  connection?: { saveData?: boolean };
};

/** Decide once, on the client, whether this device gets the 3D scene. */
function canRun3d(): boolean {
  const mq = (q: string) => window.matchMedia(q).matches;
  if (mq("(prefers-reduced-motion: reduce)")) return false;
  // Desktop-class only: phones keep the poster (performance budget, battery).
  if (!mq("(pointer: fine) and (min-width: 1024px)")) return false;
  const nav = navigator as NavigatorExtras;
  if ((nav.hardwareConcurrency ?? 4) <= 2 || (nav.deviceMemory ?? 8) <= 2) return false;
  if (nav.connection?.saveData) return false;
  try {
    return Boolean(document.createElement("canvas").getContext("webgl2"));
  } catch {
    return false;
  }
}

export function HeroVisual() {
  const box = useRef<HTMLDivElement>(null);
  const [load, setLoad] = useState(false);
  const [ready, setReady] = useState(false);
  const [onScreen, setOnScreen] = useState(true);
  const [tabVisible, setTabVisible] = useState(true);

  // Lazy-load after the page has painted and gone idle (never before LCP).
  useEffect(() => {
    if (!canRun3d()) return;
    let cancelled = false;
    // After load + idle, never before LCP. (Staging three/fiber/postprocessing
    // imports separately was measured: no shorter long task, +117 KB because a
    // namespace import of "three" defeats tree-shaking.)
    void afterLoadIdle().then(() => {
      if (!cancelled) setLoad(true);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // Pause rendering when scrolled away or the tab is hidden.
  useEffect(() => {
    const el = box.current;
    if (!el || !load) return;
    const io = new IntersectionObserver(([entry]) => setOnScreen(Boolean(entry?.isIntersecting)));
    io.observe(el);
    const vis = () => setTabVisible(document.visibilityState === "visible");
    document.addEventListener("visibilitychange", vis);
    return () => {
      io.disconnect();
      document.removeEventListener("visibilitychange", vis);
    };
  }, [load]);

  return (
    <div ref={box} className="relative aspect-square w-full">
      <div
        className={`absolute inset-0 transition-opacity duration-700 ${ready ? "opacity-0" : "opacity-100"}`}
      >
        <HeroPoster />
      </div>
      {load && (
        <div
          className={`absolute inset-0 transition-opacity duration-700 ${ready ? "opacity-100" : "opacity-0"}`}
        >
          <HeroScene active={onScreen && tabVisible} onReady={() => setReady(true)} />
        </div>
      )}
    </div>
  );
}
