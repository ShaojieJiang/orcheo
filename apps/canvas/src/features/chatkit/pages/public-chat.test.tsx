import { ReactNode } from "react";
import { act, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterAll, beforeEach, describe, expect, it, vi } from "vitest";

import PublicChatPage from "./public-chat";
import { resetPublishTokenStore } from "../lib/publish-token-store";

declare global {
  var fetch: typeof globalThis.fetch;
}

const renderWithRouter = (ui: ReactNode, initialEntry: string) => {
  window.history.replaceState({}, "", initialEntry);
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/chat/:workflowId" element={ui} />
      </Routes>
    </MemoryRouter>,
  );
};

describe("PublicChatPage", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
    resetPublishTokenStore();
    global.fetch = vi.fn() as unknown as typeof global.fetch;
  });

  afterAll(() => {
    global.fetch = originalFetch;
  });

  it("renders workflow name when metadata loads", async () => {
    (global.fetch as unknown as vi.Mock).mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "wf-1",
          name: "Workflow One",
          require_login: false,
          is_public: true,
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );

    renderWithRouter(<PublicChatPage />, "/chat/wf-1?token=abc123");

    await waitFor(() =>
      expect(screen.getByText("Workflow One")).toBeInTheDocument(),
    );
    expect(screen.queryByText(/Sign in required/i)).not.toBeInTheDocument();
  });

  it("prompts for login when workflow requires authentication", async () => {
    (global.fetch as unknown as vi.Mock).mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "wf-secure",
          name: "Secure Workflow",
          require_login: true,
          is_public: true,
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );

    renderWithRouter(<PublicChatPage />, "/chat/wf-secure?token=secret");

    await waitFor(() =>
      expect(screen.getByText("Secure Workflow")).toBeInTheDocument(),
    );
    expect(screen.getByText(/Sign in required/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Start chat/i }),
    ).toBeInTheDocument();
  });

  it("shows an error when metadata cannot be loaded", async () => {
    (global.fetch as unknown as vi.Mock).mockResolvedValue(
      new Response(JSON.stringify({ detail: { message: "Not found" } }), {
        status: 404,
        headers: { "content-type": "application/json" },
      }),
    );

    renderWithRouter(<PublicChatPage />, "/chat/unknown?token=foo");

    await waitFor(() =>
      expect(screen.getByText(/Unable to load workflow/i)).toBeInTheDocument(),
    );
  });

  it("stores token from query string and removes it from the URL", async () => {
    (global.fetch as unknown as vi.Mock).mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "wf-2",
          name: "Workflow Two",
          require_login: false,
          is_public: true,
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );

    await act(async () => {
      renderWithRouter(
        <PublicChatPage />,
        "/chat/wf-2?token=special&ref=share",
      );
    });

    await waitFor(() =>
      expect(screen.getByText("Workflow Two")).toBeInTheDocument(),
    );
    expect(window.location.search).toBe("?ref=share");
  });
});
