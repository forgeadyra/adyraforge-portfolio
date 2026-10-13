import Link from "next/link";

import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader } from "@/components/site/SiteHeader";

export const metadata = { title: "Page not found", robots: { index: false } };

export default function NotFound() {
  return (
    <>
      <SiteHeader />
      <main id="main" className="mx-auto max-w-3xl px-5 py-28 text-center">
        <p className="font-display text-7xl font-bold text-gold">404</p>
        <h1 className="mt-4 font-display text-3xl font-bold">This page isn&apos;t in the forge</h1>
        <p className="mt-3 text-ink/80">It may have moved, or the link may be mistyped.</p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link href="/" className="btn-gold">
            Go home
          </Link>
          <Link href="/work" className="btn-ghost">
            See the work
          </Link>
        </div>
      </main>
      <SiteFooter />
    </>
  );
}
