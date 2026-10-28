import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AdminUsers } from "./admin-users";
import * as api from "@/lib/api";

const replace = vi.fn();
const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace, push }) }));

const admin = { id: 1, email: "admin@example.test", is_app_admin: true, it_role: "NONE" } as const;
const managed = { ...admin, is_active: true, lifecycle_status: "active" } as const;

describe("AdminUsers", () => {
  beforeEach(() => { vi.restoreAllMocks(); replace.mockReset(); push.mockReset(); });

  it("redirects a non-admin without loading the user list", async () => {
    const list = vi.spyOn(api, "listUsers");
    vi.spyOn(api, "currentUser").mockResolvedValue({ ...admin, is_app_admin: false });
    render(<AdminUsers />);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard"));
    expect(list).not.toHaveBeenCalled();
  });

  it("lists users and requires confirmation before deactivation", async () => {
    vi.spyOn(api, "currentUser").mockResolvedValue(admin);
    vi.spyOn(api, "listUsers").mockResolvedValue({ users: [managed], pagination: { page: 1, page_size: 20, count: 1, total_pages: 1 } });
    const deactivate = vi.spyOn(api, "deactivateUser").mockResolvedValue({ ...managed, is_active: false, lifecycle_status: "deactivated" });
    vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<AdminUsers />);
    await userEvent.click(await screen.findByRole("button", { name: "Deactivate" }));
    expect(deactivate).not.toHaveBeenCalled();
    vi.mocked(window.confirm).mockReturnValue(true);
    await userEvent.click(screen.getByRole("button", { name: "Deactivate" }));
    await waitFor(() => expect(deactivate).toHaveBeenCalledWith(1));
  });

  it("navigates page boundaries and refreshes the current page after mutation", async () => {
    const pageTwoUser = { ...managed, id: 21, email: "page2@example.test" };
    vi.spyOn(api, "currentUser").mockResolvedValue(admin);
    const list = vi.spyOn(api, "listUsers").mockImplementation(async page => page === 1
      ? { users: [managed], pagination: { page: 1, page_size: 20, count: 21, total_pages: 2 } }
      : { users: [pageTwoUser], pagination: { page: 2, page_size: 20, count: 21, total_pages: 2 } });
    vi.spyOn(api, "updateUser").mockResolvedValue({ ...pageTwoUser, it_role: "IT_MEMBER" });
    render(<AdminUsers />);
    expect(await screen.findByText("Page 1 of 2 · 21 users")).toBeVisible();
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(list).toHaveBeenCalledWith(2));
    expect(await screen.findByText("page2@example.test")).toBeVisible();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
    await userEvent.selectOptions(screen.getByLabelText("Role for page2@example.test"), "IT_MEMBER");
    await waitFor(() => expect(list).toHaveBeenLastCalledWith(2));
  });

  it("renders an empty bounded result without enabling navigation", async () => {
    vi.spyOn(api, "currentUser").mockResolvedValue(admin);
    vi.spyOn(api, "listUsers").mockResolvedValue({ users: [], pagination: { page: 1, page_size: 20, count: 0, total_pages: 0 } });
    render(<AdminUsers />);
    expect(await screen.findByText("No users found.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });
});
