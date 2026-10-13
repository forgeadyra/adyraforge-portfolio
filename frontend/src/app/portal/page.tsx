"use client";

import Link from "next/link";

import { Alert, Empty, errorText, formatDate } from "@/components/ui";
import { endpoints } from "@/lib/api";
import { STATUS_LABEL } from "@/lib/labels";
import { useApi } from "@/lib/use-api";

export default function PortalHome() {
  const { data, error, loading } = useApi(() => endpoints.projects(), "projects");

  return (
    <>
      <h1 className="font-display text-3xl font-bold">Your projects</h1>
      <div className="mt-8" aria-live="polite" aria-busy={loading}>
        {error ? <Alert tone="error">{errorText(error)}</Alert> : null}
        {data && data.results.length === 0 && (
          <Empty>No projects yet. Forge will add yours here.</Empty>
        )}
        <ul className="grid gap-4 sm:grid-cols-2">
          {data?.results.map((p) => (
            <li key={p.id} className="rounded-xl border border-ink/10 bg-surface p-6">
              <h2 className="font-display text-xl font-bold">
                <Link
                  href={`/portal/projects/${p.id}`}
                  className="text-ink no-underline hover:text-gold"
                >
                  {p.title}
                </Link>
              </h2>
              <p className="mt-1 text-sm text-muted">
                {STATUS_LABEL[p.status]} · due {formatDate(p.due_date)}
              </p>
              <div
                className="mt-4 h-2 rounded-full bg-base"
                role="progressbar"
                aria-label={`${p.title} progress`}
                aria-valuenow={p.progress}
                aria-valuemin={0}
                aria-valuemax={100}
              >
                <div className="h-2 rounded-full bg-gold" style={{ width: `${p.progress}%` }} />
              </div>
              <p className="mt-2 text-right text-xs text-muted">{p.progress}%</p>
            </li>
          ))}
        </ul>
      </div>
    </>
  );
}
