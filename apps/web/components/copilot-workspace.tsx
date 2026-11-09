"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Menu, Plus, RefreshCw, Trash2, X } from "lucide-react";
import {
  ApiError, createCopilotConversation, currentUser, deleteCopilotConversation,
  getCopilotConversation, listCopilotConversations, submitCopilotQuestion,
  type CopilotConversation, type CopilotMessage,
} from "@/lib/api";
import { Button } from "@/components/ui/button";

const MAX_QUESTION = 2000;

function Result({ message }: { message: CopilotMessage }) {
  if (message.role === "user") return <div className="ml-auto max-w-2xl rounded-2xl rounded-br-sm bg-slate-900 px-4 py-3 text-white"><p className="whitespace-pre-wrap break-words">{message.content}</p></div>;
  if (message.grounding_status === "references") return <article className="max-w-2xl rounded-2xl rounded-bl-sm border bg-white p-4"><p className="font-medium">Relevant authorized documents were found</p><p className="mt-1 text-sm text-slate-600">AI-generated synthesis is not enabled. These references are evidence sources, not proof of a specific answer.</p><ul aria-label="Authorized references" className="mt-3 space-y-2">{message.citations.map(citation => <li key={citation.id} className="rounded bg-slate-50 p-3"><span className="font-medium">{citation.label}</span><span className="ml-2 text-sm text-slate-600">Version {citation.version_sequence}</span></li>)}</ul></article>;
  if (message.grounding_status === "insufficient") return <article className="max-w-2xl rounded-2xl rounded-bl-sm border bg-white p-4"><p className="font-medium">Insufficient authorized documentation</p><p className="mt-1 text-sm text-slate-600">No relevant authorized source was found. No ungrounded troubleshooting response was generated.</p></article>;
  return <div className="max-w-2xl rounded-2xl rounded-bl-sm border bg-white px-4 py-3"><p className="whitespace-pre-wrap break-words">{message.content}</p></div>;
}

