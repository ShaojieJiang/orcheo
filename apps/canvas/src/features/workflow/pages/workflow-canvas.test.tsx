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
      value: vi.fn(() => `test-node-${Math.random().toString(36).slice(2, 10)}`),
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
  it("duplicates selected nodes and toggles undo/redo state", async () => {
    renderCanvas();

    await screen.findByText("Initial Node");

    const moreActionsButton = screen.getByRole("button", { name: /more actions/i });
    fireEvent.pointerDown(moreActionsButton);
    fireEvent.click(moreActionsButton);

    const duplicateItem = await screen.findByText(/duplicate/i);
    fireEvent.click(duplicateItem);

    await waitFor(() => {
      expect(screen.getByText(/Initial Node Copy/i)).toBeInTheDocument();
    });

    const undoButton = screen.getByRole("button", { name: /undo/i });
    expect(undoButton).not.toBeDisabled();

    fireEvent.click(undoButton);

    await waitFor(() => {
      expect(screen.queryByText(/Initial Node Copy/i)).not.toBeInTheDocument();
    });

    const redoButton = screen.getByRole("button", { name: /redo/i });
    expect(redoButton).not.toBeDisabled();

    fireEvent.click(redoButton);

    await waitFor(() => {
      expect(screen.getByText(/Initial Node Copy/i)).toBeInTheDocument();
    });
  });
});
