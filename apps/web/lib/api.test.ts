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
});
