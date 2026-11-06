"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { BookOpen, Bot, KeyRound, LockKeyhole, ShieldCheck } from "lucide-react";
import { ApiError, currentUser, logout, type UserIdentity } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const modules = [
  { name: "Documents", description: "Authorized IT documentation and processing", icon: BookOpen },
  { name: "Private Web Documentation", description: "Your private web references", icon: LockKeyhole },
  { name: "My Credentials", description: "Your protected credential vault", icon: KeyRound },
  { name: "Copilot", description: "Assisted IT support conversations", icon: Bot },
];

export function DashboardShell() {
  const router = useRouter();
  const [user, setUser] = useState<UserIdentity | null>(null);
  const [failure, setFailure] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  useEffect(() => { currentUser().then(setUser).catch((error) => { if (error instanceof ApiError && error.status === 401) router.replace("/login"); else setFailure(true); }); }, [router]);
  async function signOut() { setLoggingOut(true); try { await logout(); router.replace("/login"); } catch { setLoggingOut(false); setFailure(true); } }
  if (failure) return <main className="grid min-h-screen place-items-center px-4"><div role="alert" className="max-w-md rounded-lg border bg-white p-6"><h1 className="font-semibold">Unable to load your workspace</h1><p className="mt-2 text-sm text-slate-600">Check the API service and try again.</p><Button className="mt-4" onClick={() => location.reload()}>Try again</Button></div></main>;
  if (!user) return <main className="grid min-h-screen place-items-center" aria-busy="true"><p role="status">Loading your workspace…</p></main>;
  const visible = user.is_app_admin ? [...modules, { name: "Administration", description: "User and platform administration", icon: ShieldCheck }] : modules;
  return <div className="min-h-screen lg:grid lg:grid-cols-[260px_1fr]">
    <aside className="border-b bg-slate-950 p-6 text-white lg:min-h-screen lg:border-b-0 lg:border-r"><p className="font-semibold">IT Support Copilot</p><nav aria-label="Module navigation" className="mt-8"><ul className="space-y-2">{visible.map(({ name, icon: Icon }) => <li key={name}>{name === "Administration" || name === "Documents" ? <Link href={name === "Administration" ? "/admin/users" : "/documents"} className="flex items-center gap-3 rounded-md px-3 py-2 text-sm text-white hover:bg-slate-800"><Icon aria-hidden="true" size={18} /><span>{name}</span></Link> : <div className="flex items-center gap-3 rounded-md px-3 py-2 text-sm text-slate-300"><Icon aria-hidden="true" size={18} /><span>{name}</span><span className="ml-auto rounded bg-slate-800 px-2 py-0.5 text-xs">Coming soon</span></div>}</li>)}</ul></nav></aside>
    <div><header className="flex flex-wrap items-center justify-between gap-4 border-b bg-white px-6 py-4"><div><p className="text-xs uppercase tracking-wide text-slate-500">Signed in as</p><p className="font-medium">{user.email}</p></div><Button variant="outline" onClick={signOut} disabled={loggingOut}>{loggingOut ? "Signing out…" : "Sign out"}</Button></header>
      <main className="p-6 lg:p-10"><h1 className="text-3xl font-bold tracking-tight">Dashboard</h1><p className="mt-2 text-slate-600">Your IT support workspace is ready. Modules will become available in later releases.</p><section aria-labelledby="modules-heading" className="mt-8"><h2 id="modules-heading" className="text-xl font-semibold">Modules</h2><div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{visible.map(({ name, description, icon: Icon }) => <Card key={name}><CardHeader><Icon aria-hidden="true" className="text-slate-600" /><CardTitle>{name}</CardTitle></CardHeader><CardContent><p className="text-sm text-slate-600">{description}</p><p className="mt-4 text-sm font-medium">{name === "Documents" ? "Available" : "Not yet available"}</p></CardContent></Card>)}</div></section></main>
    </div></div>;
}
