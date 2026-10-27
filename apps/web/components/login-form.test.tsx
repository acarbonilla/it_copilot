import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LoginForm } from "./login-form";
import * as api from "@/lib/api";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));

describe("LoginForm", () => {
  beforeEach(() => replace.mockReset());

  it("has labeled keyboard-operable controls and validates blanks", async () => {
    const user = userEvent.setup();
    render(<LoginForm />);
    expect(screen.getByLabelText("Email address")).toHaveAttribute("type", "email");
    expect(screen.getByLabelText("Password")).toHaveAttribute("type", "password");
    await user.tab();
    expect(screen.getByLabelText("Email address")).toHaveFocus();
    await user.tab();
    expect(screen.getByLabelText("Password")).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("button", { name: "Sign in" })).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Enter your email and password.");
  });

  it("redirects after a successful login and blocks duplicate submission", async () => {
    let finish!: () => void;
    vi.spyOn(api, "login").mockImplementation(() => new Promise((resolve) => { finish = () => resolve({ id: 1, email: "user@example.com", is_app_admin: false, it_role: "NONE" }); }));
    render(<LoginForm />);
    await userEvent.type(screen.getByLabelText("Email address"), "user@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "secret");
    const form = screen.getByRole("button", { name: "Sign in" }).closest("form")!;
    fireEvent.submit(form); fireEvent.submit(form);
    expect(api.login).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Signing in…" })).toBeDisabled();
    finish();
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard"));
  });

  it("uses a generic invalid-credential error", async () => {
    vi.spyOn(api, "login").mockRejectedValue(new api.ApiError(401, "invalid_credentials", "Invalid"));
    render(<LoginForm />);
    await userEvent.type(screen.getByLabelText("Email address"), "unknown@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "wrong");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Email or password is incorrect.");
  });

  it("distinguishes network failures from invalid credentials", async () => {
    vi.spyOn(api, "login").mockRejectedValue(new api.ApiError(0, "network_error", "Offline"));
    render(<LoginForm />);
    await userEvent.type(screen.getByLabelText("Email address"), "user@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "secret");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("service is unavailable");
  });
});
