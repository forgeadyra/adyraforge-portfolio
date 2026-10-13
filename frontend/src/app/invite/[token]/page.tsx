"use client";

import { useParams } from "next/navigation";

import { SetPasswordForm } from "@/components/SetPasswordForm";
import { AuthCard } from "@/components/ui";
import { endpoints } from "@/lib/api";

export default function InvitePage() {
  const { token } = useParams<{ token: string }>();
  return (
    <AuthCard title="Activate your portal">
      <p className="mb-6 text-sm text-muted">
        Choose a password to finish setting up your AdyraForge client account.
      </p>
      <SetPasswordForm
        cta="Activate account"
        submit={(password) => endpoints.acceptInvite(decodeURIComponent(token), password)}
      />
    </AuthCard>
  );
}
