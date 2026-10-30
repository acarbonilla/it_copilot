import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DocumentsManager } from "./documents-manager";
import * as api from "@/lib/api";

const replace = vi.fn(); const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace, push }) }));
const member = { id: 1, email: "member@example.test", is_app_admin: false, it_role: "IT_MEMBER" } as const;
const item: api.DocumentItem = { id: "11111111-1111-4111-8111-111111111111", title: "Runbook", description: "Private", visibility: "active", metadata_revision: 1, created_at: "2026-10-30T00:00:00Z", updated_at: "2026-10-30T00:00:00Z", processing: { version_id: "22222222-2222-4222-8222-222222222222", sequence: 1, status: "ready" }, capabilities: { edit: true, download: true, archive: true, restore: false, delete: true, retry: true } };
const page = { documents: [item], pagination: { page: 1, page_size: 25, count: 1, total_pages: 1 } };

describe("DocumentsManager", () => {
  beforeEach(() => { vi.restoreAllMocks(); replace.mockReset(); push.mockReset(); });
  it("lists authorized documents and renders only server-provided controls", async () => {
    vi.spyOn(api, "currentUser").mockResolvedValue(member); vi.spyOn(api, "listDocuments").mockResolvedValue(page);
    render(<DocumentsManager />);
    expect(await screen.findByText("Runbook")).toBeVisible();
    expect(screen.getByRole("link", { name: "Download" })).toHaveAttribute("href", expect.stringContaining("/download"));
    expect(screen.getByRole("button", { name: "Archive" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Restore" })).not.toBeInTheDocument();
  });
  it("keeps App Admin-only view metadata-only without upload or content controls", async () => {
    vi.spyOn(api, "currentUser").mockResolvedValue({ ...member, is_app_admin: true, it_role: "NONE" });
    vi.spyOn(api, "listDocuments").mockResolvedValue({ ...page, documents: [{ ...item, title: undefined, description: undefined, capabilities: { edit: false, download: false, archive: false, restore: false, delete: false, retry: false } }] });
    render(<DocumentsManager />);
    expect(await screen.findByText("Document 11111111")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Upload document" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Download" })).not.toBeInTheDocument();
  });
  it("requires confirmation before archive", async () => {
    vi.spyOn(api, "currentUser").mockResolvedValue(member); vi.spyOn(api, "listDocuments").mockResolvedValue(page);
    const action = vi.spyOn(api, "documentAction").mockResolvedValue({ ...item, visibility: "archived" });
    vi.spyOn(window, "confirm").mockReturnValue(false); render(<DocumentsManager />);
    await userEvent.click(await screen.findByRole("button", { name: "Archive" })); expect(action).not.toHaveBeenCalled();
  });
  it("redirects when identity cannot be restored", async () => {
    vi.spyOn(api, "currentUser").mockRejectedValue(new api.ApiError(401, "authentication_required", "Required")); render(<DocumentsManager />);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
  });
});
