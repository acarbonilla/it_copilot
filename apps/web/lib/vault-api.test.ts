import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createVaultCredential,
  deleteVaultCredential,
  listVaultCredentials,
  resetApiStateForTests,
  type VaultCredential,
} from "./api";

const credential: VaultCredential = {
  id: "11111111-1111-4111-8111-111111111111",
  credential_type: "LOGIN",
  label: "Portal",
  service_label: "Example",
  origin: "https://example.test",
  revision: 3,
  created_at: "2026-11-01T00:00:00Z",
  updated_at: "2026-11-01T00:00:00Z",
};
const json = (body: object, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

describe("vault API client", () => {
  beforeEach(() => resetApiStateForTests());

  it("encodes active-list filters and opaque cursor without exposing secrets", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(json({ credentials: [credential], nextCursor: "next/cursor" }));
    await expect(listVaultCredentials({ cursor: "opaque+cursor", type: "LOGIN", prefix: "Por", limit: 10 })).resolves.toMatchObject({ nextCursor: "next/cursor" });
    const url = new URL(fetchMock.mock.calls[0][0] as string);
    expect(Object.fromEntries(url.searchParams)).toEqual({ limit: "10", cursor: "opaque+cursor", type: "LOGIN", prefix: "Por" });
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ credentials: "include" });
  });

  it("sends the accepted create contract with explicit CSRF and one-use grant headers", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(json({ csrfToken: "csrf" }))
      .mockResolvedValueOnce(json({ credential }, 201));
    await createVaultCredential({ credentialType: "LOGIN", label: "Portal", serviceLabel: "Example", origin: "https://example.test", secretFields: { username: "owner", password: "secret" } }, "one-use-grant");
    expect(fetchMock.mock.calls[1]).toEqual([
      expect.stringContaining("/api/v1/vault/credentials"),
      expect.objectContaining({
        credentials: "include",
        method: "POST",
        headers: expect.objectContaining({ "X-CSRFToken": "csrf", "X-Vault-Grant": "one-use-grant" }),
        body: JSON.stringify({ credentialType: "LOGIN", label: "Portal", serviceLabel: "Example", origin: "https://example.test", secretFields: { username: "owner", password: "secret" } }),
      }),
    ]);
  });

  it("accepts delete HTTP 204 and never replays a grant-protected operation after CSRF failure", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(json({ csrfToken: "csrf" }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    await expect(deleteVaultCredential(credential, "grant")).resolves.toBeUndefined();
    expect(fetchMock.mock.calls[1][1]).toMatchObject({ method: "DELETE", body: JSON.stringify({ expectedRevision: 3 }) });

    resetApiStateForTests();
    fetchMock.mockReset()
      .mockResolvedValueOnce(json({ csrfToken: "stale" }))
      .mockResolvedValueOnce(json({ error: { code: "csrf_failed", message: "Failed" } }, 403));
    await expect(deleteVaultCredential(credential, "single-use")).rejects.toMatchObject({ status: 403, code: "csrf_failed" });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
