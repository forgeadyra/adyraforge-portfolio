"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import { Alert, AuthCard, Button, Field, errorText } from "@/components/ui";
import { endpoints } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [done, setDone] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      // The API answers identically whether or not the account exists.
      setDone((await endpoints.requestPasswordReset(email)).detail);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthCard title="Reset your password">
      {done ? (
        <Alert tone="success">{done}</Alert>
      ) : (
        <form onSubmit={onSubmit} noValidate>
          {error && <Alert tone="error">{error}</Alert>}
          <Field
            label="Email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Button type="submit" busy={busy} className="w-full">
            Send reset link
          </Button>
        </form>
      )}
      <p className="mt-4 text-sm">
        <Link href="/login">Back to sign in</Link>
      </p>
    </AuthCard>
  );
}
