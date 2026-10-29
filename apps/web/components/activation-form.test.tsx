import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ActivationForm } from "./activation-form";
import { activateAccount, ApiError } from "@/lib/api";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));
vi.mock("@/lib/api", async (load) => {
  const actual = await load<typeof import("@/lib/api")>();
  return { ...actual, activateAccount: vi.fn() };
});

describe("ActivationForm", () => {
  beforeEach(() => { replace.mockReset(); vi.mocked(activateAccount).mockReset(); });

  it("keeps the token out of rendered content", () => {
    const { container } = render(<ActivationForm token="SENTINEL-TOKEN" />);
    expect(container).not.toHaveTextContent("SENTINEL-TOKEN");
    expect(container.innerHTML).not.toContain("SENTINEL-TOKEN");
  });

  it("checks length and confirmation before submission", async () => {
    const user = userEvent.setup();
    render(<ActivationForm token="token" />);
    await user.type(screen.getByLabelText("Create password"), "short");
    await user.type(screen.getByLabelText("Confirm password"), "short");
    fireEvent.submit(screen.getByRole("button", { name: "Activate account" }).closest("form")!);
    expect(screen.getByRole("alert")).toHaveTextContent("at least 12");
    expect(activateAccount).not.toHaveBeenCalled();
  });

  it("activates once and replaces the token URL with login", async () => {
    vi.mocked(activateAccount).mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<ActivationForm token="secret-token" />);
    await user.type(screen.getByLabelText("Create password"), "a-secure-password-phrase");
    await user.type(screen.getByLabelText("Confirm password"), "a-secure-password-phrase");
    await user.click(screen.getByRole("button", { name: "Activate account" }));
    await waitFor(() => expect(activateAccount).toHaveBeenCalledWith("secret-token", "a-secure-password-phrase"));
    expect(replace).toHaveBeenCalledWith("/login");
  });

  it("uses a safe error for invalid links", async () => {
    vi.mocked(activateAccount).mockRejectedValueOnce(new ApiError(400, "invalid_activation", "server detail"));
    const user = userEvent.setup();
    render(<ActivationForm token="token-one" />);
    await user.type(screen.getByLabelText("Create password"), "a-secure-password-phrase");
    await user.type(screen.getByLabelText("Confirm password"), "a-secure-password-phrase");
    await user.click(screen.getByRole("button", { name: "Activate account" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("invalid or has expired");
    expect(screen.getByRole("alert")).not.toHaveTextContent("server detail");
  });

  it("uses a safe error for server-side password policy rejection", async () => {
    vi.mocked(activateAccount).mockRejectedValue(new ApiError(400, "password_policy_failed", "server detail"));
    const user = userEvent.setup();
    render(<ActivationForm token="token-two" />);
    await user.type(screen.getByLabelText("Create password"), "a-secure-password-phrase");
    await user.type(screen.getByLabelText("Confirm password"), "a-secure-password-phrase");
    await user.click(screen.getByRole("button", { name: "Activate account" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("less common password");
    expect(screen.getByRole("alert")).not.toHaveTextContent("server detail");
  });
});
