import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ActivationBootstrap } from "./activation-bootstrap";

vi.mock("@/components/activation-form", () => ({
  ActivationForm: ({ token }: { token: string }) => <div data-testid="form" data-token={token}>form</div>,
}));

const TOKEN = "A".repeat(43);

describe("ActivationBootstrap", () => {
  beforeEach(() => window.history.replaceState({}, "", "/activate"));

  it("reads a valid token from the fragment and scrubs the URL synchronously", () => {
    window.history.replaceState({}, "", `/activate#token=${TOKEN}`);
    render(<ActivationBootstrap />);
    expect(window.location.pathname).toBe("/activate");
    expect(window.location.hash).toBe("");
    expect(screen.getByTestId("form")).toHaveAttribute("data-token", TOKEN);
    expect(document.body.innerHTML).not.toContain(`#token=${TOKEN}`);
  });

  it.each(["", "#token=short", `#other=${TOKEN}`, `#token=${TOKEN}&extra=x`])(
    "shows one generic error for invalid fragment %s",
    (fragment) => {
      window.history.replaceState({}, "", `/activate${fragment}`);
      render(<ActivationBootstrap />);
      expect(window.location.hash).toBe("");
      expect(screen.getByRole("alert")).toHaveTextContent("invalid or has expired");
      expect(screen.queryByTestId("form")).not.toBeInTheDocument();
    },
  );
});
