import type { Metadata } from "next";

import { ProcessTimeline } from "@/components/site/ProcessTimeline";
import { CtaBand, SectionHeading, ServiceCards } from "@/components/site/Sections";
import { content } from "@/lib/content";

export const revalidate = 3600;

export const metadata: Metadata = {
  title: "Services",
  description:
    "Business websites, landing pages and web applications. What's included in each, and how a project runs from first message to launch.",
  alternates: { canonical: "/services" },
};

export default async function ServicesPage() {
  const services = await content.services();
  const hasPrices = services.some((s) => s.price_from_inr || s.price_from_usd);
  return (
    <>
      <section className="mx-auto max-w-6xl px-5 pb-12 pt-16">
        <p className="text-xs uppercase tracking-[0.2em] text-gold">Services</p>
        <h1 className="mt-3 font-display text-4xl font-bold sm:text-5xl">What I build</h1>
        <p className="mt-4 max-w-2xl text-lg text-ink/80">
          Three kinds of project, each designed and built end-to-end.
          {hasPrices
            ? " Prices are starting points; the planner gives you a scoped estimate."
            : " Every project is quoted from its scope; the planner is the fastest way to get a number."}
        </p>
        <div className="mt-12">
          <ServiceCards services={services} headingLevel={2} />
        </div>
      </section>
      <section aria-labelledby="process" className="mx-auto max-w-6xl px-5 py-16">
        <SectionHeading eyebrow="Process" title="How a project runs" id="process" />
        <ProcessTimeline />
      </section>
      <CtaBand />
    </>
  );
}
