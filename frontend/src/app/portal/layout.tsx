import type { Metadata } from "next";

import { PortalNav } from "@/components/PortalNav";

export const metadata: Metadata = {
  title: "Client portal — AdyraForge",
  robots: { index: false, follow: false },
};

// Access is checked by middleware (UX) and enforced by the API on every request.
export default function PortalLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen">
      <PortalNav />
      <main id="main" className="mx-auto max-w-5xl px-4 py-10">
        {children}
      </main>
    </div>
  );
}
