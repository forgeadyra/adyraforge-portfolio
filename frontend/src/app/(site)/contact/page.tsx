import type { Metadata } from "next";
import Link from "next/link";

import { ContactForm } from "@/components/site/ContactForm";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: "Contact",
  description: "Tell AdyraForge about your website or web app project.",
  alternates: { canonical: "/contact" },
};

export default function ContactPage() {
  return (
    <section className="mx-auto grid max-w-6xl gap-12 px-5 pt-16 md:grid-cols-[1fr_1.4fr]">
      <div>
        <p className="text-xs uppercase tracking-[0.2em] text-gold">Contact</p>
        <h1 className="mt-3 font-display text-4xl font-bold sm:text-5xl">Let&apos;s talk</h1>
        <p className="mt-4 text-lg text-ink/80">
          Tell Forge what you need. Not sure about scope yet? The{" "}
          <Link href="/planner">project planner</Link> walks you through it.
        </p>
        <dl className="mt-10 space-y-4 text-sm">
          <div>
            <dt className="text-muted">Email</dt>
            <dd>
              <a href={`mailto:${site.email}`}>{site.email}</a>
            </dd>
          </div>
          <div>
            <dt className="text-muted">Elsewhere</dt>
            <dd>
              <a href={site.links.fiverr} target="_blank" rel="noopener noreferrer">
                Fiverr<span className="sr-only"> (opens in a new tab)</span>
              </a>
              {" · "}
              <a href={site.links.github} target="_blank" rel="noopener noreferrer">
                GitHub<span className="sr-only"> (opens in a new tab)</span>
              </a>
            </dd>
          </div>
        </dl>
      </div>
      <ContactForm />
    </section>
  );
}
