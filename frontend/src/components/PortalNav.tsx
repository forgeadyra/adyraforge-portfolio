"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { endpoints } from "@/lib/api";

const LINKS = [
  { href: "/portal", label: "Projects" },
  { href: "/portal/files", label: "Files" },
  { href: "/portal/invoices", label: "Invoices" },
  { href: "/portal/account", label: "Account" },
];

export function PortalNav() {
  const pathname = usePathname();
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function logout() {
    setBusy(true);
    try {
      await endpoints.logout();
    } finally {
      router.replace("/login");
    }
  }

  return (
    <header className="border-b border-ink/10 bg-surface">
      <nav
        aria-label="Portal"
        className="mx-auto flex max-w-5xl flex-wrap items-center gap-6 px-4 py-4"
      >
        <Link href="/portal" className="font-display font-bold no-underline">
          <span className="text-ink">Adyra</span>
          <span className="text-gold">Forge</span>
        </Link>
        <ul className="flex flex-wrap gap-4 text-sm">
          {LINKS.map(({ href, label }) => {
            const current =
              href === "/portal"
                ? pathname === href || pathname.startsWith("/portal/projects")
                : pathname.startsWith(href);
            return (
              <li key={href}>
                <Link
                  href={href}
                  aria-current={current ? "page" : undefined}
                  className={
                    current ? "text-gold no-underline" : "text-ink/80 no-underline hover:text-ink"
                  }
                >
                  {label}
                </Link>
              </li>
            );
          })}
        </ul>
        <button
          type="button"
          onClick={logout}
          disabled={busy}
          className="ml-auto text-sm text-muted hover:text-ink"
        >
          {busy ? "Signing out…" : "Sign out"}
        </button>
      </nav>
    </header>
  );
}
