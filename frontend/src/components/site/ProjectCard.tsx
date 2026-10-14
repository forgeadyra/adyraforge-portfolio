"use client";

import Image from "next/image";
import Link from "next/link";
import { useRef, type PointerEvent } from "react";

import type { ProjectCard as Project } from "@/lib/content";

import { ProjectBadges } from "./ProjectBadges";

/** Case-study card with a subtle hover tilt (fine pointers, motion allowed). */
export function ProjectCard({
  project,
  headingLevel = 3,
}: {
  project: Project;
  headingLevel?: 2 | 3;
}) {
  const ref = useRef<HTMLElement>(null);
  const Heading = headingLevel === 2 ? "h2" : "h3";

  function tilt(e: PointerEvent<HTMLElement>) {
    const el = ref.current;
    if (!el || e.pointerType !== "mouse") return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const r = el.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - 0.5;
    const y = (e.clientY - r.top) / r.height - 0.5;
    el.style.transform = `perspective(900px) rotateX(${(-y * 5).toFixed(2)}deg) rotateY(${(x * 6).toFixed(2)}deg)`;
  }

  function reset() {
    if (ref.current) ref.current.style.transform = "";
  }

  return (
    <article
      ref={ref}
      onPointerMove={tilt}
      onPointerLeave={reset}
      className="group relative flex h-full flex-col overflow-hidden rounded-xl border border-ink/10 bg-surface transition-transform duration-200 ease-out will-change-transform hover:border-gold/40"
    >
      <div className="relative aspect-[16/10] overflow-hidden bg-base">
        {project.cover_image ? (
          <Image
            src={project.cover_image}
            alt={project.cover_alt}
            fill
            sizes="(min-width: 1024px) 33vw, (min-width: 640px) 50vw, 100vw"
            className="object-cover transition-transform duration-500 group-hover:scale-[1.03]"
          />
        ) : (
          // No screenshot yet: a branded placeholder, never a stock image.
          <div
            aria-hidden="true"
            className="flex h-full items-end bg-[radial-gradient(circle_at_30%_20%,rgba(212,175,55,0.25),transparent_60%)] p-5"
          >
            <span className="font-display text-5xl font-bold text-gold/70">
              {project.title.charAt(0)}
            </span>
          </div>
        )}
        <span className="absolute left-3 top-3">
          <ProjectBadges project={project} />
        </span>
      </div>
      <div className="flex flex-1 flex-col p-5">
        <p className="text-xs uppercase tracking-wider text-muted">
          {project.industry || "Web project"}
        </p>
        <Heading className="mt-1 font-display text-xl font-bold">
          {/* Stretched link: the whole card is clickable, one tab stop. */}
          <Link
            href={`/work/${project.slug}`}
            className="text-ink no-underline after:absolute after:inset-0"
          >
            {project.title}
          </Link>
        </Heading>
        {project.summary && <p className="mt-2 text-sm text-ink/75">{project.summary}</p>}
        <ul className="mt-auto flex flex-wrap gap-1.5 pt-4" aria-label="Technologies">
          {project.technologies.slice(0, 4).map((t) => (
            <li
              key={t.slug}
              className="rounded border border-ink/10 px-2 py-0.5 text-xs text-muted"
            >
              {t.name}
            </li>
          ))}
        </ul>
      </div>
    </article>
  );
}
