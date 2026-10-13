import Link from "next/link";

import { nav, site } from "@/lib/site";

import { Logo } from "./SiteHeader";

export function SiteFooter() {
  return (
    <footer className="mt-24 border-t border-ink/10">
      <div className="mx-auto grid max-w-6xl gap-10 px-5 py-12 md:grid-cols-3">
        <div>
          <Logo />
          <p className="mt-3 max-w-xs text-sm text-muted">
            A freelance web development brand under {site.parent}, founded by {site.founder}.
          </p>
        </div>
        <nav aria-label="Footer">
          <ul className="space-y-2 text-sm">
            {[...nav, { href: "/planner", label: "Project planner" }].map((item) => (
              <li key={item.href}>
                <Link href={item.href} className="text-ink/80 no-underline hover:text-ink">
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <div className="space-y-2 text-sm">
          <p>
            <a href={`mailto:${site.email}`}>{site.email}</a>
          </p>
          <p>
            <a href={site.links.fiverr} rel="noopener noreferrer" target="_blank">
              Fiverr<span className="sr-only"> (opens in a new tab)</span>
            </a>
            {" · "}
            <a href={site.links.github} rel="noopener noreferrer" target="_blank">
              GitHub<span className="sr-only"> (opens in a new tab)</span>
            </a>
          </p>
          <p className="pt-2 text-muted">
            <Link href="/login" className="text-muted">
              Client portal
            </Link>
          </p>
        </div>
      </div>
      <p className="pb-8 text-center text-xs text-muted">
        © {new Date().getFullYear()} {site.name}. All rights reserved.
      </p>
    </footer>
  );
}
