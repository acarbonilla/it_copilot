import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DashboardShell } from "./dashboard-shell";
import * as api from "@/lib/api";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));

const member = { id: 1, email: "member@example.com", is_app_admin: false, it_role: "IT_MEMBER" } as const;

describe("DashboardShell", () => {
  beforeEach(() => replace.mockReset());

  it("hides protected content until identity is restored, then labels placeholders", async () => {
    vi.spyOn(api, "currentUser").mockResolvedValue(member);
    render(<DashboardShell />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading");
    expect(await screen.findByText("member@example.com")).toBeVisible();
    expect(screen.getAllByText("Not yet available")).toHaveLength(4);
    expect(screen.queryByText("Administration")).not.toBeInTheDocument();
  });

  it("shows administration only for App Admin without changing IT role", async () => {
    vi.spyOn(api, "currentUser").mockResolvedValue({ ...member, is_app_admin: true, it_role: "NONE" });
    render(<DashboardShell />);
    expect(await screen.findByRole("link", { name: "Administration" })).toHaveAttribute("href", "/admin/users");
  });

  it("redirects an anonymous user before rendering protected content", async () => {
    vi.spyOn(api, "currentUser").mockRejectedValue(new api.ApiError(401, "authentication_required", "Required"));
    render(<DashboardShell />);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
    expect(screen.queryByRole("heading", { name: "Dashboard" })).not.toBeInTheDocument();
  });

  it("logs out and returns to login", async () => {
    vi.spyOn(api, "currentUser").mockResolvedValue(member);
    vi.spyOn(api, "logout").mockResolvedValue();
    render(<DashboardShell />);
    await userEvent.click(await screen.findByRole("button", { name: "Sign out" }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
  });
});
