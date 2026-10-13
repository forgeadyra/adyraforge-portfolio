import Link from "next/link";

import { HeroVisual } from "@/components/site/HeroVisual";
import { ProcessTimeline } from "@/components/site/ProcessTimeline";
import { ProjectCard } from "@/components/site/ProjectCard";
import { Reveal } from "@/components/site/Reveal";
import {
  CtaBand,
  ProofBar,
  SectionHeading,
  ServiceCards,
  Testimonials,
} from "@/components/site/Sections";
import { content } from "@/lib/content";
import { site } from "@/lib/site";

export const revalidate = 3600;

export default async function HomePage() {
  const [stats, featured, services, testimonials] = await Promise.all([
    content.stats(),
    content.featured(),
    content.services(),
    content.testimonials(),
  ]);

  return (
    <>
      {/* 1. Hero: the headline is the LCP element and paints without JS. */}
      <section
        aria-labelledby="hero"
        className="mx-auto grid max-w-6xl items-center gap-10 px-5 pb-16 pt-12 md:grid-cols-[1.1fr_1fr] md:pt-20"
      >
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-gold">
            Freelance web development · {site.parent}
          </p>
          <h1 id="hero" className="mt-4 font-display text-4xl font-bold leading-[1.05] sm:text-6xl">
            We forge websites that work as hard as you do.
          </h1>
          <p className="mt-6 max-w-lg text-lg text-ink/80">
            Fast business websites, landing pages and web applications, designed and built
            end-to-end by {site.founder}, with a private client portal for progress, files and
            invoices.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/planner" className="btn-gold">
              Start a project
            </Link>
            <Link href="/work" className="btn-ghost">
              See the work
            </Link>
          </div>
        </div>
        <div className="mx-auto w-full max-w-[460px] md:max-w-none">
          <HeroVisual />
        </div>
      </section>

      {/* 2. Proof bar (real numbers only) */}
      <ProofBar stats={stats} />

      {/* 3. Featured work */}
      {featured.length > 0 && (
        <section aria-labelledby="work" className="mx-auto max-w-6xl px-5 py-20">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <SectionHeading eyebrow="Selected work" title="Recent projects" id="work" />
            <Link href="/work" className="text-sm">
              All work →
            </Link>
          </div>
          <Reveal as="ul" className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {featured.slice(0, 3).map((p) => (
              <li key={p.slug}>
                <ProjectCard project={p} />
              </li>
            ))}
          </Reveal>
        </section>
      )}

      {/* 4. Services */}
      {services.length > 0 && (
        <section aria-labelledby="services" className="mx-auto max-w-6xl px-5 py-20">
          <SectionHeading eyebrow="Services" title="What I build" id="services" />
          <div className="mt-10">
            <ServiceCards services={services} />
          </div>
        </section>
      )}

      {/* 5. Process */}
      <section aria-labelledby="process" className="mx-auto max-w-6xl px-5 py-20">
        <SectionHeading eyebrow="Process" title="From first message to launch" id="process" />
        <ProcessTimeline />
      </section>

      {/* 6. Testimonials: hidden until real ones exist */}
      <Testimonials items={testimonials} />

      {/* 7. CTA */}
      <CtaBand />
    </>
  );
}
