import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { VaultManager } from "./vault-manager";
import * as api from "@/lib/api";

const replace = vi.fn();
const push = vi.fn();
const router = { replace, push };
vi.mock("next/navigation", () => ({ useRouter: () => router }));

const member = { id: 1, email: "owner@example.test", is_app_admin: false, it_role: "IT_MEMBER" } as const;
const active: api.VaultCredential = {
  id: "11111111-1111-4111-8111-111111111111", credential_type: "LOGIN", label: "Portal", service_label: "Example",
  origin: "https://example.test", revision: 1, created_at: "2026-11-01T00:00:00Z", updated_at: "2026-11-01T00:00:00Z",
};
const deleted: api.DeletedVaultCredential = {
  id: "22222222-2222-4222-8222-222222222222", credential_type: "API_TOKEN", label: "Expired token", service_label: "",
  origin: "", revision: 2, restorationEligible: false, restorationExpiresAt: "2026-10-01T00:00:00Z",
};

function setupLists() {
  vi.spyOn(api, "currentUser").mockResolvedValue(member);
  vi.spyOn(api, "listVaultCredentials").mockResolvedValue({ credentials: [active], nextCursor: "cursor-2" });
  vi.spyOn(api, "listDeletedVaultCredentials").mockResolvedValue({ credentials: [deleted], nextCursor: null });
}

