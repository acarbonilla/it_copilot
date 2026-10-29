"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { activateAccount, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function ActivationForm({ token }: { token: string }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    const form = new FormData(event.currentTarget);
    const password = String(form.get("password") ?? "");
    const confirmation = String(form.get("confirmation") ?? "");
    if (password.length < 12) { setError("Use at least 12 characters."); return; }
    if (password !== confirmation) { setError("Passwords do not match."); return; }
    setPending(true);
    setError("");
    try {
      await activateAccount(token, password);
      router.replace("/login");
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === "password_policy_failed") {
        setError("Choose a less common password that is not based on your account details.");
      } else if (caught instanceof ApiError && caught.code === "invalid_activation") {
        setError("This activation link is invalid or has expired.");
      } else {
        setError("The service is unavailable. Please try again.");
      }
    } finally {
      setPending(false);
    }
  }

  return <form onSubmit={submit} noValidate className="space-y-5">
    <div className="space-y-2">
      <label htmlFor="password" className="text-sm font-medium">Create password</label>
      <Input id="password" name="password" type="password" autoComplete="new-password" minLength={12} required disabled={pending} />
      <p className="text-xs text-slate-500">Use at least 12 characters and avoid common passwords.</p>
    </div>
    <div className="space-y-2">
      <label htmlFor="confirmation" className="text-sm font-medium">Confirm password</label>
      <Input id="confirmation" name="confirmation" type="password" autoComplete="new-password" minLength={12} required disabled={pending} />
    </div>
    {error && <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">{error}</p>}
    <Button type="submit" className="w-full" disabled={pending}>{pending ? "Activating…" : "Activate account"}</Button>
  </form>;
}
