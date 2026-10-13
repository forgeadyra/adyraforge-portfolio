import Link from "next/link";

import type { Service, Stats, Testimonial } from "@/lib/content";
import { formatPrice } from "@/lib/site";

import { Reveal } from "./Reveal";

export function SectionHeading({
  eyebrow,
  title,
  id,
}: {
  eyebrow: string;
  title: string;
  id: string;
}) {
  return (
    <div className="max-w-2xl">
      <p className="text-xs uppercase tracking-[0.2em] text-gold">{eyebrow}</p>
      <h2 id={id} className="mt-3 font-display text-3xl font-bold sm:text-4xl">
        {title}
      </h2>
    </div>
  );
}

/** Only real numbers from the API. Anything not set simply isn't shown. */
export function ProofBar({ stats }: { stats: Stats }) {
  const items = [
    stats.live_projects > 0 && { value: String(stats.live_projects), label: "live projects" },
    stats.industries.length > 0 && {
      value: String(stats.industries.length),
      label: "industries served",
    },
    stats.response_time_hours && {
      value: `${stats.response_time_hours}h`,
      label: "reply to every enquiry",
    },
  ].filter(Boolean) as { value: string; label: string }[];

  if (items.length === 0) return null;
  return (
    <section aria-label="At a glance" className="border-y border-ink/10 bg-surface/60">
      <dl className="mx-auto flex max-w-6xl flex-wrap justify-around gap-6 px-5 py-6 text-center">
        {items.map((item) => (
          <div key={item.label}>
            <dt className="sr-only">{item.label}</dt>
            <dd>
              <span className="font-display text-3xl font-bold text-gold">{item.value}</span>
              <span className="mt-1 block text-sm text-muted">{item.label}</span>
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

export function PriceFrom({ service }: { service: Service }) {
  const { price_from_inr: inr, price_from_usd: usd } = service;
  if (!inr && !usd) return null;
  return (
    <p className="mt-4 text-sm">
      <span className="text-muted">Starting from </span>
      <span className="font-medium text-ink">
        {[inr && formatPrice(inr, "INR"), usd && formatPrice(usd, "USD")]
          .filter(Boolean)
          .join(" · ")}
      </span>
    </p>
  );
}

export function ServiceCards({
  services,
  headingLevel = 3,
}: {
  services: Service[];
  headingLevel?: 2 | 3;
}) {
  const Heading = headingLevel === 2 ? "h2" : "h3";
  return (
    <Reveal as="ul" className="grid gap-5 md:grid-cols-3">
      {services.map((s) => (
        <li
          key={s.slug}
          id={s.slug}
          className="flex flex-col rounded-xl border border-ink/10 bg-surface p-6"
        >
          <Heading className="font-display text-xl font-bold">{s.name}</Heading>
          <p className="mt-2 text-ink/80">{s.summary}</p>
          {s.includes.length > 0 && (
            <>
              <p className="mt-5 text-xs uppercase tracking-wider text-muted">
                What&apos;s included
              </p>
              <ul className="mt-2 space-y-1.5 text-sm">
                {s.includes.map((item) => (
                  <li key={item} className="flex gap-2">
                    <span aria-hidden="true" className="text-gold">
                      ◆
                    </span>
                    {item}
                  </li>
                ))}
              </ul>
            </>
          )}
          <div className="mt-auto pt-2">
            <PriceFrom service={s} />
          </div>
        </li>
      ))}
    </Reveal>
  );
}

/** Rendered only when real, published testimonials exist. Never placeholders. */
export function Testimonials({ items }: { items: Testimonial[] }) {
  if (items.length === 0) return null;
  return (
    <section aria-labelledby="testimonials" className="mx-auto max-w-6xl px-5 py-20">
      <SectionHeading eyebrow="Clients" title="In their words" id="testimonials" />
      <Reveal as="ul" className="mt-10 grid gap-5 md:grid-cols-2">
        {items.map((t) => (
          <li key={`${t.author_name}-${t.quote.slice(0, 20)}`}>
            <figure className="h-full rounded-xl border border-ink/10 bg-surface p-6">
              <blockquote className="text-lg text-ink/90">“{t.quote}”</blockquote>
              <figcaption className="mt-4 text-sm text-muted">
                <span className="text-ink">{t.author_name}</span>
                {[t.author_role, t.company].filter(Boolean).length > 0 &&
                  ` · ${[t.author_role, t.company].filter(Boolean).join(", ")}`}
              </figcaption>
            </figure>
          </li>
        ))}
      </Reveal>
    </section>
  );
}

export function CtaBand({
  title = "Have a project in mind?",
  body = "The project planner takes two minutes and gives Forge everything needed to reply with a clear next step.",
}: {
  title?: string;
  body?: string;
}) {
  return (
    <section aria-labelledby="cta" className="mx-auto max-w-6xl px-5 py-12">
      <div className="rounded-2xl border border-gold/30 bg-[radial-gradient(circle_at_80%_0%,rgba(212,175,55,0.18),transparent_55%)] px-6 py-12 text-center sm:px-12">
        <h2 id="cta" className="font-display text-3xl font-bold sm:text-4xl">
          {title}
        </h2>
        <p className="mx-auto mt-3 max-w-xl text-ink/80">{body}</p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link href="/planner" className="btn-gold">
            Plan your project
          </Link>
          <Link href="/contact" className="btn-ghost">
            Just send a message
          </Link>
        </div>
      </div>
    </section>
  );
}
