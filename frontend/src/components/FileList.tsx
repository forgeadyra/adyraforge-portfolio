"use client";

import { useState } from "react";

import { Alert, Empty, errorText, formatBytes, formatDate } from "@/components/ui";
import { endpoints } from "@/lib/api";
import { useApi } from "@/lib/use-api";

export function FileList({ project }: { project?: number }) {
  const { data, error } = useApi(() => endpoints.files(project), `files-${project ?? "all"}`);
  const [downloadError, setDownloadError] = useState("");

  async function download(id: number) {
    setDownloadError("");
    try {
      // Short-lived signed link, bound to this session; fetched on demand.
      const { url } = await endpoints.fileDownload(id);
      window.location.assign(url);
    } catch (e) {
      setDownloadError(errorText(e));
    }
  }

  if (error) return <Alert tone="error">{errorText(error)}</Alert>;
  if (!data) return <p aria-busy="true">Loading…</p>;
  if (data.results.length === 0) return <Empty>No files yet.</Empty>;

  return (
    <>
      {downloadError && <Alert tone="error">{downloadError}</Alert>}
      <ul className="mt-4 divide-y divide-ink/10 rounded-lg border border-ink/10 bg-surface">
        {data.results.map((f) => (
          <li key={f.id} className="flex flex-wrap items-center gap-4 p-4">
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium">{f.original_name}</p>
              <p className="text-sm text-muted">
                {formatBytes(f.size)} · {formatDate(f.created_at)}
                {f.description && ` · ${f.description}`}
              </p>
            </div>
            <button
              type="button"
              onClick={() => download(f.id)}
              className="text-sm text-accent underline"
            >
              Download<span className="sr-only"> {f.original_name}</span>
            </button>
          </li>
        ))}
      </ul>
    </>
  );
}
