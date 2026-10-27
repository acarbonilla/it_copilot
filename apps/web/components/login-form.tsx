"use client";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, login } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function LoginForm() {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "").trim();
    const password = String(form.get("password") ?? "");
    if (!email || !password) { setError("Enter your email and password."); return; }
    setPending(true); setError("");
    try { await login(email, password); router.replace("/dashboard"); }
    catch (caught) { setError(caught instanceof ApiError && caught.status === 401 ? "Email or password is incorrect." : "The service is unavailable. Please try again."); }
    finally { setPending(false); }
  }
  return <form onSubmit={submit} noValidate className="space-y-5">
    <div className="space-y-2"><label htmlFor="email" className="text-sm font-medium">Email address</label><Input id="email" name="email" type="email" autoComplete="email" required disabled={pending} /></div>
    <div className="space-y-2"><label htmlFor="password" className="text-sm font-medium">Password</label><Input id="password" name="password" type="password" autoComplete="current-password" required disabled={pending} /></div>
    {error && <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">{error}</p>}
    <Button type="submit" className="w-full" disabled={pending}>{pending ? "Signing in…" : "Sign in"}</Button>
  </form>;
}
