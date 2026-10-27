import { beforeEach, describe, expect, it, vi } from "vitest";
import { bootstrapCsrf, login, logout, resetApiStateForTests } from "./api";

const json = (body: object, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

describe("session API client", () => {
  beforeEach(() => resetApiStateForTests());

  it("bootstraps CSRF, logs in with credentials, then refreshes the rotated token", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(json({ csrfToken: "before" }))
      .mockResolvedValueOnce(json({ user: { id: 1, email: "user@example.com", is_app_admin: false, it_role: "IT_MEMBER" } }))
      .mockResolvedValueOnce(json({ csrfToken: "after" }));
    await login("user@example.com", "secret");
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[1][1]).toMatchObject({ credentials: "include", method: "POST", headers: expect.objectContaining({ "X-CSRFToken": "before" }) });
  });

  it("uses the rotated token for logout", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(json({ csrfToken: "before" }))
      .mockResolvedValueOnce(json({ user: { id: 1, email: "user@example.com", is_app_admin: false, it_role: "NONE" } }))
      .mockResolvedValueOnce(json({ csrfToken: "after" }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    await login("user@example.com", "secret");
    await logout();
    expect(vi.mocked(fetch).mock.calls[3][1]).toMatchObject({ headers: expect.objectContaining({ "X-CSRFToken": "after" }) });
  });

  it("always includes browser credentials", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(json({ csrfToken: "token" }));
    await bootstrapCsrf();
    expect(fetchMock).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ credentials: "include" }));
  });

  it("recovers login once from a cross-tab stale CSRF token", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(json({ csrfToken: "stale" }))
      .mockResolvedValueOnce(json({ error: { code: "invalid_credentials", message: "Invalid email or password" } }, 401))
      .mockResolvedValueOnce(json({ error: { code: "csrf_failed", message: "CSRF validation failed" } }, 403))
      .mockResolvedValueOnce(json({ csrfToken: "current" }))
      .mockResolvedValueOnce(json({ user: { id: 1, email: "user@example.com", is_app_admin: false, it_role: "NONE" } }))
      .mockResolvedValueOnce(json({ csrfToken: "rotated" }));

    await expect(login("user@example.com", "wrong")).rejects.toMatchObject({ status: 401 });
    await expect(login("user@example.com", "correct")).resolves.toMatchObject({ email: "user@example.com" });
    expect(fetchMock).toHaveBeenCalledTimes(6);
    expect(fetchMock.mock.calls[2][1]).toMatchObject({ headers: expect.objectContaining({ "X-CSRFToken": "stale" }) });
    expect(fetchMock.mock.calls[4][1]).toMatchObject({ headers: expect.objectContaining({ "X-CSRFToken": "current" }) });
  });

  it("recovers logout once from a cross-tab stale CSRF token", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(json({ csrfToken: "stale" }))
      .mockResolvedValueOnce(json({ error: { code: "csrf_failed", message: "CSRF validation failed" } }, 403))
      .mockResolvedValueOnce(json({ csrfToken: "current" }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));

    await bootstrapCsrf();
    await expect(logout()).resolves.toBeUndefined();
    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect(fetchMock.mock.calls[1][1]).toMatchObject({ headers: expect.objectContaining({ "X-CSRFToken": "stale" }) });
    expect(fetchMock.mock.calls[3][1]).toMatchObject({ headers: expect.objectContaining({ "X-CSRFToken": "current" }) });
  });

  it("does not retry unrelated 403 responses or network failures", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(json({ csrfToken: "token" }))
      .mockResolvedValueOnce(json({ error: { code: "permission_denied", message: "Denied" } }, 403));
    await expect(logout()).rejects.toMatchObject({ status: 403, code: "permission_denied" });
    expect(fetchMock).toHaveBeenCalledTimes(2);

    resetApiStateForTests();
    fetchMock.mockReset().mockRejectedValueOnce(new TypeError("offline"));
    await expect(logout()).rejects.toMatchObject({ status: 0, code: "network_error" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("bounds csrf_failed recovery to one retry", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(json({ csrfToken: "stale" }))
      .mockResolvedValueOnce(json({ error: { code: "csrf_failed", message: "Failed" } }, 403))
      .mockResolvedValueOnce(json({ csrfToken: "current" }))
      .mockResolvedValueOnce(json({ error: { code: "csrf_failed", message: "Failed" } }, 403));
    await expect(logout()).rejects.toMatchObject({ status: 403, code: "csrf_failed" });
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });
});
