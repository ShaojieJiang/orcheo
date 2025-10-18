import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { App } from "./App";

describe("App", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => [],
    })));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders navigation for templates, issuance, and alerts", () => {
    render(<App />);
    expect(
      screen.getByText(/Credential Templates & Governance/),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Templates/i })).toBeEnabled();
    expect(screen.getByRole("button", { name: /Issue Credential/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Governance Alerts/i })).toBeEnabled();
  });
});
