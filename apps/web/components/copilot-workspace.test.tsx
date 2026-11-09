import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CopilotWorkspace } from "./copilot-workspace";
import * as api from "@/lib/api";

const replace = vi.fn(); const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace, push }) }));
const member = { id: 1, email: "member@example.test", is_app_admin: false, it_role: "IT_MEMBER" } as const;
const conversation: api.CopilotConversation = { id: "11111111-1111-4111-8111-111111111111", title: "Reset access", created_at: "2026-11-01T00:00:00Z", updated_at: "2026-11-01T00:00:00Z", last_activity_at: "2026-11-01T00:00:00Z", retention_expires_at: "2026-12-01T00:00:00Z" };
const secondConversation: api.CopilotConversation = { ...conversation, id: "22222222-2222-4222-8222-222222222222", title: "Network access" };
const userMessage: api.CopilotMessage = { id: "u1", role: "user", content: "How do I reset access?", grounding_status: "not_applicable", provider_status: "not_applicable", citations: [], created_at: "2026-11-01T00:00:01Z" };
const secondMessage: api.CopilotMessage = { ...userMessage, id: "u2", content: "Network conversation" };
const referenceMessage: api.CopilotMessage = { id: "a1", role: "assistant", content: "", grounding_status: "references", provider_status: "disabled", citations: [{ id: "cite_safe", document_id: "doc", version_id: "version", label: "Reset guide", version_sequence: 3 }], created_at: "2026-11-01T00:00:02Z" };
const emptyPage = { conversations: [], pagination: { page: 1, page_size: 25, count: 0, total_pages: 0 } };
const page = { ...emptyPage, conversations: [conversation], pagination: { ...emptyPage.pagination, count: 1, total_pages: 1 } };

function deferred<T>() {
  let resolve!: (value: T) => void; let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => { resolve = resolvePromise; reject = rejectPromise; });
  return { promise, resolve, reject };
}

function setup(messages: api.CopilotMessage[] = []) {
  vi.spyOn(api, "currentUser").mockResolvedValue(member);
  vi.spyOn(api, "listCopilotConversations").mockResolvedValue(page);
  vi.spyOn(api, "getCopilotConversation").mockResolvedValue({ conversation, messages });
}

