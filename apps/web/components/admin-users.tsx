"use client";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, currentUser, deactivateUser, inviteUser, listUsers, reactivateUser, requestDeletionReview, updateUser, type ManagedUser, type UserIdentity } from "@/lib/api";
import { Button } from "@/components/ui/button";

const roles: UserIdentity["it_role"][] = ["NONE", "IT_DOC_ADMIN", "IT_EDITOR", "IT_MEMBER"];

export function AdminUsers() {
  const router = useRouter();
  const [users, setUsers] = useState<ManagedUser[]>([]);
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const load = () => listUsers().then(({ users }) => setUsers(users));
  function showError(error: unknown) { setMessage(error instanceof ApiError ? error.message : "Request failed"); }
  useEffect(() => { currentUser().then(user => { if (!user.is_app_admin) router.replace("/dashboard"); else load().catch(error => setMessage(error instanceof ApiError ? error.message : "Request failed")); }).catch(() => router.replace("/login")); }, [router]);
  async function run(action: () => Promise<unknown>, success: string) { setBusy(true); setMessage(""); try { await action(); await load(); setMessage(success); } catch (error) { showError(error); } finally { setBusy(false); } }
  async function invite(event: FormEvent) { event.preventDefault(); await run(() => inviteUser(email, "IT_MEMBER", false), "Invitation created"); setEmail(""); }
  return <main className="mx-auto max-w-6xl p-6 lg:p-10"><div className="flex items-center justify-between"><div><h1 className="text-3xl font-bold">User administration</h1><p className="mt-2 text-slate-600">Invite users and manage approved lifecycle actions.</p></div><Button variant="outline" onClick={() => router.push("/dashboard")}>Dashboard</Button></div>
    {message && <p role="status" className="mt-4 rounded border p-3">{message}</p>}
    <form onSubmit={invite} className="mt-8 flex gap-3"><label className="sr-only" htmlFor="invite-email">Email</label><input id="invite-email" type="email" required value={email} onChange={e => setEmail(e.target.value)} className="flex-1 rounded border px-3" placeholder="user@example.test"/><Button disabled={busy}>Invite user</Button></form>
    <div className="mt-8 overflow-x-auto"><table className="w-full border-collapse text-left text-sm"><thead><tr className="border-b"><th className="p-3">User</th><th className="p-3">Role</th><th className="p-3">App Admin</th><th className="p-3">State</th><th className="p-3">Actions</th></tr></thead><tbody>{users.map(user => <tr key={user.id} className="border-b"><td className="p-3">{user.email}</td><td className="p-3"><select aria-label={`Role for ${user.email}`} value={user.it_role} disabled={busy} onChange={e => run(() => updateUser(user.id, { it_role: e.target.value as UserIdentity["it_role"], is_app_admin: user.is_app_admin }), "Role updated")} className="rounded border p-2">{roles.map(role => <option key={role}>{role}</option>)}</select></td><td className="p-3"><input aria-label={`App Admin for ${user.email}`} type="checkbox" checked={user.is_app_admin} disabled={busy} onChange={e => run(() => updateUser(user.id, { it_role: user.it_role, is_app_admin: e.target.checked }), "Admin access updated")}/></td><td className="p-3">{user.lifecycle_status}</td><td className="p-3"><div className="flex flex-wrap gap-2">{user.lifecycle_status === "active" ? <Button disabled={busy} variant="outline" onClick={() => confirm(`Deactivate ${user.email}? All sessions will end.`) && run(() => deactivateUser(user.id), "User deactivated")}>Deactivate</Button> : user.lifecycle_status === "deactivated" ? <Button disabled={busy} variant="outline" onClick={() => confirm(`Reactivate ${user.email}? They must log in again.`) && run(() => reactivateUser(user.id), "User reactivated")}>Reactivate</Button> : null}<Button disabled={busy || user.lifecycle_status === "pending_invitation"} variant="outline" onClick={() => confirm(`Request deletion review for ${user.email}? This does not delete the account.`) && run(() => requestDeletionReview(user.id, "NO_LONGER_NEEDED"), "Deletion review requested")}>Request deletion review</Button></div></td></tr>)}</tbody></table></div>
  </main>;
}
