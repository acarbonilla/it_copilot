"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Copy, Eye, EyeOff, KeyRound, Pencil, Plus, RotateCcw, Trash2, X } from "lucide-react";
import {
  ApiError,
  createVaultCredential,
  currentUser,
  deleteVaultCredential,
  listDeletedVaultCredentials,
  listVaultCredentials,
  reauthenticateVault,
  restoreVaultCredential,
  revealVaultCredential,
  updateVaultCredential,
  type DeletedVaultCredential,
  type VaultCredential,
  type VaultCredentialInput,
  type VaultCredentialType,
  type VaultSecretFields,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const credentialTypes: { value: VaultCredentialType; label: string }[] = [
  { value: "LOGIN", label: "Login" },
  { value: "API_TOKEN", label: "API token" },
  { value: "SSH_KEY", label: "SSH key" },
  { value: "GENERIC_SECRET", label: "Generic secret" },
];

const secretContracts: Record<VaultCredentialType, { name: string; label: string; required?: boolean; multiline?: boolean }[]> = {
  LOGIN: [{ name: "username", label: "Username" }, { name: "password", label: "Password", required: true }, { name: "notes", label: "Notes", multiline: true }],
  API_TOKEN: [{ name: "token_identifier", label: "Token identifier" }, { name: "token", label: "Token", required: true, multiline: true }, { name: "notes", label: "Notes", multiline: true }],
  SSH_KEY: [{ name: "private_key", label: "Private key", required: true, multiline: true }, { name: "passphrase", label: "Passphrase" }, { name: "notes", label: "Notes", multiline: true }],
  GENERIC_SECRET: [{ name: "account_identifier", label: "Account identifier" }, { name: "secret", label: "Secret", required: true, multiline: true }, { name: "notes", label: "Notes", multiline: true }],
};

type VaultUpdateInput = { metadata: { label: string; service_label?: string; origin?: string }; secretFields?: VaultSecretFields };
type PendingAction =
  | { kind: "reveal"; title: string; id: string; run: (grant: string) => Promise<VaultSecretFields> }
  | { kind: "mutation"; title: string; run: (grant: string) => Promise<unknown>; success: string; closeEditor?: boolean };
type EditorState = { mode: "create"; type: VaultCredentialType } | { mode: "edit"; item: VaultCredential };

function friendlyError(error: unknown) {
  if (!(error instanceof ApiError)) return "The vault request could not be completed.";
  if (error.status === 401) return "Your session has ended. Sign in again.";
  if (error.code === "invalid_grant") return "Authorization expired or was already used. Reauthenticate and try again.";
  if (error.code === "conflict") return "This credential changed. Refresh the list and try again.";
  if (error.code === "reauthentication_failed") return error.status === 429 ? "Too many attempts. Wait before trying again." : "Reauthentication failed.";
  if (error.code === "credential_unavailable") return "The credential is unavailable.";
  return error.message || "The vault request could not be completed.";
}

function typeLabel(type: VaultCredentialType) {
  return credentialTypes.find(item => item.value === type)?.label ?? type;
}

export function VaultManager() {
  const router = useRouter();
  const [initialization, setInitialization] = useState<"loading" | "ready" | "error">("loading");
  const [initializationError, setInitializationError] = useState("");
  const [initializationAttempt, setInitializationAttempt] = useState(0);
  const [tab, setTab] = useState<"active" | "deleted">("active");
  const [active, setActive] = useState<VaultCredential[]>([]);
  const [deleted, setDeleted] = useState<DeletedVaultCredential[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [cursor, setCursor] = useState<string | undefined>();
  const [cursorHistory, setCursorHistory] = useState<(string | undefined)[]>([]);
  const [filterType, setFilterType] = useState<VaultCredentialType | "">("");
  const [prefix, setPrefix] = useState("");
  const [editor, setEditor] = useState<EditorState | null>(null);
  const [pending, setPending] = useState<PendingAction | null>(null);
  const [revealed, setRevealed] = useState<{ id: string; fields: VaultSecretFields } | null>(null);
  const [showPlaintext, setShowPlaintext] = useState(false);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [listLoading, setListLoading] = useState(false);
  const [listError, setListError] = useState("");
  const generation = useRef(0);
  const listGeneration = useRef(0);
  const paginationInFlight = useRef(false);
  const authorizationInFlight = useRef(false);
  const revealTimer = useRef<number | null>(null);
  const copiedValues = useRef(new Set<string>());

  const clearSensitive = useCallback(() => {
    generation.current += 1;
    authorizationInFlight.current = false;
    setBusy(false);
    setRevealed(null);
    setShowPlaintext(false);
    setPending(null);
    setEditor(null);
    if (revealTimer.current !== null) window.clearTimeout(revealTimer.current);
    revealTimer.current = null;
    copiedValues.current.forEach(value => { void clearClipboardIfUnchanged(value); });
    copiedValues.current.clear();
  }, []);

  const handleError = useCallback((error: unknown) => {
    clearSensitive();
    setMessage(friendlyError(error));
    if (error instanceof ApiError && error.status === 401) router.replace("/login");
  }, [clearSensitive, router]);

  const load = useCallback(async () => {
    const marker = ++listGeneration.current;
    setListLoading(true);
    setListError("");
    try {
      if (tab === "active") {
        const result = await listVaultCredentials({ cursor, type: filterType, prefix: prefix.trim(), limit: 25 });
        if (marker !== listGeneration.current) return;
        setActive(result.credentials);
        setNextCursor(result.nextCursor);
      } else {
        const result = await listDeletedVaultCredentials(cursor, 25);
        if (marker !== listGeneration.current) return;
        setDeleted(result.credentials);
        setNextCursor(result.nextCursor);
      }
    } catch (error) {
      if (marker !== listGeneration.current) return;
      setListError(friendlyError(error));
      if (error instanceof ApiError && error.status === 401) router.replace("/login");
    } finally {
      if (marker === listGeneration.current) {
        paginationInFlight.current = false;
        setListLoading(false);
      }
    }
  }, [cursor, filterType, prefix, router, tab]);

  useEffect(() => {
    let cancelled = false;
    currentUser().then(() => {
      if (!cancelled) {
        setInitializationError("");
        setInitialization("ready");
      }
    }).catch(error => {
      if (cancelled) return;
      if (error instanceof ApiError && error.status === 401) {
        handleError(error);
        return;
      }
      setInitializationError(friendlyError(error));
      setInitialization("error");
    });
    return () => { cancelled = true; clearSensitive(); };
  }, [clearSensitive, handleError, initializationAttempt]);

  useEffect(() => {
    if (initialization !== "ready") return;
    const timer = window.setTimeout(() => { void load(); }, 0);
    return () => { window.clearTimeout(timer); listGeneration.current += 1; };
  }, [initialization, load]);

  useEffect(() => {
    function hide() { if (document.visibilityState !== "visible") clearSensitive(); }
    function pageHide() { clearSensitive(); }
    document.addEventListener("visibilitychange", hide);
    window.addEventListener("pagehide", pageHide);
    return () => { document.removeEventListener("visibilitychange", hide); window.removeEventListener("pagehide", pageHide); };
  }, [clearSensitive]);

  function switchTab(next: "active" | "deleted") {
    clearSensitive();
    setTab(next); setCursor(undefined); setCursorHistory([]); setNextCursor(null); setMessage("");
  }

  function nextPage() {
    if (listLoading || paginationInFlight.current || !nextCursor) return;
    paginationInFlight.current = true;
    setListLoading(true);
    setCursorHistory(history => [...history, cursor]);
    setCursor(nextCursor);
  }

  function previousPage() {
    if (listLoading || paginationInFlight.current || !cursorHistory.length) return;
    paginationInFlight.current = true;
    setListLoading(true);
    const history = [...cursorHistory];
    setCursor(history.pop());
    setCursorHistory(history);
  }

  function requireGrant(action: PendingAction) {
    clearSensitive();
    setPending(action);
  }

  function showReveal(id: string, fields: VaultSecretFields) {
    setPending(null);
    setRevealed({ id, fields: { ...fields } });
    setShowPlaintext(false);
    revealTimer.current = window.setTimeout(clearSensitive, 30_000);
  }

  async function copySecret(value: string) {
    if (!window.isSecureContext || !navigator.clipboard?.writeText) {
      setMessage("Clipboard access requires a secure browser context. Select and copy the value manually.");
      return;
    }
    try {
      await navigator.clipboard.writeText(value);
      copiedValues.current.add(value);
      setMessage("Copied. The app will try to clear this clipboard value in 30 seconds.");
      window.setTimeout(() => { copiedValues.current.delete(value); void clearClipboardIfUnchanged(value); }, 30_000);
    } catch { setMessage("Clipboard access was denied. Select and copy the value manually."); }
  }

  if (initialization === "loading") return <main className="grid min-h-screen place-items-center"><p role="status">Loading your vault…</p></main>;
  if (initialization === "error") return <main className="grid min-h-screen place-items-center p-6"><div role="alert" className="max-w-md rounded-lg border border-red-200 bg-red-50 p-6 text-red-900"><h1 className="text-xl font-semibold">Unable to open your vault</h1><p className="mt-2 text-sm">{initializationError}</p><Button className="mt-4" onClick={() => { setInitialization("loading"); setInitializationError(""); setInitializationAttempt(value => value + 1); }}>Try again</Button></div></main>;

  return <main className="mx-auto max-w-6xl p-6 lg:p-10">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div><div className="flex items-center gap-3"><KeyRound aria-hidden="true" /><h1 className="text-3xl font-bold">My Credentials</h1></div><p className="mt-2 text-slate-600">Private credentials protected by password reauthentication.</p></div>
      <div className="flex gap-2"><Button variant="outline" onClick={() => { clearSensitive(); router.push("/dashboard"); }}>Dashboard</Button><Button onClick={() => setEditor({ mode: "create", type: "LOGIN" })}><Plus size={16} aria-hidden="true" /> Add credential</Button></div>
    </div>

    <div role="tablist" aria-label="Credential lifecycle" className="mt-8 flex gap-2 border-b">
      <button role="tab" aria-selected={tab === "active"} className={`px-4 py-3 text-sm font-medium ${tab === "active" ? "border-b-2 border-slate-950" : "text-slate-500"}`} onClick={() => switchTab("active")}>Active</button>
      <button role="tab" aria-selected={tab === "deleted"} className={`px-4 py-3 text-sm font-medium ${tab === "deleted" ? "border-b-2 border-slate-950" : "text-slate-500"}`} onClick={() => switchTab("deleted")}>Deleted</button>
    </div>

    {message && <p role="status" className="mt-4 rounded-md border bg-white p-3 text-sm">{message}</p>}
    {tab === "active" && <div className="mt-5 flex flex-wrap gap-3 rounded-lg border bg-white p-4">
      <label className="text-sm">Type<select aria-label="Credential type filter" value={filterType} onChange={e => { setFilterType(e.target.value as VaultCredentialType | ""); setCursor(undefined); setCursorHistory([]); }} className="ml-2 rounded-md border p-2"><option value="">All types</option>{credentialTypes.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
      <label className="text-sm">Label prefix<Input aria-label="Label prefix" maxLength={120} value={prefix} onChange={e => { setPrefix(e.target.value); setCursor(undefined); setCursorHistory([]); }} className="ml-2 inline-block w-56" /></label>
    </div>}

    <section aria-live="polite" className="mt-6 grid gap-4">
      {(tab === "active" ? active : deleted).map(item => <article key={item.id} className="rounded-lg border bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-xs font-medium uppercase tracking-wide text-slate-500">{typeLabel(item.credential_type)}</p><h2 className="mt-1 font-semibold">{item.label}</h2>{item.service_label && <p className="text-sm text-slate-600">{item.service_label}</p>}{item.origin && <p className="break-all text-sm text-slate-600">{item.origin}</p>}{tab === "deleted" && <p className="mt-2 text-xs text-slate-500">Restore window ends {new Date((item as DeletedVaultCredential).restorationExpiresAt).toLocaleString()}</p>}</div>
          <div className="flex flex-wrap gap-2">{tab === "active" ? <>
            <Button variant="outline" disabled={busy} onClick={() => requireGrant({ kind: "reveal", title: `Reveal ${item.label}`, id: item.id, run: grant => revealVaultCredential(item.id, grant) })}><Eye size={16} aria-hidden="true" /> Reveal</Button>
            <Button variant="outline" disabled={busy} onClick={() => setEditor({ mode: "edit", item: item as VaultCredential })}><Pencil size={16} aria-hidden="true" /> Edit</Button>
            <Button variant="outline" disabled={busy} onClick={() => { if (window.confirm(`Delete ${item.label}? It can be restored only during its retention window.`)) requireGrant({ kind: "mutation", title: `Delete ${item.label}`, run: grant => deleteVaultCredential(item as VaultCredential, grant), success: "Credential deleted." }); }}><Trash2 size={16} aria-hidden="true" /> Delete</Button>
          </> : <Button variant="outline" disabled={busy || !(item as DeletedVaultCredential).restorationEligible} onClick={() => requireGrant({ kind: "mutation", title: `Restore ${item.label}`, run: grant => restoreVaultCredential(item as DeletedVaultCredential, grant), success: "Credential restored." })}><RotateCcw size={16} aria-hidden="true" /> {(item as DeletedVaultCredential).restorationEligible ? "Restore" : "Restore unavailable"}</Button>}</div>
        </div>
      </article>)}
      {listLoading && <p role="status" className="py-12 text-center text-slate-600">Loading {tab} credentials…</p>}
      {!listLoading && listError && <div role="alert" className="rounded-md border border-red-200 bg-red-50 p-4 text-red-800"><p>{listError}</p><Button variant="outline" className="mt-3" onClick={() => void load()}>Try again</Button></div>}
      {!listLoading && !listError && !(tab === "active" ? active : deleted).length && <p className="py-12 text-center text-slate-600">No {tab} credentials found.</p>}
    </section>

    <nav aria-label="Vault pagination" className="mt-6 flex items-center justify-between"><Button variant="outline" disabled={listLoading || !cursorHistory.length} onClick={previousPage}>Previous</Button><span className="text-sm text-slate-600">Page {cursorHistory.length + 1}</span><Button variant="outline" disabled={listLoading || !nextCursor} onClick={nextPage}>Next</Button></nav>

    {editor && <CredentialEditor state={editor} busy={busy} onClose={() => setEditor(null)} onSubmit={(input, item) => {
      if (item) requireGrant({ kind: "mutation", title: `Update ${item.label}`, run: grant => updateVaultCredential(item, input as VaultUpdateInput, grant), success: "Credential updated.", closeEditor: true });
      else requireGrant({ kind: "mutation", title: "Create credential", run: grant => createVaultCredential(input as VaultCredentialInput, grant), success: "Credential created.", closeEditor: true });
    }} />}
    {pending && <ReauthenticationDialog title={pending.title} busy={busy} onCancel={clearSensitive} onAuthorize={async password => {
      if (authorizationInFlight.current) return;
      authorizationInFlight.current = true;
      setBusy(true);
      setMessage("");
      const action = pending;
      const marker = generation.current;
      try {
        const { grant } = await reauthenticateVault(password);
        if (marker !== generation.current) return;
        const result = await action.run(grant);
        if (marker !== generation.current) return;
        if (action.kind === "reveal") showReveal(action.id, result as VaultSecretFields);
        else {
          if (action.closeEditor) setEditor(null);
          setPending(null);
          setMessage(action.success);
          await load();
        }
      } catch (error) {
        if (marker === generation.current) handleError(error);
      } finally {
        if (marker === generation.current) {
          authorizationInFlight.current = false;
          setBusy(false);
        }
      }
    }} />}
    {revealed && <RevealPanel label={active.find(item => item.id === revealed.id)?.label ?? "Credential"} fields={revealed.fields} visible={showPlaintext} onToggle={() => setShowPlaintext(value => !value)} onCopy={copySecret} onClose={clearSensitive} />}
  </main>;
}

async function clearClipboardIfUnchanged(value: string) {
  if (!window.isSecureContext || !navigator.clipboard?.readText || !navigator.clipboard?.writeText) return;
  try { if (await navigator.clipboard.readText() === value) await navigator.clipboard.writeText(""); } catch { /* Browsers may deny clipboard reads; cleanup is best effort. */ }
}

function ReauthenticationDialog({ title, busy, onCancel, onAuthorize }: { title: string; busy: boolean; onCancel: () => void; onAuthorize: (password: string) => Promise<void> }) {
  const [password, setPassword] = useState("");
  const priorFocus = useRef<HTMLElement | null>(null);
  const submitted = useRef(false);
  useEffect(() => { priorFocus.current = document.activeElement as HTMLElement; return () => priorFocus.current?.focus(); }, []);
  async function submit(event: FormEvent) { event.preventDefault(); if (submitted.current || !password) return; submitted.current = true; const supplied = password; setPassword(""); await onAuthorize(supplied); }
  return <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/60 p-4" role="presentation" onKeyDown={event => { if (event.key === "Escape" && !busy) onCancel(); }}><form role="dialog" aria-modal="true" aria-labelledby="reauth-title" onSubmit={submit} className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl"><div className="flex items-start justify-between"><div><h2 id="reauth-title" className="text-lg font-semibold">Reauthenticate to continue</h2><p className="mt-1 text-sm text-slate-600">{title}. Enter your current account password.</p></div><Button type="button" variant="ghost" aria-label="Close" disabled={busy} onClick={onCancel}><X aria-hidden="true" /></Button></div><label className="mt-5 block text-sm font-medium">Password<Input autoFocus required autoComplete="current-password" type="password" value={password} onChange={event => setPassword(event.target.value)} className="mt-1" /></label><p className="mt-3 text-xs text-slate-500">Authorization is valid for one sensitive operation and is never stored by this page.</p><div className="mt-5 flex justify-end gap-2"><Button type="button" variant="outline" disabled={busy} onClick={onCancel}>Cancel</Button><Button disabled={busy || !password}>{busy ? "Authorizing…" : "Authorize once"}</Button></div></form></div>;
}

function CredentialEditor({ state, busy, onClose, onSubmit }: { state: EditorState; busy: boolean; onClose: () => void; onSubmit: (input: VaultCredentialInput | VaultUpdateInput, item?: VaultCredential) => void }) {
  const item = state.mode === "edit" ? state.item : undefined;
  const [type, setType] = useState<VaultCredentialType>(state.mode === "create" ? state.type : state.item.credential_type);
  const [label, setLabel] = useState(item?.label ?? ""); const [service, setService] = useState(item?.service_label ?? ""); const [origin, setOrigin] = useState(item?.origin ?? ""); const [secrets, setSecrets] = useState<VaultSecretFields>({});
  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (type !== "LOGIN") setOrigin("");
      if (type !== "LOGIN" && type !== "API_TOKEN") setService("");
    }, 0);
    return () => window.clearTimeout(timer);
  }, [type]);
  function submit(event: FormEvent) {
    event.preventDefault();
    const secretFields = Object.fromEntries(Object.entries(secrets).filter(([, value]) => value !== ""));
    if (item) {
      const metadata = type === "LOGIN" ? { label, service_label: service, origin } : type === "API_TOKEN" ? { label, service_label: service } : { label };
      onSubmit({ metadata, ...(Object.keys(secretFields).length ? { secretFields } : {}) }, item);
    } else {
      const metadata = type === "LOGIN" ? { serviceLabel: service, origin } : type === "API_TOKEN" ? { serviceLabel: service } : {};
      onSubmit({ credentialType: type, label, ...metadata, secretFields });
    }
  }
  return <div className="fixed inset-0 z-40 grid place-items-center overflow-y-auto bg-slate-950/60 p-4"><form role="dialog" aria-modal="true" aria-labelledby="editor-title" onSubmit={submit} className="my-8 w-full max-w-2xl rounded-lg bg-white p-6 shadow-xl"><div className="flex justify-between"><div><h2 id="editor-title" className="text-xl font-semibold">{item ? "Edit credential" : "Add credential"}</h2><p className="mt-1 text-sm text-slate-600">{item ? "Leave secret fields blank to keep their current values." : "All secret values are encrypted by the vault service."}</p></div><Button type="button" variant="ghost" aria-label="Close" onClick={onClose}><X /></Button></div><div className="mt-5 grid gap-4 md:grid-cols-2"><label className="text-sm font-medium">Type<select disabled={!!item} value={type} onChange={e => { setType(e.target.value as VaultCredentialType); setSecrets({}); }} className="mt-1 w-full rounded-md border p-2.5">{credentialTypes.map(entry => <option key={entry.value} value={entry.value}>{entry.label}</option>)}</select></label><label className="text-sm font-medium">Label<Input required maxLength={120} value={label} onChange={e => setLabel(e.target.value)} className="mt-1" /></label>{(type === "LOGIN" || type === "API_TOKEN") && <label className="text-sm font-medium">Service label<Input maxLength={120} value={service} onChange={e => setService(e.target.value)} className="mt-1" /></label>}{type === "LOGIN" && <label className="text-sm font-medium">HTTPS origin<Input type="url" placeholder="https://example.com" value={origin} onChange={e => setOrigin(e.target.value)} className="mt-1" /></label>}{secretContracts[type].map(field => <label key={field.name} className={`text-sm font-medium ${field.multiline ? "md:col-span-2" : ""}`}>{field.label}{field.multiline ? <textarea required={!item && field.required} maxLength={field.name === "private_key" ? 65536 : field.name === "notes" ? 8192 : 32768} value={secrets[field.name] ?? ""} onChange={e => setSecrets(value => ({ ...value, [field.name]: e.target.value }))} className="mt-1 min-h-24 w-full rounded-md border p-2" /> : <Input required={!item && field.required} type={["password", "passphrase", "secret", "token"].includes(field.name) ? "password" : "text"} value={secrets[field.name] ?? ""} onChange={e => setSecrets(value => ({ ...value, [field.name]: e.target.value }))} className="mt-1" />}</label>)}</div><div className="mt-6 flex justify-end gap-2"><Button type="button" variant="outline" onClick={onClose}>Cancel</Button><Button disabled={busy}>{item ? "Continue to reauthentication" : "Continue to reauthentication"}</Button></div></form></div>;
}

