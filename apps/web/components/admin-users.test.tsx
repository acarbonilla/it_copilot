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
});
