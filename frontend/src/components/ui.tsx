"use client";

import Link from "next/link";
import { useId, type ComponentProps, type ReactNode } from "react";

import { ApiError } from "@/lib/api";

/** Human-readable message from an API error, including DRF field errors. */
export function errorText(
  error: unknown,
  fallback = "Something went wrong. Please try again.",
): string {
  if (error instanceof ApiError) {
    const data = error.data;
    if (data && typeof data === "object") {
      const first = Object.entries(data as Record<string, unknown>).find(
        ([key]) => key !== "otp_required",
      );
      const value = first?.[1];
      if (typeof value === "string") return value;
      if (Array.isArray(value) && typeof value[0] === "string") return value.join(" ");
    }
    if (error.status === 429) return "Too many attempts. Please wait and try again.";
    return error.detail || fallback;
  }
  return fallback;
}

export function AuthCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main id="main" className="flex min-h-screen items-center justify-center px-4 py-16">
      <div className="w-full max-w-sm rounded-xl border border-ink/10 bg-surface p-8">
        <Link href="/" className="font-display text-lg font-bold no-underline">
          <span className="text-ink">Adyra</span>
          <span className="text-gold">Forge</span>
        </Link>
        <h1 className="mt-6 font-display text-2xl font-bold text-ink">{title}</h1>
        <div className="mt-6">{children}</div>
      </div>
    </main>
  );
}

type FieldProps = ComponentProps<"input"> & { label: string; hint?: string };

export function Field({ label, hint, ...input }: FieldProps) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  return (
    <div className="mb-4">
      <label htmlFor={id} className="mb-1 block text-sm text-ink/90">
        {label}
      </label>
      <input
        id={id}
        aria-describedby={hintId}
        className="w-full rounded-md border border-ink/20 bg-base px-3 py-2 text-ink placeholder:text-muted focus-visible:border-accent"
        {...input}
      />
      {hint && (
        <p id={hintId} className="mt-1 text-xs text-muted">
          {hint}
        </p>
      )}
    </div>
  );
}

export function Button({
  busy,
  children,
  className = "",
  ...props
}: ComponentProps<"button"> & { busy?: boolean }) {
  return (
    <button
      {...props}
      disabled={busy || props.disabled}
      aria-busy={busy || undefined}
      className={`rounded-md border border-gold px-4 py-2 font-medium text-gold transition-colors hover:bg-gold hover:text-base disabled:opacity-50 ${className}`}
    >
      {busy ? "Please wait…" : children}
    </button>
  );
}

export function Alert({ tone, children }: { tone: "error" | "success"; children: ReactNode }) {
  return (
    <p
      role={tone === "error" ? "alert" : "status"}
      className={`mb-4 rounded-md border px-3 py-2 text-sm ${
        tone === "error" ? "border-red-400/40 text-red-200" : "border-gold/40 text-gold-warm"
      }`}
    >
      {children}
    </p>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="rounded-lg border border-ink/10 bg-surface p-6 text-muted">{children}</p>;
}

export function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString(undefined, { dateStyle: "medium" });
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function formatMoney(amount: string, currency: string): string {
  return new Intl.NumberFormat(currency === "INR" ? "en-IN" : "en-US", {
    style: "currency",
    currency,
  }).format(Number(amount));
}
