import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthRedirect } from "./auth-redirect";
import * as api from "@/lib/api";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));

describe("AuthRedirect", () => {
  beforeEach(() => replace.mockReset());
  it("sends an authenticated session to dashboard", async () => {
    vi.spyOn(api, "currentUser").mockResolvedValue({ id: 1, email: "a@b.com", is_app_admin: false, it_role: "NONE" });
    render(<AuthRedirect />);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard"));
  });
  it("sends an anonymous session to login", async () => {
    vi.spyOn(api, "currentUser").mockRejectedValue(new api.ApiError(401, "authentication_required", "Required"));
    render(<AuthRedirect />);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
  });
});
