"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { currentUser } from "@/lib/api";

export function AuthRedirect() {
  const router = useRouter();
  useEffect(() => { currentUser().then(() => router.replace("/dashboard")).catch(() => router.replace("/login")); }, [router]);
  return <main className="grid min-h-screen place-items-center" aria-busy="true"><p role="status">Checking your session…</p></main>;
}