describe("VaultManager", () => {
  beforeEach(() => { vi.restoreAllMocks(); replace.mockReset(); push.mockReset(); setupLists(); });

  it("filters and paginates active credentials using the backend cursor", async () => {
    render(<VaultManager />);
    expect(await screen.findByText("Portal")).toBeVisible();
    await userEvent.selectOptions(screen.getByLabelText("Credential type filter"), "LOGIN");
    await waitFor(() => expect(api.listVaultCredentials).toHaveBeenLastCalledWith(expect.objectContaining({ type: "LOGIN" })));
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(api.listVaultCredentials).toHaveBeenLastCalledWith(expect.objectContaining({ cursor: "cursor-2" })));
    expect(screen.getByText("Page 2")).toBeVisible();
  });

  it("renders deleted restore eligibility and blocks an ineligible restore", async () => {
    render(<VaultManager />);
    await userEvent.click(await screen.findByRole("tab", { name: "Deleted" }));
    expect(await screen.findByText("Expired token")).toBeVisible();
    expect(screen.getByRole("button", { name: "Restore unavailable" })).toBeDisabled();
    expect(screen.getByText(/Restore window ends/)).toBeVisible();
  });

  it("blocks duplicate reauthentication submissions and performs one reveal operation", async () => {
    let finish!: (value: { grant: string; expiresAt: string }) => void;
    const reauth = vi.spyOn(api, "reauthenticateVault").mockImplementation(() => new Promise(resolve => { finish = resolve; }));
    const reveal = vi.spyOn(api, "revealVaultCredential").mockResolvedValue({ password: "top-secret" });
    render(<VaultManager />);
    await userEvent.click(await screen.findByRole("button", { name: "Reveal" }));
    await userEvent.type(screen.getAllByLabelText("Password").at(-1)!, "account-password");
    const form = screen.getByRole("dialog", { name: "Reauthenticate to continue" }).closest("form")!;
    fireEvent.submit(form); fireEvent.submit(form);
    expect(reauth).toHaveBeenCalledTimes(1);
    finish({ grant: "grant", expiresAt: "2026-11-15T01:00:00Z" });
    expect(await screen.findByText("••••••••••")).toBeVisible();
    expect(reveal).toHaveBeenCalledTimes(1);
  });

  it("invalidates an in-flight authorization when hidden so stale reveal plaintext cannot return", async () => {
    let finish!: (value: { grant: string; expiresAt: string }) => void;
    vi.spyOn(api, "reauthenticateVault").mockImplementation(() => new Promise(resolve => { finish = resolve; }));
    const reveal = vi.spyOn(api, "revealVaultCredential").mockResolvedValue({ password: "must-not-render" });
    render(<VaultManager />);
    await userEvent.click(await screen.findByRole("button", { name: "Reveal" }));
    await userEvent.type(screen.getByLabelText("Password"), "account-password");
    await userEvent.click(screen.getByRole("button", { name: "Authorize once" }));
    Object.defineProperty(document, "visibilityState", { configurable: true, value: "hidden" });
    fireEvent(document, new Event("visibilitychange"));
    finish({ grant: "grant", expiresAt: "2026-11-15T01:00:00Z" });
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Reauthenticate to continue" })).not.toBeInTheDocument());
    expect(reveal).not.toHaveBeenCalled();
    expect(screen.queryByText("must-not-render")).not.toBeInTheDocument();
    Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" });
  });

  it("clears revealed values when the panel is closed", async () => {
    vi.spyOn(api, "reauthenticateVault").mockResolvedValue({ grant: "grant", expiresAt: "2026-11-15T01:00:00Z" });
    vi.spyOn(api, "revealVaultCredential").mockResolvedValue({ password: "top-secret" });
    render(<VaultManager />);
    await userEvent.click(await screen.findByRole("button", { name: "Reveal" }));
    await userEvent.type(screen.getByLabelText("Password"), "account-password");
    await userEvent.click(screen.getByRole("button", { name: "Authorize once" }));
    await screen.findByText("••••••••••");
    await userEvent.click(screen.getByRole("button", { name: "Close revealed credential" }));
    expect(screen.queryByRole("button", { name: "Close revealed credential" })).not.toBeInTheDocument();
    expect(screen.queryByText("top-secret")).not.toBeInTheDocument();
  });

  it("creates a credential through reauthentication and clears the editor secret", async () => {
    vi.spyOn(api, "reauthenticateVault").mockResolvedValue({ grant: "grant", expiresAt: "2026-11-15T01:00:00Z" });
    const create = vi.spyOn(api, "createVaultCredential").mockResolvedValue(active);
    render(<VaultManager />);
    await userEvent.click(await screen.findByRole("button", { name: "Add credential" }));
    await userEvent.type(screen.getByLabelText("Label"), "New portal");
    await userEvent.type(screen.getByLabelText("Password"), "new-secret");
    await userEvent.click(screen.getByRole("button", { name: "Continue to reauthentication" }));
    await userEvent.type(screen.getAllByLabelText("Password").at(-1)!, "account-password");
    await userEvent.click(screen.getByRole("button", { name: "Authorize once" }));
    await waitFor(() => expect(create).toHaveBeenCalledWith(expect.objectContaining({ label: "New portal", secretFields: expect.objectContaining({ password: "new-secret" }) }), "grant"));
    expect(await screen.findByText("Credential created.")).toBeVisible();
    expect(screen.queryByRole("dialog", { name: "Add credential" })).not.toBeInTheDocument();
  });

  it("surfaces a consumed-grant failure and does not retry deletion", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.spyOn(api, "reauthenticateVault").mockResolvedValue({ grant: "grant", expiresAt: "2026-11-15T01:00:00Z" });
    const remove = vi.spyOn(api, "deleteVaultCredential").mockRejectedValue(new api.ApiError(403, "invalid_grant", "Invalid"));
    render(<VaultManager />);
    await userEvent.click(await screen.findByRole("button", { name: "Delete" }));
    await userEvent.type(screen.getByLabelText("Password"), "account-password");
    await userEvent.click(screen.getByRole("button", { name: "Authorize once" }));
    expect(await screen.findByText(/Authorization expired or was already used/)).toBeVisible();
    expect(remove).toHaveBeenCalledTimes(1);
  });

  it.each(["visibilitychange", "pagehide"] as const)("clears editor secrets on %s and does not restore them", async eventName => {
    render(<VaultManager />);
    await userEvent.click(await screen.findByRole("button", { name: "Add credential" }));
    await userEvent.type(screen.getByLabelText("Password"), "editor-secret");
    if (eventName === "visibilitychange") {
      Object.defineProperty(document, "visibilityState", { configurable: true, value: "hidden" });
      fireEvent(document, new Event("visibilitychange"));
      Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" });
    } else {
      fireEvent(window, new Event("pagehide"));
    }
    expect(screen.queryByRole("dialog", { name: "Add credential" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Add credential" }));
    expect(screen.getByLabelText("Password")).toHaveValue("");
  });

  it("clears editor secrets when creation is cancelled", async () => {
    render(<VaultManager />);
    await userEvent.click(await screen.findByRole("button", { name: "Add credential" }));
    await userEvent.type(screen.getByLabelText("Password"), "cancelled-secret");
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await userEvent.click(screen.getByRole("button", { name: "Add credential" }));
    expect(screen.getByLabelText("Password")).toHaveValue("");
  });

  it("does not restore editor secrets after component unmount", async () => {
    const first = render(<VaultManager />);
    await userEvent.click(await screen.findByRole("button", { name: "Add credential" }));
    await userEvent.type(screen.getByLabelText("Password"), "unmounted-secret");
    first.unmount();
    render(<VaultManager />);
    await userEvent.click(await screen.findByRole("button", { name: "Add credential" }));
    expect(screen.getByLabelText("Password")).toHaveValue("");
  });

  it.each([
    { type: "API_TOKEN", secretLabel: "Token", secret: "token-value", serviceExpected: true },
    { type: "SSH_KEY", secretLabel: "Private key", secret: "private-key-value", serviceExpected: false },
    { type: "GENERIC_SECRET", secretLabel: "Secret", secret: "generic-value", serviceExpected: false },
  ] as const)("omits incompatible LOGIN metadata after switching to $type", async ({ type, secretLabel, secret, serviceExpected }) => {
    vi.spyOn(api, "reauthenticateVault").mockResolvedValue({ grant: "grant", expiresAt: "2026-11-15T01:00:00Z" });
    const create = vi.spyOn(api, "createVaultCredential").mockResolvedValue({ ...active, credential_type: type });
    render(<VaultManager />);
    await userEvent.click(await screen.findByRole("button", { name: "Add credential" }));
    await userEvent.type(screen.getByLabelText("Label"), "Changed type");
    await userEvent.type(screen.getByLabelText("Service label"), "Supported service");
    await userEvent.type(screen.getByLabelText("HTTPS origin"), "https://stale.example.test");
    await userEvent.selectOptions(screen.getAllByLabelText("Type").at(-1)!, type);
    await userEvent.type(screen.getByLabelText(secretLabel), secret);
    await userEvent.click(screen.getByRole("button", { name: "Continue to reauthentication" }));
    await userEvent.type(screen.getByLabelText("Password"), "account-password");
    await userEvent.click(screen.getByRole("button", { name: "Authorize once" }));
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1));
    const input = create.mock.calls[0][0];
    expect(input).not.toHaveProperty("origin");
    if (serviceExpected) expect(input).toHaveProperty("serviceLabel", "Supported service");
    else expect(input).not.toHaveProperty("serviceLabel");
  });

  it("blocks rapid duplicate Next transitions while the page request is pending", async () => {
    let finish!: (value: api.VaultPage<api.VaultCredential>) => void;
    vi.mocked(api.listVaultCredentials)
      .mockResolvedValueOnce({ credentials: [active], nextCursor: "cursor-2" })
      .mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
    render(<VaultManager />);
    const next = await screen.findByRole("button", { name: "Next" });
    await waitFor(() => expect(next).toBeEnabled());
    fireEvent.click(next); fireEvent.click(next); fireEvent.click(next);
    expect(next).toBeDisabled();
    await waitFor(() => expect(api.listVaultCredentials).toHaveBeenCalledTimes(2));
    expect(api.listVaultCredentials).toHaveBeenLastCalledWith(expect.objectContaining({ cursor: "cursor-2" }));
    expect(screen.getByText("Page 2")).toBeVisible();
    finish({ credentials: [active], nextCursor: null });
    await waitFor(() => expect(next).toBeDisabled());
    expect(screen.getByText("Page 2")).toBeVisible();
  });

  it("shows an initialization error without metadata and recovers on retry", async () => {
    vi.mocked(api.currentUser)
      .mockRejectedValueOnce(new api.ApiError(503, "service_unavailable", "Service unavailable"))
      .mockResolvedValueOnce(member);
    render(<VaultManager />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Service unavailable");
    expect(screen.queryByText("Portal")).not.toBeInTheDocument();
    expect(api.listVaultCredentials).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Portal")).toBeVisible();
    expect(api.currentUser).toHaveBeenCalledTimes(2);
  });
});
