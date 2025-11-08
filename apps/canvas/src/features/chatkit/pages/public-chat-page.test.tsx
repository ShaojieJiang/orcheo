import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, afterEach } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import {
  clearAllPublishTokens,
  getPublishToken,
} from "@features/chatkit/lib/publish-token-store";

import PublicChatPage from "./public-chat-page";

const renderWithRoute = (route = "/chat/wf-123") =>
  render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route path="/chat/:workflowId" element={<PublicChatPage />} />
        <Route path="*" element={<div data-testid="fallback">home</div>} />
      </Routes>
    </MemoryRouter>,
  );

const buildMetadataResponse = (
  overrides: Partial<{ require_login: boolean; name: string }> = {},
) =>
  new Response(
    JSON.stringify({
      id: "wf-123",
      name: overrides.name ?? "Workflow 123",
      is_public: true,
      require_login: overrides.require_login ?? false,
    }),
    {
      status: 200,
      headers: { "Content-Type": "application/json" },
    },
  );

describe("PublicChatPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    clearAllPublishTokens();
  });

  it("loads workflow metadata and renders the token form", async () => {
    const fetchMock = vi
      .spyOn(global, "fetch")
      .mockImplementation(() => Promise.resolve(buildMetadataResponse()));

    renderWithRoute();

    expect(screen.getByText(/Loading workflow/i)).toBeInTheDocument();

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    expect(await screen.findByText("Workflow 123")).toBeInTheDocument();
    await waitFor(() => {
      expect(document.getElementById("publish-token")).toBeTruthy();
    });
  });

  it("shows a friendly error when the workflow is not published", async () => {
    vi.spyOn(global, "fetch").mockImplementation(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({ detail: { message: "Workflow is not published." } }),
          { status: 404, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    renderWithRoute();

    expect(
      await screen.findByText(/not published or the identifier is incorrect/i),
    ).toBeInTheDocument();
  });

  it("prompts for login when the workflow requires authentication", async () => {
    vi.spyOn(global, "fetch").mockImplementation(() =>
      Promise.resolve(buildMetadataResponse({ require_login: true })),
    );

    renderWithRoute();

    expect(await screen.findByText(/Login required/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Log in/i })).toBeInTheDocument();
  });

  it("prefills the token field from the query string", async () => {
    vi.spyOn(global, "fetch").mockImplementation(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            id: "wf-123",
            name: "Prefill Workflow",
            is_public: true,
            require_login: false,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    renderWithRoute("/chat/wf-123?token=secret-token");

    expect(await screen.findByText("Prefill Workflow")).toBeInTheDocument();

    await waitFor(() => {
      expect(getPublishToken("wf-123")).toBe("secret-token");
    });
  });
});
