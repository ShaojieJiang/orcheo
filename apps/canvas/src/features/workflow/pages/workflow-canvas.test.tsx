import { beforeAll, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import userEvent from "@testing-library/user-event";
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

const renderCanvas = (
  nodes?: Array<{
    id: string;
    type: string;
    position: { x: number; y: number };
    data: Record<string, unknown>;
    selected?: boolean;
    draggable?: boolean;
  }>,
) => {
  const initialNodes = nodes ?? [
    {
      id: "node-1",
      type: "default" as const,
      position: { x: 0, y: 0 },
      data: {
        type: "default",
        label: "Initial Node",
        status: "idle" as const,
      },
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
  it("duplicates nodes and allows undo/redo via controls", async () => {
    renderCanvas();

    await screen.findByText("Initial Node");

    const user = userEvent.setup();
    const undoButton = screen.getByRole("button", { name: /undo/i });
    const redoButton = screen.getByRole("button", { name: /redo/i });

    expect(undoButton).toBeDisabled();
    expect(redoButton).toBeDisabled();

    await user.click(screen.getByRole("button", { name: /more actions/i }));
    const duplicateMenuItem = await screen.findByTestId(
      "duplicate-workflow-menu-item",
    );
    await user.click(duplicateMenuItem);

    await screen.findByText("Initial Node Copy");
    await waitFor(() => expect(undoButton).not.toBeDisabled());
    expect(redoButton).toBeDisabled();

    await user.click(undoButton);
    await waitFor(() =>
      expect(screen.queryByText("Initial Node Copy")).toBeNull(),
    );
    await waitFor(() => expect(redoButton).not.toBeDisabled());

    await user.click(redoButton);
    await screen.findByText("Initial Node Copy");
  });

  it("supports keyboard shortcuts for undo and redo", async () => {
    renderCanvas();

    await screen.findByText("Initial Node");

    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: /more actions/i }));
    const duplicateMenuItem = await screen.findByTestId(
      "duplicate-workflow-menu-item",
    );
    await user.click(duplicateMenuItem);
    await screen.findByText("Initial Node Copy");

    await user.keyboard("{Control>}{z}{/Control}");
    await waitFor(() =>
      expect(screen.queryByText("Initial Node Copy")).toBeNull(),
    );

    await user.keyboard("{Control>}{Shift>}{z}{/Shift}{/Control}");
    await screen.findByText("Initial Node Copy");
  });
});

describe("WorkflowCanvas search", () => {
  it("opens the search overlay and navigates results", async () => {
    const user = userEvent.setup();
    renderCanvas([
      {
        id: "alpha",
        type: "default",
        position: { x: 0, y: 0 },
        data: { type: "default", label: "Alpha Node", status: "idle" },
      },
      {
        id: "beta",
        type: "default",
        position: { x: 160, y: 40 },
        data: { type: "default", label: "Beta Node", status: "idle" },
      },
      {
        id: "gamma",
        type: "default",
        position: { x: 320, y: 80 },
        data: { type: "default", label: "Gamma Step", status: "idle" },
      },
    ]);

    await screen.findByText("Alpha Node");

    await user.keyboard("{Control>}{f}{/Control}");
    const searchInput = await screen.findByPlaceholderText("Search nodes...");
    await user.type(searchInput, "node");

    await screen.findByText("1 of 2");
    expect(
      screen.getByText("Alpha Node").closest('[data-search-active="true"]'),
    ).not.toBeNull();

    expect(
      screen.getByText("Gamma Step").closest('[data-search-dimmed="true"]'),
    ).not.toBeNull();

    await user.keyboard("{Enter}");
    await waitFor(() =>
      expect(
        screen.getByText("Beta Node").closest('[data-search-active="true"]'),
      ).not.toBeNull(),
    );

    await user.keyboard("{Shift>}{Enter}{/Shift}");
    await waitFor(() =>
      expect(
        screen.getByText("Alpha Node").closest('[data-search-active="true"]'),
      ).not.toBeNull(),
    );

    await user.keyboard("{Escape}");
    await waitFor(() =>
      expect(
        screen.queryByPlaceholderText("Search nodes..."),
      ).not.toBeInTheDocument(),
    );

    await waitFor(() =>
      expect(
        screen.getByText("Alpha Node").closest("[data-search-active]") ?? null,
      ).toBeNull(),
    );
    expect(
      screen.getByText("Gamma Step").closest("[data-search-dimmed]") ?? null,
    ).toBeNull();
  });
});