describe("CopilotWorkspace", () => {
  beforeEach(() => { vi.restoreAllMocks(); replace.mockReset(); push.mockReset(); });

  it("protects the workspace and redirects an anonymous session", async () => {
    vi.spyOn(api, "currentUser").mockRejectedValue(new api.ApiError(401, "authentication_required", "Required"));
    vi.spyOn(api, "listCopilotConversations"); render(<CopilotWorkspace />);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
  });

  it("lists, selects, and renders safe reference-only metadata", async () => {
    setup([userMessage, referenceMessage]); render(<CopilotWorkspace />);
    expect(await screen.findByText("How do I reset access?")).toBeVisible();
    expect(screen.getByText("Relevant authorized documents were found")).toBeVisible();
    expect(screen.getByText("Reset guide")).toBeVisible(); expect(screen.getByText("Version 3")).toBeVisible();
    expect(screen.queryByText("doc")).not.toBeInTheDocument(); expect(screen.queryByRole("link", { name: /Reset guide/ })).not.toBeInTheDocument();
    expect(screen.getByText(/AI-generated synthesis is not enabled/)).toBeVisible();
  });

  it("creates a conversation and enables the validated composer", async () => {
    vi.spyOn(api, "currentUser").mockResolvedValue(member); vi.spyOn(api, "listCopilotConversations").mockResolvedValue(emptyPage);
    vi.spyOn(api, "createCopilotConversation").mockResolvedValue(conversation); render(<CopilotWorkspace />);
    await userEvent.click(await screen.findByRole("button", { name: "New conversation" }));
    expect(api.createCopilotConversation).toHaveBeenCalled(); expect(screen.getByPlaceholderText(/Ask a question/)).toBeEnabled();
  });

  it("submits with Enter once and shows insufficient evidence without advice", async () => {
    setup(); const insufficient = { ...referenceMessage, id: "a2", grounding_status: "insufficient" as const, citations: [] };
    const submit = vi.spyOn(api, "submitCopilotQuestion").mockResolvedValue({ conversation, user_message: userMessage, assistant_message: insufficient });
    render(<CopilotWorkspace />); const input = await screen.findByPlaceholderText(/Ask a question/);
    await userEvent.type(input, "How do I reset access?{Enter}");
    await waitFor(() => expect(submit).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("Insufficient authorized documentation")).toBeVisible();
    expect(screen.getByText(/No ungrounded troubleshooting response/)).toBeVisible();
  });

  it("refreshes after an uncertain failure and preserves the typed question", async () => {
    setup(); vi.spyOn(api, "submitCopilotQuestion").mockRejectedValue(new api.ApiError(0, "network_error", "Offline")); render(<CopilotWorkspace />);
    const input = await screen.findByPlaceholderText(/Ask a question/); await userEvent.type(input, "Keep this question"); await userEvent.click(screen.getByRole("button", { name: "Submit question" }));
    expect(await screen.findByText(/conversation was refreshed/i)).toBeVisible(); expect(input).toHaveValue("Keep this question");
    expect(api.getCopilotConversation).toHaveBeenCalledTimes(2);
  });

  it("requires confirmation for deletion and handles expired not-found safely", async () => {
    setup(); const remove = vi.spyOn(api, "deleteCopilotConversation").mockRejectedValue(new api.ApiError(404, "not_found", "Conversation not found"));
    vi.spyOn(window, "confirm").mockReturnValue(true); render(<CopilotWorkspace />);
    await userEvent.click(await screen.findByRole("button", { name: "Delete conversation" }));
    await waitFor(() => expect(remove).toHaveBeenCalledWith(conversation.id)); expect(await screen.findByText(/no longer available/i)).toBeVisible();
  });

  it("ignores out-of-order detail responses and stale selection errors", async () => {
    const oldRequest = deferred<api.CopilotConversationDetail>(); const latestRequest = deferred<api.CopilotConversationDetail>();
    vi.spyOn(api, "currentUser").mockResolvedValue(member);
    vi.spyOn(api, "listCopilotConversations").mockResolvedValue({ ...page, conversations: [conversation, secondConversation], pagination: { ...page.pagination, count: 2 } });
    vi.spyOn(api, "getCopilotConversation")
      .mockResolvedValueOnce({ conversation, messages: [userMessage] })
      .mockImplementationOnce(() => oldRequest.promise)
      .mockImplementationOnce(() => latestRequest.promise);
    render(<CopilotWorkspace />); await screen.findByText("How do I reset access?");
    await userEvent.click(screen.getByRole("button", { name: "Network access" }));
    await userEvent.click(screen.getByRole("button", { name: "Reset access" }));
    latestRequest.resolve({ conversation, messages: [userMessage] });
    expect(await screen.findByText("How do I reset access?")).toBeVisible();
    oldRequest.reject(new api.ApiError(503, "request_failed", "Stale failure"));
    await waitFor(() => expect(screen.queryByText("Stale failure")).not.toBeInTheDocument());
    expect(screen.getByRole("heading", { name: "Reset access" })).toBeVisible();
  });

  it("does not apply a completed submission after navigation and preserves the draft", async () => {
    const pending = deferred<Awaited<ReturnType<typeof api.submitCopilotQuestion>>>();
    vi.spyOn(api, "currentUser").mockResolvedValue(member);
    vi.spyOn(api, "listCopilotConversations").mockResolvedValue({ ...page, conversations: [conversation, secondConversation] });
    vi.spyOn(api, "getCopilotConversation").mockImplementation(async id => id === secondConversation.id ? { conversation: secondConversation, messages: [secondMessage] } : { conversation, messages: [] });
    vi.spyOn(api, "submitCopilotQuestion").mockReturnValue(pending.promise);
    render(<CopilotWorkspace />); const input = await screen.findByPlaceholderText(/Ask a question/);
    await userEvent.type(input, "Draft for reset"); await userEvent.click(screen.getByRole("button", { name: "Submit question" }));
    await userEvent.click(screen.getByRole("button", { name: "Network access" }));
    expect(await screen.findByText("Network conversation")).toBeVisible();
    pending.resolve({ conversation, user_message: userMessage, assistant_message: referenceMessage });
    await waitFor(() => expect(screen.getByRole("heading", { name: "Network access" })).toBeVisible());
    expect(screen.queryByText("Relevant authorized documents were found")).not.toBeInTheDocument();
    expect(input).toHaveValue("Draft for reset");
  });

  it("allows only the latest concurrent list refresh to update the sidebar", async () => {
    const first = deferred<api.CopilotConversationPage>(); const second = deferred<api.CopilotConversationPage>();
    const latest = { ...conversation, title: "Latest title" };
    vi.spyOn(api, "currentUser").mockResolvedValue(member);
    vi.spyOn(api, "listCopilotConversations").mockResolvedValueOnce(page).mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
    vi.spyOn(api, "getCopilotConversation").mockResolvedValue({ conversation, messages: [] });
    render(<CopilotWorkspace />); await screen.findByPlaceholderText(/Ask a question/);
    await userEvent.click(screen.getByRole("button", { name: "Refresh conversations" }));
    await userEvent.click(screen.getByRole("button", { name: "Refresh conversations" }));
    second.resolve({ ...page, conversations: [latest] }); expect(await screen.findByRole("button", { name: "Latest title" })).toBeVisible();
    first.reject(new api.ApiError(503, "request_failed", "Obsolete list failure"));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Obsolete title" })).not.toBeInTheDocument());
    expect(screen.queryByText("Obsolete list failure")).not.toBeInTheDocument();
  });

  it("keeps a committed turn when the secondary list refresh fails", async () => {
    setup(); vi.mocked(api.listCopilotConversations).mockResolvedValueOnce(page).mockRejectedValueOnce(new api.ApiError(503, "request_failed", "List unavailable"));
    vi.spyOn(api, "submitCopilotQuestion").mockResolvedValue({ conversation, user_message: userMessage, assistant_message: referenceMessage });
    render(<CopilotWorkspace />); const input = await screen.findByPlaceholderText(/Ask a question/);
    await userEvent.type(input, "Committed question"); await userEvent.click(screen.getByRole("button", { name: "Submit question" }));
    expect(await screen.findByText("Relevant authorized documents were found")).toBeVisible();
    expect(screen.getByText(/message was saved.*list could not be refreshed/i)).toBeVisible(); expect(input).toHaveValue("");
  });

  it("treats explicit API rejection as definite and preserves input without a detail refresh", async () => {
    setup(); vi.spyOn(api, "submitCopilotQuestion").mockRejectedValue(new api.ApiError(400, "invalid_request", "Request is invalid"));
    render(<CopilotWorkspace />); const input = await screen.findByPlaceholderText(/Ask a question/);
    await userEvent.type(input, "Rejected question"); await userEvent.click(screen.getByRole("button", { name: "Submit question" }));
    expect(await screen.findByText("Request is invalid")).toBeVisible(); expect(input).toHaveValue("Rejected question");
    expect(api.getCopilotConversation).toHaveBeenCalledTimes(1);
  });

  it("reports unresolved transport uncertainty when the detail refresh also fails", async () => {
    setup(); vi.spyOn(api, "submitCopilotQuestion").mockRejectedValue(new api.ApiError(0, "network_error", "Offline"));
    vi.mocked(api.getCopilotConversation).mockResolvedValueOnce({ conversation, messages: [] }).mockRejectedValueOnce(new api.ApiError(503, "request_failed", "Refresh failed"));
    render(<CopilotWorkspace />); const input = await screen.findByPlaceholderText(/Ask a question/);
    await userEvent.type(input, "Uncertain question"); await userEvent.click(screen.getByRole("button", { name: "Submit question" }));
    expect(await screen.findByText(/status could not be confirmed/i)).toBeVisible(); expect(input).toHaveValue("Uncertain question");
  });

  it("prevents deferred updates after unmount", async () => {
    const pending = deferred<api.CopilotConversationDetail>(); setup(); vi.mocked(api.getCopilotConversation).mockReturnValue(pending.promise);
    const view = render(<CopilotWorkspace />); await waitFor(() => expect(api.getCopilotConversation).toHaveBeenCalled());
    view.unmount(); pending.resolve({ conversation, messages: [userMessage] });
    await Promise.resolve(); expect(replace).not.toHaveBeenCalled();
  });
});
