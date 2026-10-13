import type { Metadata } from "next";

// The URL carries a one-time token: never leak it via Referer, never index it.
export const metadata: Metadata = {
  title: "Activate your portal — AdyraForge",
  referrer: "no-referrer",
  robots: { index: false, follow: false },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
