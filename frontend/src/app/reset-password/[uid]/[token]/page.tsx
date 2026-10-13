"use client";

import { useParams } from "next/navigation";

import { SetPasswordForm } from "@/components/SetPasswordForm";
import { AuthCard } from "@/components/ui";
import { endpoints } from "@/lib/api";

export default function ResetPasswordPage() {
  const { uid, token } = useParams<{ uid: string; token: string }>();
  return (
    <AuthCard title="Choose a new password">
      <SetPasswordForm
        cta="Update password"
        submit={(password) => endpoints.confirmPasswordReset(uid, token, password)}
      />
    </AuthCard>
  );
}
