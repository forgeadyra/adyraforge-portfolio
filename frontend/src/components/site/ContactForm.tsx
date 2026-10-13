"use client";

import { useState, type FormEvent } from "react";

import { Alert, Button, Field, errorText } from "@/components/ui";
import { api } from "@/lib/api";

import { Honeypot, Turnstile } from "./Turnstile";
import { BUDGETS, PROJECT_TYPES, TIMELINES, utmFromUrl } from "./form-options";

const selectCls =
  "w-full rounded-md border border-ink/20 bg-base px-3 py-2 text-ink focus-visible:border-accent";

export function ContactForm() {
  const [form, setForm] = useState({
    name: "",
    email: "",
    company: "",
    project_type: "business_website",
    budget_range: "not_sure",
    timeline: "flexible",
    message: "",
  });
  const [website, setWebsite] = useState("");
  const [token, setToken] = useState("");
  const [resetKey, setResetKey] = useState(0);
  const [state, setState] = useState<{ tone: "error" | "success"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const set = (key: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!token) {
      setState({ tone: "error", text: "Please complete the verification check." });
      return;
    }
    setBusy(true);
    setState(null);
    try {
      const res = await api.post<{ detail: string }>("/api/leads/contact/", {
        ...form,
        ...utmFromUrl(),
        website,
        turnstile_token: token,
      });
      setState({ tone: "success", text: res.detail });
    } catch (e) {
      setState({ tone: "error", text: errorText(e) });
      setToken("");
      setResetKey((k) => k + 1); // tokens are single-use
    } finally {
      setBusy(false);
    }
  }

  if (state?.tone === "success") {
    return (
      <div role="status" className="rounded-xl border border-gold/40 bg-surface p-8">
        <p className="font-display text-2xl font-bold">Message sent.</p>
        <p className="mt-2 text-ink/80">
          {state.text} Forge will reply to {form.email}.
        </p>
      </div>
    );
  }

  return (
    <form
      onSubmit={onSubmit}
      className="relative rounded-xl border border-ink/10 bg-surface p-6"
      noValidate
    >
      {state && <Alert tone="error">{state.text}</Alert>}
      <div className="grid gap-x-4 sm:grid-cols-2">
        <Field
          label="Name"
          required
          autoComplete="name"
          maxLength={120}
          value={form.name}
          onChange={set("name")}
        />
        <Field
          label="Email"
          type="email"
          required
          autoComplete="email"
          maxLength={254}
          value={form.email}
          onChange={set("email")}
        />
      </div>
      <Field
        label="Company (optional)"
        autoComplete="organization"
        maxLength={150}
        value={form.company}
        onChange={set("company")}
      />
      <div className="mb-4 grid gap-4 sm:grid-cols-3">
        {(
          [
            ["project_type", "Project type", PROJECT_TYPES],
            ["budget_range", "Budget", BUDGETS],
            ["timeline", "Timeline", TIMELINES],
          ] as const
        ).map(([key, label, options]) => (
          <label key={key} className="block text-sm text-ink/90">
            {label}
            <select className={`${selectCls} mt-1`} value={form[key]} onChange={set(key)}>
              {options.map(([value, text]) => (
                <option key={value} value={value}>
                  {text}
                </option>
              ))}
            </select>
          </label>
        ))}
      </div>
      <label className="mb-4 block text-sm text-ink/90">
        What do you need?
        <textarea
          required
          rows={5}
          maxLength={5000}
          value={form.message}
          onChange={set("message")}
          className={`${selectCls} mt-1`}
        />
      </label>
      <Honeypot value={website} onChange={setWebsite} />
      <Turnstile onToken={setToken} resetKey={resetKey} />
      <Button type="submit" busy={busy} className="mt-4">
        Send message
      </Button>
    </form>
  );
}
