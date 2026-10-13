"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Alert, Button, Field, errorText } from "@/components/ui";
import { endpoints } from "@/lib/api";

export default function AccountPage() {
  const router = useRouter();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [message, setMessage] = useState<{ tone: "error" | "success"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [signingOut, setSigningOut] = useState(false);

  async function changePassword(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    try {
      await endpoints.changePassword(current, next);
      setMessage({
        tone: "success",
        text: "Password updated. Other devices have been signed out.",
      });
      setCurrent("");
      setNext("");
    } catch (e) {
      setMessage({ tone: "error", text: errorText(e) });
    } finally {
      setBusy(false);
    }
  }

  async function logoutEverywhere() {
    setSigningOut(true);
    try {
      await endpoints.logoutAll();
    } finally {
      router.replace("/login");
    }
  }

  return (
    <>
      <h1 className="font-display text-3xl font-bold">Account</h1>

      <section aria-labelledby="pw" className="mt-8 max-w-sm">
        <h2 id="pw" className="font-display text-xl font-bold">
          Change password
        </h2>
        <form onSubmit={changePassword} className="mt-4" noValidate>
          {message && <Alert tone={message.tone}>{message.text}</Alert>}
          <Field
            label="Current password"
            type="password"
            autoComplete="current-password"
            required
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
          />
          <Field
            label="New password"
            type="password"
            autoComplete="new-password"
            required
            minLength={12}
            hint="At least 12 characters."
            value={next}
            onChange={(e) => setNext(e.target.value)}
          />
          <Button type="submit" busy={busy}>
            Update password
          </Button>
        </form>
      </section>

      <section aria-labelledby="sessions" className="mt-12 max-w-sm">
        <h2 id="sessions" className="font-display text-xl font-bold">
          Sessions
        </h2>
        <p className="mt-2 text-sm text-muted">
          Lost a device? Sign out of the portal everywhere, including this browser.
        </p>
        <Button type="button" onClick={logoutEverywhere} busy={signingOut} className="mt-4">
          Sign out of all devices
        </Button>
      </section>
    </>
  );
}