function RevealPanel({ label, fields, visible, onToggle, onCopy, onClose }: { label: string; fields: VaultSecretFields; visible: boolean; onToggle: () => void; onCopy: (value: string) => void; onClose: () => void }) {
  return <aside role="dialog" aria-modal="true" aria-labelledby="reveal-title" className="fixed inset-x-4 bottom-4 z-40 mx-auto max-w-2xl rounded-lg border bg-white p-5 shadow-2xl"><div className="flex items-start justify-between"><div><h2 id="reveal-title" className="font-semibold">{label}</h2><p className="text-xs text-slate-500">Plaintext clears in 30 seconds or when this page is hidden.</p></div><Button variant="ghost" aria-label="Close revealed credential" onClick={onClose}><X /></Button></div><dl className="mt-4 grid gap-3">{Object.entries(fields).map(([name, value]) => <div key={name} className="rounded-md bg-slate-50 p-3"><dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{name.replaceAll("_", " ")}</dt><dd className="mt-1 flex items-start justify-between gap-3"><code className="max-h-40 overflow-auto whitespace-pre-wrap break-all text-sm">{visible ? value : "•".repeat(Math.min(Math.max(value.length, 8), 24))}</code><Button variant="outline" size="sm" onClick={() => onCopy(value)}><Copy size={14} /> Copy</Button></dd></div>)}</dl><Button variant="outline" className="mt-4" onClick={onToggle}>{visible ? <EyeOff size={16} /> : <Eye size={16} />} {visible ? "Mask values" : "Show values"}</Button></aside>;
}
