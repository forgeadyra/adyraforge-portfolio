"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import { Alert, Button, Field, errorText } from "@/components/ui";

export function SetPasswordForm({
  submit,
  cta,
}: {
  submit: (password: string) => Promise<{ detail: string }>;
  cta: string;
}) {
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (password !== confirm) {
      setError("The passwords don't match.");
      return;
    }
    setBusy(true);
    try {
      setDone((await submit(password)).detail);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <>
        <Alert tone="success">{done}</Alert>
        <Link href="/login">Go to sign in</Link>
      </>
    );
  }

  return (
    <form onSubmit={onSubmit} noValidate>
      {error && <Alert tone="error">{error}</Alert>}
      <Field
        label="New password"
        type="password"
        autoComplete="new-password"
        required
        minLength={12}
        hint="At least 12 characters. Avoid common or all-number passwords."
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <Field
        label="Confirm password"
        type="password"
        autoComplete="new-password"
        required
        value={confirm}
        onChange={(e) => setConfirm(e.target.value)}
      />
      <Button type="submit" busy={busy} className="w-full">
        {cta}
      </Button>
    </form>
  );
}