export function CopilotWorkspace() {
  const router = useRouter();
  const [conversations, setConversations] = useState<CopilotConversation[]>([]);
  const [selected, setSelected] = useState<CopilotConversation | null>(null);
  const [messages, setMessages] = useState<CopilotMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(true); const [submitting, setSubmitting] = useState(false);
  const [notice, setNotice] = useState(""); const [sidebarOpen, setSidebarOpen] = useState(false);
  const composer = useRef<HTMLTextAreaElement>(null);

  function handleError(error: unknown, fallback = "Request could not be completed") {
    if (error instanceof ApiError && error.status === 401) { router.replace("/login"); return; }
    setNotice(error instanceof ApiError ? error.message : fallback);
  }
  async function loadList() { const result = await listCopilotConversations(); setConversations(result.conversations); return result.conversations; }
  async function selectConversation(item: CopilotConversation) {
    setNotice(""); setLoading(true);
    try { const detail = await getCopilotConversation(item.id); setSelected(detail.conversation); setMessages(detail.messages); setSidebarOpen(false); }
    catch (error) { if (error instanceof ApiError && error.status === 404) { setSelected(null); setMessages([]); await loadList().catch(() => undefined); setNotice("That conversation is no longer available."); } else handleError(error); }
    finally { setLoading(false); }
  }
  useEffect(() => { let active = true; currentUser().then(() => loadList()).then(items => { if (active && items[0]) return selectConversation(items[0]); }).catch(handleError).finally(() => { if (active) setLoading(false); }); return () => { active = false; }; }, []); // eslint-disable-line react-hooks/exhaustive-deps
  async function createNew() { setNotice(""); try { const item = await createCopilotConversation(); await loadList(); setSelected(item); setMessages([]); setSidebarOpen(false); composer.current?.focus(); } catch (error) { handleError(error); } }
  async function removeSelected() { if (!selected || !window.confirm(`Delete “${selected.title}”? This cannot be undone.`)) return; try { await deleteCopilotConversation(selected.id); const items = await loadList(); setSelected(null); setMessages([]); if (items[0]) await selectConversation(items[0]); } catch (error) { if (error instanceof ApiError && error.status === 404) { await loadList(); setSelected(null); setMessages([]); setNotice("That conversation is no longer available."); } else handleError(error); } }
  async function submit(event: FormEvent) {
    event.preventDefault(); const normalized = question.trim();
    if (!selected || !normalized || normalized.length > MAX_QUESTION || submitting) return;
    setSubmitting(true); setNotice("");
    try { const result = await submitCopilotQuestion(selected.id, normalized); setQuestion(""); setSelected(result.conversation); setMessages(current => [...current, result.user_message, result.assistant_message]); await loadList(); }
    catch (error) {
      // A timeout can occur after the server commits. Refresh before offering a retry.
      try { const detail = await getCopilotConversation(selected.id); setSelected(detail.conversation); setMessages(detail.messages); setNotice("Submission status was uncertain. The conversation was refreshed; review it before retrying."); }
      catch (refreshError) { if (refreshError instanceof ApiError && refreshError.status === 404) { setSelected(null); setMessages([]); await loadList().catch(() => undefined); setNotice("That conversation is no longer available."); } else handleError(error, "Submission failed; your question was preserved."); }
    } finally { setSubmitting(false); composer.current?.focus(); }
  }
  return <div className="min-h-screen bg-slate-100 lg:grid lg:grid-cols-[320px_1fr]">
    <Button variant="outline" className="fixed left-4 top-4 z-30 bg-white lg:hidden" aria-label="Open conversations" onClick={() => setSidebarOpen(true)}><Menu aria-hidden="true" /></Button>
    {sidebarOpen && <button aria-label="Close conversations" className="fixed inset-0 z-30 bg-slate-950/40 lg:hidden" onClick={() => setSidebarOpen(false)} />}
    <aside className={`${sidebarOpen ? "translate-x-0" : "-translate-x-full"} fixed inset-y-0 left-0 z-40 flex w-[min(88vw,320px)] flex-col border-r bg-white transition-transform lg:static lg:w-auto lg:translate-x-0`} aria-label="Conversations">
      <div className="flex items-center justify-between border-b p-4"><div><p className="font-semibold">Copilot</p><p className="text-xs text-slate-500">Authorized references only</p></div><Button variant="outline" className="lg:hidden" aria-label="Close conversations" onClick={() => setSidebarOpen(false)}><X aria-hidden="true" /></Button></div>
      <div className="p-4"><Button className="w-full gap-2" onClick={createNew}><Plus aria-hidden="true" size={18} />New conversation</Button></div>
      <nav className="min-h-0 flex-1 overflow-y-auto px-3" aria-label="Conversation history"><ul className="space-y-1">{conversations.map(item => <li key={item.id}><button className={`w-full truncate rounded-md px-3 py-3 text-left text-sm ${selected?.id === item.id ? "bg-slate-900 text-white" : "hover:bg-slate-100"}`} aria-current={selected?.id === item.id ? "page" : undefined} onClick={() => selectConversation(item)}>{item.title}</button></li>)}</ul>{!conversations.length && !loading && <p className="p-3 text-sm text-slate-500">Start a conversation to find authorized documentation.</p>}</nav>
      <div className="border-t p-4"><Button variant="outline" className="w-full" onClick={() => router.push("/dashboard")}>Back to dashboard</Button></div>
    </aside>
    <main className="flex min-h-screen min-w-0 flex-col">
      <header className="flex min-h-20 items-center justify-between gap-4 border-b bg-white px-16 py-4 lg:px-6"><div className="min-w-0"><h1 className="truncate text-lg font-semibold">{selected?.title ?? "Copilot workspace"}</h1><p className="text-sm text-slate-500">AI-generated synthesis is disabled</p></div><div className="flex gap-2"><Button variant="outline" aria-label="Refresh conversations" onClick={() => { loadList().then(items => selected ? selectConversation(selected) : items[0] ? selectConversation(items[0]) : undefined).catch(handleError); }}><RefreshCw aria-hidden="true" size={18} /></Button>{selected && <Button variant="outline" aria-label="Delete conversation" onClick={removeSelected}><Trash2 aria-hidden="true" size={18} /></Button>}</div></header>
      {notice && <p role="alert" className="m-4 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm">{notice}</p>}
      <section aria-label="Messages" aria-busy={loading} className="flex-1 overflow-y-auto p-4 lg:p-8"><div className="mx-auto max-w-4xl space-y-4">{loading && <p role="status" className="text-center text-slate-500">Loading conversation…</p>}{!loading && !selected && <div className="py-24 text-center"><h2 className="text-2xl font-semibold">Ask using authorized documentation</h2><p className="mx-auto mt-2 max-w-lg text-slate-600">Create a conversation to find relevant references. Generated answers are not enabled.</p><Button className="mt-6" onClick={createNew}>New conversation</Button></div>}{messages.map(message => <Result key={message.id} message={message} />)}</div></section>
      <form onSubmit={submit} className="border-t bg-white p-4"><div className="mx-auto max-w-4xl"><label htmlFor="copilot-question" className="sr-only">Question</label><textarea ref={composer} id="copilot-question" rows={3} maxLength={MAX_QUESTION} disabled={!selected || submitting} value={question} onChange={event => setQuestion(event.target.value)} onKeyDown={event => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} placeholder={selected ? "Ask a question about authorized IT documentation" : "Create or select a conversation"} className="w-full resize-none rounded-lg border p-3 focus:outline-none focus:ring-2 focus:ring-slate-900 disabled:bg-slate-100" /><div className="mt-2 flex items-center justify-between gap-4"><p className={`text-xs ${question.length >= MAX_QUESTION ? "text-red-700" : "text-slate-500"}`}>{question.length} / {MAX_QUESTION}</p><Button disabled={!selected || !question.trim() || question.length > MAX_QUESTION || submitting}>{submitting ? "Submitting…" : "Submit question"}</Button></div></div></form>
    </main>
  </div>;
}
