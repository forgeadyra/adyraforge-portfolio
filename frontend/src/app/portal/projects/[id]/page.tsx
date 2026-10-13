"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { FileList } from "@/components/FileList";
import { InvoiceList } from "@/components/InvoiceList";
import { Alert, errorText, formatDate } from "@/components/ui";
import { endpoints } from "@/lib/api";
import { STATUS_LABEL } from "@/lib/labels";
import { useApi } from "@/lib/use-api";

export default function ProjectPage() {
  const id = Number(useParams<{ id: string }>().id);
  const { data: project, error } = useApi(() => endpoints.project(id), `project-${id}`);

  if (error) return <Alert tone="error">{errorText(error, "Project not found.")}</Alert>;
  if (!project) return <p aria-busy="true">Loading…</p>;

  return (
    <>
      <p className="text-sm">
        <Link href="/portal">← All projects</Link>
      </p>
      <h1 className="mt-2 font-display text-3xl font-bold">{project.title}</h1>
      <p className="mt-2 text-muted">
        {STATUS_LABEL[project.status]} · {project.progress}% · started{" "}
        {formatDate(project.start_date)} · due {formatDate(project.due_date)}
      </p>
      {project.description && <p className="mt-6 whitespace-pre-line">{project.description}</p>}

      <p className="mt-6">
        <Link href={`/portal/projects/${project.id}/messages`}>Open messages →</Link>
      </p>

      <section aria-labelledby="milestones" className="mt-10">
        <h2 id="milestones" className="font-display text-xl font-bold">
          Milestones
        </h2>
        {project.milestones.length === 0 ? (
          <p className="mt-3 text-muted">No milestones yet.</p>
        ) : (
          <ol className="mt-4 space-y-3">
            {project.milestones.map((m) => (
              <li
                key={m.id}
                className="flex items-start gap-3 rounded-lg border border-ink/10 bg-surface p-4"
              >
                <span aria-hidden="true" className={m.is_complete ? "text-gold" : "text-muted"}>
                  {m.is_complete ? "●" : "○"}
                </span>
                <div>
                  <p className="font-medium">
                    {m.title}
                    <span className="sr-only">{m.is_complete ? " (complete)" : " (open)"}</span>
                  </p>
                  <p className="text-sm text-muted">
                    {m.is_complete
                      ? `Completed ${formatDate(m.completed_at)}`
                      : `Due ${formatDate(m.due_date)}`}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section aria-labelledby="files" className="mt-10">
        <h2 id="files" className="font-display text-xl font-bold">
          Files
        </h2>
        <FileList project={project.id} />
      </section>

      <section aria-labelledby="invoices" className="mt-10">
        <h2 id="invoices" className="font-display text-xl font-bold">
          Invoices
        </h2>
        <InvoiceList project={project.id} />
      </section>
    </>
  );
}
