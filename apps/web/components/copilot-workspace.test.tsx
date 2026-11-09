import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CopilotWorkspace } from "./copilot-workspace";
import * as api from "@/lib/api";

const replace = vi.fn(); const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace, push }) }));
const member = { id: 1, email: "member@example.test", is_app_admin: false, it_role: "IT_MEMBER" } as const;
const conversation: api.CopilotConversation = { id: "11111111-1111-4111-8111-111111111111", title: "Reset access", created_at: "2026-11-01T00:00:00Z", updated_at: "2026-11-01T00:00:00Z", last_activity_at: "2026-11-01T00:00:00Z", retention_expires_at: "2026-12-01T00:00:00Z" };
const userMessage: api.CopilotMessage = { id: "u1", role: "user", content: "How do I reset access?", grounding_status: "not_applicable", provider_status: "not_applicable", citations: [], created_at: "2026-11-01T00:00:01Z" };
const referenceMessage: api.CopilotMessage = { id: "a1", role: "assistant", content: "", grounding_status: "references", provider_status: "disabled", citations: [{ id: "cite_safe", document_id: "doc", version_id: "version", label: "Reset guide", version_sequence: 3 }], created_at: "2026-11-01T00:00:02Z" };
const emptyPage = { conversations: [], pagination: { page: 1, page_size: 25, count: 0, total_pages: 0 } };
const page = { ...emptyPage, conversations: [conversation], pagination: { ...emptyPage.pagination, count: 1, total_pages: 1 } };

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
});
