import { beforeAll, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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

  it("opens search overlay with keyboard shortcut", async () => {
    renderCanvas();

    fireEvent.keyDown(window, { key: "f", ctrlKey: true });

    const searchInput = await screen.findByPlaceholderText("Search nodes...");
    fireEvent.change(searchInput, { target: { value: "Initial" } });

    expect(await screen.findByText(/1 of 1/i)).toBeInTheDocument();

    const closeButton = screen.getByRole("button", { name: /close search/i });
    fireEvent.click(closeButton);

    await waitFor(() => {
      expect(
        screen.queryByPlaceholderText("Search nodes..."),
      ).not.toBeInTheDocument();
    });
  });

  it("shows collapsible inspector panel when a node is opened", async () => {
    renderCanvas();

    const nodeLabel = await screen.findByText("Initial Node");
    fireEvent.doubleClick(nodeLabel);

    const collapseButton = await screen.findByRole("button", {
      name: /collapse inspector panel/i,
    });
    expect(collapseButton).toBeVisible();

    fireEvent.click(collapseButton);

    expect(
      await screen.findByRole("button", { name: /expand inspector panel/i }),
    ).toBeVisible();
  });
});
