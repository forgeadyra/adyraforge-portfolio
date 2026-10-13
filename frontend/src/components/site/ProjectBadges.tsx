import type { ProjectCard } from "@/lib/content";

/**
 * Honest labelling: concept work is always visibly marked "Concept" and is
 * never presented as client work. "Live" only means the site is deployed.
 */
export function ProjectBadges({ project }: { project: Pick<ProjectCard, "kind" | "status"> }) {
  return (
    <span className="flex flex-wrap gap-1.5">
      {project.kind === "concept" ? (
        <span className="rounded-full border border-gold bg-base/90 px-2.5 py-0.5 text-xs font-semibold text-gold">
          Concept
        </span>
      ) : (
        <span className="rounded-full border border-ink/30 bg-base/90 px-2.5 py-0.5 text-xs text-ink">
          Client project
        </span>
      )}
      {project.status === "live" && (
        <span className="rounded-full border border-ink/15 bg-base/90 px-2.5 py-0.5 text-xs text-ink/80">
          Live
        </span>
      )}
    </span>
  );
}
