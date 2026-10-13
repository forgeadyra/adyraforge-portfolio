"use client";

import { useEffect, useId, useMemo, useState } from "react";

import type { ProjectCard as Project, Technology } from "@/lib/content";

import { ProjectCard } from "./ProjectCard";

function readParam(name: string): string {
  if (typeof window === "undefined") return "";
  return new URLSearchParams(window.location.search).get(name) ?? "";
}

/** Grid with industry/tech filters, mirrored into the URL so a filtered view can be shared. */
export function WorkExplorer({
  projects,
  industries,
  technologies,
}: {
  projects: Project[];
  industries: string[];
  technologies: Technology[];
}) {
  const [industry, setIndustry] = useState("");
  const [tech, setTech] = useState("");
  const industryId = useId();
  const techId = useId();

  // Read ?industry=&tech= after hydration (the page itself stays static/ISR).
  useEffect(() => {
    const fromUrl = { industry: readParam("industry"), tech: readParam("tech") };
    if (fromUrl.industry || fromUrl.tech) {
      queueMicrotask(() => {
        setIndustry(fromUrl.industry);
        setTech(fromUrl.tech);
      });
    }
  }, []);

  useEffect(() => {
    const params = new URLSearchParams();
    if (industry) params.set("industry", industry);
    if (tech) params.set("tech", tech);
    const query = params.toString();
    window.history.replaceState(null, "", query ? `?${query}` : window.location.pathname);
  }, [industry, tech]);

  const shown = useMemo(
    () =>
      projects.filter(
        (p) =>
          (!industry || p.industry === industry) &&
          (!tech || p.technologies.some((t) => t.slug === tech)),
      ),
    [projects, industry, tech],
  );

  const select =
    "mt-1 w-full rounded-md border border-ink/20 bg-surface px-3 py-2 text-ink focus-visible:border-accent";

  return (
    <>
      <form
        className="mt-10 grid gap-4 sm:grid-cols-[1fr_1fr_auto] sm:items-end"
        onSubmit={(e) => e.preventDefault()}
      >
        <div>
          <label htmlFor={industryId} className="text-sm text-muted">
            Industry
          </label>
          <select
            id={industryId}
            className={select}
            value={industry}
            onChange={(e) => setIndustry(e.target.value)}
          >
            <option value="">All industries</option>
            {industries.map((i) => (
              <option key={i} value={i}>
                {i}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor={techId} className="text-sm text-muted">
            Technology
          </label>
          <select
            id={techId}
            className={select}
            value={tech}
            onChange={(e) => setTech(e.target.value)}
          >
            <option value="">All technologies</option>
            {technologies.map((t) => (
              <option key={t.slug} value={t.slug}>
                {t.name}
              </option>
            ))}
          </select>
        </div>
        <button
          type="button"
          className="btn-ghost"
          onClick={() => {
            setIndustry("");
            setTech("");
          }}
          disabled={!industry && !tech}
        >
          Clear
        </button>
      </form>

      <p className="mt-6 text-sm text-muted" role="status" aria-live="polite">
        {shown.length} {shown.length === 1 ? "project" : "projects"}
      </p>

      {shown.length === 0 ? (
        <p className="mt-6 rounded-xl border border-ink/10 bg-surface p-8 text-ink/80">
          No projects match those filters yet.
        </p>
      ) : (
        <ul className="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {shown.map((p) => (
            <li key={p.slug}>
              <ProjectCard project={p} headingLevel={2} />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
