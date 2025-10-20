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
  it("duplicates selected nodes and supports undo/redo", async () => {
    renderCanvas();

    await screen.findAllByText("Initial Node");

    const undoButton = screen.getByRole("button", { name: /undo/i });
    const redoButton = screen.getByRole("button", { name: /redo/i });
    expect(undoButton).toBeDisabled();
    expect(redoButton).toBeDisabled();

    const actionsButton = screen.getByRole("button", { name: /more actions/i });
    fireEvent.pointerDown(actionsButton);
    fireEvent.click(actionsButton);

    const duplicateItem = await screen.findByTestId(
      "duplicate-workflow-menu-item",
    );
    fireEvent.click(duplicateItem);

    await screen.findByText(/initial node copy/i);
    await waitFor(() => expect(undoButton).not.toBeDisabled());

    fireEvent.click(undoButton);

    await waitFor(() =>
      expect(screen.queryByText(/initial node copy/i)).not.toBeInTheDocument(),
    );
    await waitFor(() => expect(redoButton).not.toBeDisabled());

    fireEvent.click(redoButton);
    await screen.findByText(/initial node copy/i);
  });
});

describe("WorkflowCanvas search", () => {
  it("opens the workflow search overlay and syncs with the sidebar", async () => {
    renderCanvas();

    fireEvent.keyDown(window, { key: "f", ctrlKey: true });

    const searchInput = await screen.findByRole("textbox", {
      name: /search workflow nodes/i,
    });

    fireEvent.change(searchInput, { target: { value: "initial" } });

    await screen.findByText(/1 of 1/i);

    const sidebarSearch = screen.getByPlaceholderText("Search nodes...");
    expect(sidebarSearch).toHaveValue("initial");

    await waitFor(() => {
      const highlighted = document.querySelectorAll(
        '[data-search-match="true"]',
      );
      expect(highlighted.length).toBeGreaterThan(0);
    });

    const clearButton = screen.getByRole("button", { name: /clear search/i });
    fireEvent.click(clearButton);

    await waitFor(() =>
      expect(document.querySelector('[data-search-match="true"]')).toBeNull(),
    );
    expect(sidebarSearch).toHaveValue("");
  });
});
