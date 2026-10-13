import type { Metadata } from "next";

import { PlannerForm } from "@/components/site/PlannerForm";

export const metadata: Metadata = {
  title: "Project planner",
  description:
    "Plan your website or web app in four quick steps: type, scope, budget and timeline. Forge replies with a clear next step.",
  alternates: { canonical: "/planner" },
};

export default function PlannerPage() {
  return (
    <section className="mx-auto max-w-3xl px-5 pt-16">
      <p className="text-xs uppercase tracking-[0.2em] text-gold">Project planner</p>
      <h1 className="mt-3 font-display text-4xl font-bold sm:text-5xl">Start a project</h1>
      <p className="mt-4 text-lg text-ink/80">
        Four quick steps. Contact details are optional, but needed if you&apos;d like a reply.
      </p>
      <div className="mt-10">
        <PlannerForm />
      </div>
    </section>
  );
}
