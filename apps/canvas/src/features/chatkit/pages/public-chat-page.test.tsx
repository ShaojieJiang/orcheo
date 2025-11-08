import { describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { render, screen } from "@testing-library/react";

import PublicChatPage from "./public-chat-page";

const renderWithRouter = (initialEntry: string) =>
  render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/chat/:workflowId" element={<PublicChatPage />} />
      </Routes>
    </MemoryRouter>,
  );

describe("PublicChatPage", () => {
  it("renders a missing token message when none is provided", () => {
    renderWithRouter("/chat/workflow-123");

    expect(screen.getByText(/missing access token/i)).toBeInTheDocument();
  });

  it("fetches workflow metadata when a token is provided via query string", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          id: "workflow-123",
          name: "Shared Workflow",
          is_public: true,
          require_login: false,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    renderWithRouter("/chat/workflow-123?token=secret-token");

    const headings = await screen.findAllByRole("heading", {
      name: "Shared Workflow",
    });
    expect(headings.length).toBeGreaterThan(0);

    expect(fetchMock).toHaveBeenCalled();
    const [requestedUrl, init] = fetchMock.mock.calls[0];
    expect(requestedUrl).toContain("/api/chatkit/workflows/workflow-123");
    const headers = new Headers((init ?? {}).headers as HeadersInit);
    expect(headers.get("X-Orcheo-Publish-Token")).toBe("secret-token");

    fetchMock.mockRestore();
  });

  it("prompts the visitor to login when require_login is true", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          id: "workflow-123",
          name: "Private Workflow",
          is_public: true,
          require_login: true,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    renderWithRouter("/chat/workflow-123?token=secret-token");

    await screen.findByText("Private Workflow");

    const loginHeading = await screen.findByRole("heading", {
      name: /login required/i,
    });
    expect(loginHeading).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /sign in/i }),
    ).toBeInTheDocument();

    fetchMock.mockRestore();
  });
});
