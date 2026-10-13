"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useId, useState, type FormEvent } from "react";

import { Alert, Button, errorText } from "@/components/ui";
import { endpoints } from "@/lib/api";
import { useApi } from "@/lib/use-api";

export default function MessagesPage() {
  const projectId = Number(useParams<{ id: string }>().id);
  const { data, error, setData } = useApi(
    () => endpoints.messages(projectId),
    `messages-${projectId}`,
  );
  const [body, setBody] = useState("");
  const [sendError, setSendError] = useState("");
  const [busy, setBusy] = useState(false);
  const inputId = useId();

  // Mark Forge's unread messages as read once they're shown.
  useEffect(() => {
    data?.results
      .filter((m) => !m.is_mine && !m.read_at)
      .forEach((m) => void endpoints.markRead(m.id).catch(() => undefined));
  }, [data]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!body.trim()) return;
    setBusy(true);
    setSendError("");
    try {
      const sent = await endpoints.sendMessage(projectId, body);
      setData((page) => (page ? { ...page, results: [...page.results, sent] } : page));
      setBody("");
    } catch (e) {
      setSendError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  if (error) return <Alert tone="error">{errorText(error, "Project not found.")}</Alert>;

  return (
    <>
      <p className="text-sm">
        <Link href={`/portal/projects/${projectId}`}>← Back to project</Link>
      </p>
      <h1 className="mt-2 font-display text-3xl font-bold">Messages</h1>

      <ol className="mt-8 space-y-4" aria-live="polite">
        {data?.results.map((m) => (
          <li
            key={m.id}
            className={`max-w-xl rounded-lg border p-4 ${
              m.is_mine ? "ml-auto border-gold/30 bg-surface" : "border-ink/10 bg-base"
            }`}
          >
            <p className="text-xs text-muted">
              {m.is_mine ? "You" : m.sender_name} · {new Date(m.created_at).toLocaleString()}
            </p>
            {/* Plain text, rendered escaped by React. Never dangerouslySetInnerHTML. */}
            <p className="mt-1 whitespace-pre-wrap break-words">{m.body}</p>
          </li>
        ))}
        {data && data.results.length === 0 && <li className="text-muted">No messages yet.</li>}
      </ol>

      <form onSubmit={onSubmit} className="mt-8">
        {sendError && <Alert tone="error">{sendError}</Alert>}
        <label htmlFor={inputId} className="mb-1 block text-sm">
          New message
        </label>
        <textarea
          id={inputId}
          value={body}
          maxLength={5000}
          rows={4}
          onChange={(e) => setBody(e.target.value)}
          className="w-full rounded-md border border-ink/20 bg-base px-3 py-2 text-ink focus-visible:border-accent"
        />
        <Button type="submit" busy={busy} className="mt-3">
          Send
        </Button>
      </form>
    </>
  );
}
