"use client";

import Link from "next/link";
import { useId, useRef, useState, type FormEvent } from "react";

import { Alert, Button, Field, errorText } from "@/components/ui";
import { api } from "@/lib/api";

import { Honeypot, Turnstile } from "./Turnstile";
import { BUDGETS, FEATURES, PROJECT_TYPES, TIMELINES, utmFromUrl } from "./form-options";

type Result = {
  detail: string;
  recommended_services: { name: string; slug: string; summary: string }[];
};

const STEPS = ["Project", "Scope", "Budget", "Contact"] as const;

function Choice({
  name,
  options,
  value,
  onChange,
  legend,
}: {
  name: string;
  options: readonly (readonly [string, string])[];
  value: string;
  onChange: (v: string) => void;
  legend: string;
}) {
  return (
    <fieldset>
      <legend className="mb-3 font-display text-xl font-bold">{legend}</legend>
      <div className="grid gap-2 sm:grid-cols-2">
        {options.map(([v, label]) => (
          <label
            key={v}
            className={`flex cursor-pointer items-center gap-3 rounded-lg border px-4 py-3 ${
              value === v ? "border-gold bg-gold/10" : "border-ink/15 hover:border-ink/30"
            }`}
          >
            <input
              type="radio"
              name={name}
              value={v}
              checked={value === v}
              onChange={() => onChange(v)}
              className="accent-[#D4AF37]"
            />
            {label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export function PlannerForm() {
  const [step, setStep] = useState(0);
  const [projectType, setProjectType] = useState("business_website");
  const [pages, setPages] = useState("5");
  const [features, setFeatures] = useState<string[]>([]);
  const [budget, setBudget] = useState("not_sure");
  const [timeline, setTimeline] = useState("flexible");
  const [contact, setContact] = useState({ name: "", email: "", company: "", message: "" });
  const [website, setWebsite] = useState("");
  const [token, setToken] = useState("");
  const [resetKey, setResetKey] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const pagesId = useId();

  function go(next: number) {
    setStep(next);
    setError("");
    // Move focus to the new step's heading for screen-reader and keyboard users.
    requestAnimationFrame(() => heading.current?.focus());
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (step < STEPS.length - 1) return go(step + 1);
    const wantsReply = contact.name.trim() || contact.email.trim();
    if (wantsReply && !(contact.name.trim() && contact.email.trim())) {
      setError("To get a reply, add both your name and email (or leave both empty).");
      return;
    }
    if (!token) {
      setError("Please complete the verification check.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const pageCount = Number.parseInt(pages, 10);
      const res = await api.post<Result>("/api/leads/planner/", {
        project_type: projectType,
        budget_range: budget,
        timeline,
        features,
        ...(Number.isFinite(pageCount) && pageCount > 0
          ? { page_count: Math.min(pageCount, 200) }
          : {}),
        answers: {},
        ...(wantsReply ? { contact } : {}),
        ...utmFromUrl(),
        website,
        turnstile_token: token,
      });
      setResult(res);
    } catch (e) {
      setError(errorText(e));
      setToken("");
      setResetKey((k) => k + 1);
    } finally {
      setBusy(false);
    }
  }

  if (result) {
    return (
      <div role="status" className="rounded-xl border border-gold/40 bg-surface p-8">
        <h2 className="font-display text-2xl font-bold">Thanks, your plan is in.</h2>
        <p className="mt-2 text-ink/80">
          {contact.email
            ? `Forge will reply to ${contact.email}.`
            : "Add your details on the contact page if you'd like a reply."}
        </p>
        {result.recommended_services.length > 0 && (
          <>
            <p className="mt-6 text-sm uppercase tracking-wider text-muted">Likely a fit</p>
            <ul className="mt-3 space-y-3">
              {result.recommended_services.map((s) => (
                <li key={s.slug} className="rounded-lg border border-ink/10 p-4">
                  <Link href={`/services#${s.slug}`} className="font-medium">
                    {s.name}
                  </Link>
                  <p className="mt-1 text-sm text-ink/75">{s.summary}</p>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    );
  }

  return (
    <form
      onSubmit={onSubmit}
      className="relative rounded-xl border border-ink/10 bg-surface p-6"
      noValidate
    >
      <ol className="mb-8 flex gap-2" aria-label="Progress">
        {STEPS.map((label, i) => (
          <li key={label} className="flex-1">
            <span
              className={`block h-1 rounded ${i <= step ? "bg-gold" : "bg-ink/10"}`}
              aria-hidden="true"
            />
            <span className={`mt-2 block text-xs ${i === step ? "text-ink" : "text-muted"}`}>
              {i === step && <span className="sr-only">Current step: </span>}
              {label}
            </span>
          </li>
        ))}
      </ol>

      <h2 ref={heading} tabIndex={-1} className="sr-only">
        Step {step + 1} of {STEPS.length}: {STEPS[step]}
      </h2>
      {error && <Alert tone="error">{error}</Alert>}

      {step === 0 && (
        <Choice
          legend="What are you building?"
          name="project_type"
          options={PROJECT_TYPES}
          value={projectType}
          onChange={setProjectType}
        />
      )}

      {step === 1 && (
        <div>
          <label htmlFor={pagesId} className="font-display text-xl font-bold">
            Roughly how many pages?
          </label>
          <input
            id={pagesId}
            type="number"
            min={1}
            max={200}
            inputMode="numeric"
            value={pages}
            onChange={(e) => setPages(e.target.value)}
            className="mt-3 block w-32 rounded-md border border-ink/20 bg-base px-3 py-2"
          />
          <fieldset className="mt-8">
            <legend className="mb-3 font-display text-xl font-bold">
              Which features do you need?
            </legend>
            <div className="grid gap-2 sm:grid-cols-2">
              {FEATURES.map((f) => (
                <label
                  key={f}
                  className="flex cursor-pointer items-center gap-3 rounded-lg border border-ink/15 px-4 py-3 hover:border-ink/30"
                >
                  <input
                    type="checkbox"
                    checked={features.includes(f)}
                    onChange={(e) =>
                      setFeatures((cur) =>
                        e.target.checked ? [...cur, f] : cur.filter((x) => x !== f),
                      )
                    }
                    className="accent-[#D4AF37]"
                  />
                  {f}
                </label>
              ))}
            </div>
          </fieldset>
        </div>
      )}

      {step === 2 && (
        <div className="space-y-8">
          <Choice
            legend="Budget"
            name="budget"
            options={BUDGETS}
            value={budget}
            onChange={setBudget}
          />
          <Choice
            legend="Timeline"
            name="timeline"
            options={TIMELINES}
            value={timeline}
            onChange={setTimeline}
          />
        </div>
      )}

      {step === 3 && (
        <div>
          <p className="mb-4 font-display text-xl font-bold">
            Where should Forge reply? (optional)
          </p>
          <div className="grid gap-x-4 sm:grid-cols-2">
            <Field
              label="Name"
              autoComplete="name"
              maxLength={120}
              value={contact.name}
              onChange={(e) => setContact((c) => ({ ...c, name: e.target.value }))}
            />
            <Field
              label="Email"
              type="email"
              autoComplete="email"
              maxLength={254}
              value={contact.email}
              onChange={(e) => setContact((c) => ({ ...c, email: e.target.value }))}
            />
          </div>
          <Field
            label="Company"
            autoComplete="organization"
            maxLength={150}
            value={contact.company}
            onChange={(e) => setContact((c) => ({ ...c, company: e.target.value }))}
          />
          <label className="mb-4 block text-sm text-ink/90">
            Anything else?
            <textarea
              rows={3}
              maxLength={5000}
              value={contact.message}
              onChange={(e) => setContact((c) => ({ ...c, message: e.target.value }))}
              className="mt-1 w-full rounded-md border border-ink/20 bg-base px-3 py-2"
            />
          </label>
          <Honeypot value={website} onChange={setWebsite} />
          <Turnstile onToken={setToken} resetKey={resetKey} />
        </div>
      )}

      <div className="mt-8 flex justify-between gap-3">
        <button
          type="button"
          className="btn-ghost"
          onClick={() => go(step - 1)}
          disabled={step === 0}
        >
          Back
        </button>
        <Button type="submit" busy={busy}>
          {step < STEPS.length - 1 ? "Next" : "Send plan"}
        </Button>
      </div>
    </form>
  );
}
