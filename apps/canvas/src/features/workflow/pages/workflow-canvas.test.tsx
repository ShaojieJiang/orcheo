import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import WorkflowCanvas from "./workflow-canvas";

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

afterEach(() => {
  cleanup();
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

describe("WorkflowCanvas tabs", () => {
  it("shows workflow tab and hides editor/execution tabs", async () => {
    renderCanvas();

    expect(await screen.findByRole("tab", { name: /workflow/i })).toBeVisible();
    expect(
      screen.queryByRole("tab", { name: /^editor$/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("tab", { name: /^execution$/i }),
    ).not.toBeInTheDocument();
  });

  it("keeps trace/readiness/settings tabs available", async () => {
    renderCanvas();

    expect(await screen.findByRole("tab", { name: /trace/i })).toBeVisible();
    expect(screen.getByRole("tab", { name: /readiness/i })).toBeVisible();
    expect(screen.getByRole("tab", { name: /settings/i })).toBeVisible();
  });

  it("renders workflow mermaid empty state when no versions exist", async () => {
    renderCanvas();

    expect(
      await screen.findByText(
        /save this workflow to generate a versioned mermaid diagram/i,
      ),
    ).toBeInTheDocument();
  });
});
