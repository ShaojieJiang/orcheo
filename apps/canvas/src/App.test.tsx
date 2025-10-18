import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "./App";

class MockWebSocket {
  public onopen: (() => void) | null = null;
  public onclose: (() => void) | null = null;
  public onmessage: ((event: MessageEvent) => void) | null = null;
  public onerror: (() => void) | null = null;

  constructor(public url: string) {
    setTimeout(() => this.onopen?.(), 0);
  }

  close() {
    this.onclose?.();
  }

  send() {
    /* noop */
  }
}

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace globalThis {
    // eslint-disable-next-line no-var
    var WebSocket: typeof MockWebSocket;
  }
}

beforeEach(() => {
  globalThis.WebSocket = MockWebSocket as unknown as typeof WebSocket;
  navigator.clipboard = {
    writeText: vi.fn().mockResolvedValue(undefined),
  } as unknown as Clipboard;
  vi.spyOn(window, "alert").mockImplementation(() => undefined);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("App", () => {
  it("supports node editing and undo/redo", async () => {
    render(<App />);

    const addAiButton = screen.getByRole("button", { name: /add ai/i });
    await userEvent.click(addAiButton);

    expect(screen.getAllByText(/node/i).length).toBeGreaterThan(0);

    const undoButton = screen.getByRole("button", { name: /undo/i });
    await userEvent.click(undoButton);
    await waitFor(() => expect(undoButton).toBeDisabled());
  });

  it("allows credential assignment and validation", async () => {
    render(<App />);

    const select = await screen.findAllByRole("combobox");
    await userEvent.selectOptions(select[0], "slack");

    const validateButton = screen.getByRole("button", { name: /run validation/i });
    await userEvent.click(validateButton);

    expect(screen.getByText(/All checks passed/i)).toBeInTheDocument();
  });

  it("supports chat simulation and websocket connection", async () => {
    render(<App />);

    const chatInput = screen.getByPlaceholderText(/ask the workflow/i);
    await userEvent.type(chatInput, "Hello world");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() =>
      expect(screen.getByTestId("chat-messages").textContent).toContain("Hello world")
    );

    await userEvent.click(screen.getByRole("button", { name: /connect/i }));
    await waitFor(() =>
      expect(screen.getByText(/connected/i)).toBeInTheDocument()
    );
  });
});
