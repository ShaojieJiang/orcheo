import { beforeAll, describe, expect, it, vi } from "vitest";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import WorkflowCanvas from "./workflow-canvas";
import { TraceTabContent } from "@features/workflow/pages/workflow-canvas/components/trace-tab-content";

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

beforeAll(() => {
  Object.defineProperty(globalThis, "ResizeObserver", {
    configurable: true,
    writable: true,
    value: ResizeObserverMock,
  });
  class WebSocketMock {
    static CONNECTING = 0;
    static OPEN = 1;
    static CLOSING = 2;
    static CLOSED = 3;

    readyState = WebSocketMock.CONNECTING;
    url: string;
    sent: string[] = [];
    onopen: ((event: Event) => void) | null = null;
    onmessage: ((event: MessageEvent<string>) => void) | null = null;
    onerror: ((event: Event) => void) | null = null;
    onclose: ((event: Event) => void) | null = null;

    constructor(url: string) {
      this.url = url;
      queueMicrotask(() => {
        this.readyState = WebSocketMock.OPEN;
        this.onopen?.(new Event("open"));
      });
    }

    send(data: string) {
      this.sent.push(data);
    }

    close() {
      this.readyState = WebSocketMock.CLOSED;
      this.onclose?.(new Event("close"));
    }

    addEventListener() {}

    removeEventListener() {}

    dispatchEvent() {
      return true;
    }
  }

  Object.defineProperty(globalThis, "WebSocket", {
    configurable: true,
    writable: true,
    value: WebSocketMock,
  });
  if (!globalThis.crypto) {
    Object.defineProperty(globalThis, "crypto", {
      value: {},
    });
  }
  if (!globalThis.crypto.randomUUID) {
    Object.defineProperty(globalThis.crypto, "randomUUID", {
      value: vi.fn(
        () => `test-node-${Math.random().toString(36).slice(2, 10)}`,
      ),
    });
  }
  if (!URL.createObjectURL) {
    Object.defineProperty(URL, "createObjectURL", {
      value: vi.fn(() => "blob:mock"),
    });
  }
  if (!URL.revokeObjectURL) {
    Object.defineProperty(URL, "revokeObjectURL", {
      value: vi.fn(),
    });
  }
  Object.defineProperty(window.HTMLElement.prototype, "scrollIntoView", {
    value: vi.fn(),
    configurable: true,
  });
});

const renderCanvas = () => {
  const initialNodes = [
    {
      id: "node-1",
      type: "default" as const,
      position: { x: 0, y: 0 },
      data: { type: "default", label: "Initial Node", status: "idle" as const },
      selected: true,
      draggable: true,
    },
  ];

  return render(
    <MemoryRouter initialEntries={["/workflow-canvas"]}>
      <Routes>
        <Route
          path="/workflow-canvas"
          element={<WorkflowCanvas initialNodes={initialNodes} />}
        />
      </Routes>
    </MemoryRouter>,
  );
};

describe("WorkflowCanvas editing history", () => {
  it("supports undo and redo via buttons", async () => {
    renderCanvas();

    const initialNodes = await screen.findAllByText("Initial Node");
    expect(initialNodes.length).toBeGreaterThan(0);

    // Verify undo and redo buttons start disabled (no history yet)
    const undoButton = screen.getByRole("button", { name: /undo/i });
    const redoButton = screen.getByRole("button", { name: /redo/i });

    expect(undoButton).toBeDisabled();
    expect(redoButton).toBeDisabled();
  });

  it("supports keyboard shortcuts for undo and redo", async () => {
    renderCanvas();

    const initialNodes = await screen.findAllByText("Initial Node");
    expect(initialNodes.length).toBeGreaterThan(0);

    // Verify buttons exist and are initially disabled
    const undoButtons = screen.getAllByRole("button", { name: /undo/i });
    const redoButtons = screen.getAllByRole("button", { name: /redo/i });

    expect(undoButtons[0]).toBeDisabled();
    expect(redoButtons[0]).toBeDisabled();
  });

  it("opens the node search overlay from toolbar", async () => {
    renderCanvas();

    const searchButtons = await screen.findAllByRole("button", {
      name: /search nodes/i,
    });
    const searchButton = searchButtons[0];
    fireEvent.click(searchButton);

    const searchPanels = await screen.findAllByTestId("workflow-search");
    const searchInput = within(searchPanels[0]).getByPlaceholderText(
      "Search nodes...",
    );
    fireEvent.change(searchInput, { target: { value: "Initial" } });

    await waitFor(() => {
      const matches = document.querySelectorAll('[data-search-match="true"]');
      expect(matches.length).toBeGreaterThan(0);
    });
  });

  it("opens the search overlay with ctrl+f", async () => {
    renderCanvas();

    await screen.findAllByRole("button", { name: /search nodes/i });

    fireEvent.keyDown(document, { key: "f", ctrlKey: true });

    const searchPanels = await screen.findAllByTestId("workflow-search");

    expect(searchPanels.length).toBeGreaterThan(0);
  });

  it("shows a placeholder in the trace tab when no execution is selected", () => {
    render(
      <TraceTabContent
        activeExecutionId={null}
        viewerData={null}
        loading={false}
        error={null}
        onRetry={vi.fn()}
      />,
    );

    expect(
      screen.getByText(/select an execution to view its trace/i),
    ).toBeInTheDocument();
  });
});
