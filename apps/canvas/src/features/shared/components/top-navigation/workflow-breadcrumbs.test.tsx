import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import WorkflowBreadcrumbs from "@/features/shared/components/top-navigation/workflow-breadcrumbs";

afterEach(() => {
  cleanup();
});

describe("WorkflowBreadcrumbs", () => {
  it("renders workflow name once when path already includes it", () => {
    render(
      <MemoryRouter>
        <WorkflowBreadcrumbs
          currentWorkflow={{
            name: "Simple Agent Copy",
            path: ["Projects", "Workflows", "Simple Agent Copy"],
          }}
          windowWidth={1280}
        />
      </MemoryRouter>,
    );

    expect(screen.getAllByText("Simple Agent Copy")).toHaveLength(1);
  });

  it("renders workflow name when path is empty", () => {
    render(
      <MemoryRouter>
        <WorkflowBreadcrumbs
          currentWorkflow={{ name: "My Workflow" }}
          windowWidth={1280}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("My Workflow")).toBeInTheDocument();
  });

  it("shows double-click tooltip when onNameChange is provided", () => {
    render(
      <MemoryRouter>
        <WorkflowBreadcrumbs
          currentWorkflow={{
            name: "Editable Workflow",
            path: ["Projects", "Workflows"],
            onNameChange: vi.fn(),
          }}
          windowWidth={1280}
        />
      </MemoryRouter>,
    );

    const nameSpan = screen.getByTestId("workflow-name-display");
    expect(nameSpan).toHaveAttribute("title", "Double-click to rename");
  });

  it("does not show tooltip without onNameChange", () => {
    render(
      <MemoryRouter>
        <WorkflowBreadcrumbs
          currentWorkflow={{
            name: "Read Only",
            path: ["Projects", "Workflows"],
          }}
          windowWidth={1280}
        />
      </MemoryRouter>,
    );

    const nameSpan = screen.getByTestId("workflow-name-display");
    expect(nameSpan).not.toHaveAttribute("title");
  });

  it("enters edit mode on double-click and commits on Enter", () => {
    const onNameChange = vi.fn();
    render(
      <MemoryRouter>
        <WorkflowBreadcrumbs
          currentWorkflow={{
            name: "Old Name",
            path: ["Projects", "Workflows"],
            onNameChange,
          }}
          windowWidth={1280}
        />
      </MemoryRouter>,
    );

    const nameSpan = screen.getByTestId("workflow-name-display");
    fireEvent.doubleClick(nameSpan);

    const input = screen.getByRole("textbox");
    expect(input).toBeInTheDocument();
    expect(input).toHaveValue("Old Name");

    fireEvent.change(input, { target: { value: "New Name" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(onNameChange).toHaveBeenCalledWith("New Name");
  });

  it("cancels edit on Escape without calling onNameChange", () => {
    const onNameChange = vi.fn();
    render(
      <MemoryRouter>
        <WorkflowBreadcrumbs
          currentWorkflow={{
            name: "Original",
            path: ["Projects", "Workflows"],
            onNameChange,
          }}
          windowWidth={1280}
        />
      </MemoryRouter>,
    );

    const nameSpan = screen.getByTestId("workflow-name-display");
    fireEvent.doubleClick(nameSpan);

    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "Changed" } });
    fireEvent.keyDown(input, { key: "Escape" });

    expect(onNameChange).not.toHaveBeenCalled();
    expect(screen.getByText("Original")).toBeInTheDocument();
  });

  it("does not call onNameChange when value is unchanged", () => {
    const onNameChange = vi.fn();
    render(
      <MemoryRouter>
        <WorkflowBreadcrumbs
          currentWorkflow={{
            name: "Same Name",
            path: ["Projects", "Workflows"],
            onNameChange,
          }}
          windowWidth={1280}
        />
      </MemoryRouter>,
    );

    const nameSpan = screen.getByTestId("workflow-name-display");
    fireEvent.doubleClick(nameSpan);

    const input = screen.getByRole("textbox");
    fireEvent.keyDown(input, { key: "Enter" });

    expect(onNameChange).not.toHaveBeenCalled();
  });

  it("commits on blur", () => {
    const onNameChange = vi.fn();
    render(
      <MemoryRouter>
        <WorkflowBreadcrumbs
          currentWorkflow={{
            name: "Blur Test",
            path: ["Projects", "Workflows"],
            onNameChange,
          }}
          windowWidth={1280}
        />
      </MemoryRouter>,
    );

    const nameSpan = screen.getByTestId("workflow-name-display");
    fireEvent.doubleClick(nameSpan);

    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "After Blur" } });
    fireEvent.blur(input);

    expect(onNameChange).toHaveBeenCalledWith("After Blur");
  });

  it("does not call onNameChange for empty/whitespace input", () => {
    const onNameChange = vi.fn();
    render(
      <MemoryRouter>
        <WorkflowBreadcrumbs
          currentWorkflow={{
            name: "No Empty",
            path: ["Projects", "Workflows"],
            onNameChange,
          }}
          windowWidth={1280}
        />
      </MemoryRouter>,
    );

    const nameSpan = screen.getByTestId("workflow-name-display");
    fireEvent.doubleClick(nameSpan);

    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "   " } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(onNameChange).not.toHaveBeenCalled();
  });

  it("works with empty path and editable name", () => {
    const onNameChange = vi.fn();
    render(
      <MemoryRouter>
        <WorkflowBreadcrumbs
          currentWorkflow={{
            name: "No Path",
            onNameChange,
          }}
          windowWidth={1280}
        />
      </MemoryRouter>,
    );

    const nameSpan = screen.getByTestId("workflow-name-display");
    fireEvent.doubleClick(nameSpan);

    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "Renamed" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(onNameChange).toHaveBeenCalledWith("Renamed");
  });
});
