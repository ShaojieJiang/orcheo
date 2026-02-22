import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, waitFor } from "@testing-library/react";

import { WorkflowThumbnail } from "./workflow-thumbnail";

const mermaidMock = vi.hoisted(() => ({
  initialize: vi.fn(),
  render: vi.fn(),
}));

vi.mock("mermaid", () => ({
  default: {
    initialize: mermaidMock.initialize,
    render: mermaidMock.render,
  },
}));

const baseWorkflow = {
  id: "workflow-1",
  name: "Support triage",
  description: "Routes inbound requests.",
  createdAt: "2026-01-01T00:00:00.000Z",
  updatedAt: "2026-01-02T00:00:00.000Z",
  owner: {
    id: "owner-1",
    name: "Owner",
    avatar: "https://example.com/avatar.png",
  },
  tags: ["support", "triage"],
  nodes: [],
  edges: [],
} satisfies Parameters<typeof WorkflowThumbnail>[0]["workflow"];

afterEach(() => {
  cleanup();
  mermaidMock.initialize.mockClear();
  mermaidMock.render.mockReset();
});

describe("WorkflowThumbnail", () => {
  it("uses fallback thumbnail when workflow has no Mermaid source", () => {
    const { container } = render(<WorkflowThumbnail workflow={baseWorkflow} />);

    expect(
      container.querySelector(".workflow-thumbnail-fallback"),
    ).not.toBeNull();
    expect(container.querySelector(".workflow-thumbnail-mermaid")).toBeNull();
    expect(mermaidMock.render).not.toHaveBeenCalled();
  });

  it("renders Mermaid thumbnail when latest version contains Mermaid source", async () => {
    mermaidMock.render.mockResolvedValue({
      svg: '<svg data-testid="mermaid-preview"></svg>',
    });

    const workflowWithMermaid = {
      ...baseWorkflow,
      versions: [
        {
          id: "v1",
          mermaid: "flowchart TD\nA[Start] --> B[End]",
        },
      ],
    };

    const { container } = render(
      <WorkflowThumbnail workflow={workflowWithMermaid} />,
    );

    await waitFor(() => {
      expect(mermaidMock.render).toHaveBeenCalledWith(
        "workflow-gallery-mermaid-workflow-1-v1",
        "flowchart TD\nA[Start] --> B[End]",
      );
    });

    await waitFor(() => {
      expect(
        container.querySelector(".workflow-thumbnail-mermaid svg"),
      ).not.toBeNull();
    });

    expect(container.querySelector(".workflow-thumbnail-fallback")).toBeNull();
    expect(mermaidMock.initialize).toHaveBeenCalledTimes(1);
  });
});
