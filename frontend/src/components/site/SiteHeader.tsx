import Link from "next/link";

import { nav } from "@/lib/site";

export function Logo() {
  return (
    <Link
      href="/"
      className="font-display text-lg font-bold no-underline"
      aria-label="AdyraForge home"
    >
      <span className="text-ink">Adyra</span>
      <span className="text-gold">Forge</span>
    </Link>
  );
}

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-ink/5 bg-base/85 backdrop-blur">
      <nav aria-label="Main" className="mx-auto flex max-w-6xl items-center gap-8 px-5 py-4">
        <Logo />
        <ul className="hidden gap-7 text-sm md:flex">
          {nav.map((item) => (
            <li key={item.href}>
              <Link href={item.href} className="text-ink/80 no-underline hover:text-ink">
                {item.label}
              </Link>
            </li>
          ))}
        </ul>
        <Link href="/planner" className="btn-gold ml-auto hidden text-sm md:inline-flex">
          Start a project
        </Link>
        {/* Mobile: a native disclosure, works without JavaScript. */}
        <details className="relative ml-auto md:hidden">
          <summary className="cursor-pointer list-none rounded-md border border-ink/15 px-3 py-1.5 text-sm">
            Menu
          </summary>
          <ul className="absolute right-0 mt-2 w-48 space-y-1 rounded-lg border border-ink/10 bg-surface p-2 shadow-xl">
            {[...nav, { href: "/planner", label: "Start a project" }].map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className="block rounded px-3 py-2 text-ink no-underline hover:bg-base"
                >
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </details>
      </nav>
    </header>
  );
}
