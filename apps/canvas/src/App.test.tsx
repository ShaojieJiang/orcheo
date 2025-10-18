import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { App } from "./App";

describe("App", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          json: () =>
            Promise.resolve([
              {
                slug: "openai",
                name: "OpenAI API Key",
                description: "Access OpenAI endpoints",
                scopes: ["ai:invoke"],
              },
            ]),
        }) as Promise<Response>
      )
    );

    class MockWebSocket {
      onopen: (() => void) | null = null;
      onmessage: ((event: MessageEvent) => void) | null = null;
      constructor() {
        setTimeout(() => {
          this.onopen?.();
        }, 0);
      }
      send() {}
      close() {}
      addEventListener() {}
      removeEventListener() {}
    }
    vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  });

  it("renders canvas controls and template list", async () => {
    render(<App />);
    expect(screen.getByRole("button", { name: /Save workflow/i })).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByText(/OpenAI API Key/)).toBeInTheDocument()
    );
  });

  it("allows sending chat messages", async () => {
    render(<App />);
    await waitFor(() => screen.getByPlaceholderText(/Send a test instruction/));
    const input = screen.getByPlaceholderText(/Send a test instruction/);
    fireEvent.change(input, { target: { value: "Run test" } });
    fireEvent.submit(input.closest("form")!);
    expect(screen.getByText(/Workflow simulated successfully/)).toBeInTheDocument();
  });
});
