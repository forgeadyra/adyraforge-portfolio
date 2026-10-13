"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";

import { Alert, AuthCard, Button, Field, errorText } from "@/components/ui";
import { ApiError, endpoints } from "@/lib/api";
import { safeNext } from "@/lib/auth-guard";

function LoginForm() {
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [otp, setOtp] = useState("");
  const [needsOtp, setNeedsOtp] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const me = await endpoints.login({
        email,
        password,
        ...(needsOtp ? { otp_token: otp } : {}),
      });
      router.replace(me.role === "client" ? next : "/");
    } catch (e) {
      if (e instanceof ApiError && (e.data as { otp_required?: boolean } | null)?.otp_required) {
        setNeedsOtp(true);
      }
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate>
      {error && <Alert tone="error">{error}</Alert>}
      <Field
        label="Email"
        type="email"
        autoComplete="username"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />
      <Field
        label="Password"
        type="password"
        autoComplete="current-password"
        required
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      {needsOtp && (
        <Field
          label="Authenticator code"
          inputMode="numeric"
          autoComplete="one-time-code"
          required
          value={otp}
          onChange={(e) => setOtp(e.target.value)}
        />
      )}
      <Button type="submit" busy={busy} className="w-full">
        Sign in
      </Button>
      <p className="mt-4 text-sm">
        <Link href="/forgot-password">Forgot your password?</Link>
      </p>
    </form>
  );
}

export default function LoginPage() {
  return (
    <AuthCard title="Client portal">
      <Suspense>
        <LoginForm />
      </Suspense>
    </AuthCard>
  );
}
