import type { Metadata } from "next";

import { WorkExplorer } from "@/components/site/WorkExplorer";
import { CtaBand } from "@/components/site/Sections";
import { content } from "@/lib/content";

export const revalidate = 3600;

export const metadata: Metadata = {
  title: "Work",
  description:
    "Websites, landing pages and web apps by AdyraForge: live client projects and concept builds, filterable by industry and technology.",
  alternates: { canonical: "/work" },
};

export default async function WorkPage() {
  const [projects, technologies] = await Promise.all([content.projects(), content.technologies()]);
  const industries = [...new Set(projects.map((p) => p.industry).filter(Boolean))].sort();

  return (
    <>
      <section className="mx-auto max-w-6xl px-5 pb-8 pt-16">
        <p className="text-xs uppercase tracking-[0.2em] text-gold">Work</p>
        <h1 className="mt-3 font-display text-4xl font-bold sm:text-5xl">Projects</h1>
        <p className="mt-4 max-w-2xl text-lg text-ink/80">
          Live client sites and concept builds. Each one has a short case study: the problem, what
          was built, and the stack.
        </p>
        <WorkExplorer projects={projects} industries={industries} technologies={technologies} />
      </section>
      <CtaBand />
    </>
  );
}
