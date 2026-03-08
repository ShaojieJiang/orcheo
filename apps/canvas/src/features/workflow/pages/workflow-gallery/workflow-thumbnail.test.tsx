import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, waitFor } from "@testing-library/react";

import { WorkflowThumbnail } from "./workflow-thumbnail";

const mermaidRendererMock = vi.hoisted(() => ({
  buildMermaidCacheKey: vi.fn(),
  buildMermaidRenderId: vi.fn(),
  forceMermaidLeftToRight: vi.fn((source: string) =>
    source.replace(/\b(?:TB|TD|BT|RL|LR)\b/, "LR"),
  ),
  renderMermaidSvg: vi.fn(),
}));

vi.mock("@features/workflow/lib/mermaid-renderer", () => ({
  buildMermaidCacheKey: mermaidRendererMock.buildMermaidCacheKey,
  buildMermaidRenderId: mermaidRendererMock.buildMermaidRenderId,
  forceMermaidLeftToRight: mermaidRendererMock.forceMermaidLeftToRight,
  renderMermaidSvg: mermaidRendererMock.renderMermaidSvg,
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
  mermaidRendererMock.buildMermaidCacheKey.mockReset();
  mermaidRendererMock.buildMermaidRenderId.mockReset();
  mermaidRendererMock.forceMermaidLeftToRight.mockClear();
  mermaidRendererMock.renderMermaidSvg.mockReset();
});

describe("WorkflowThumbnail", () => {
  it("uses fallback thumbnail when workflow has no Mermaid source", () => {
    const { container } = render(<WorkflowThumbnail workflow={baseWorkflow} />);

    expect(
      container.querySelector(".workflow-thumbnail-fallback"),
    ).not.toBeNull();
    expect(container.querySelector(".workflow-thumbnail-mermaid")).toBeNull();
    expect(mermaidRendererMock.renderMermaidSvg).not.toHaveBeenCalled();
  });

  it("renders Mermaid thumbnail when latest version contains Mermaid source", async () => {
    mermaidRendererMock.buildMermaidCacheKey.mockReturnValue("cache-key");
    mermaidRendererMock.buildMermaidRenderId.mockReturnValue("render-id");
    mermaidRendererMock.renderMermaidSvg.mockResolvedValue(
      '<svg data-testid="mermaid-preview"></svg>',
    );

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
      expect(mermaidRendererMock.renderMermaidSvg).toHaveBeenCalledWith({
        source: "flowchart LR\nA[Start] --> B[End]",
        cacheKey: "cache-key",
        renderId: "render-id",
      });
    });
    expect(mermaidRendererMock.forceMermaidLeftToRight).toHaveBeenCalledWith(
      "flowchart TD\nA[Start] --> B[End]",
    );

    await waitFor(() => {
      expect(
        container.querySelector(".workflow-thumbnail-mermaid svg"),
      ).not.toBeNull();
    });

    const thumbnailRoot = container.querySelector(
      ".workflow-thumbnail-mermaid",
    );
    expect(thumbnailRoot?.className).toContain("items-center");
    expect(thumbnailRoot?.className).toContain("justify-center");

    expect(container.querySelector(".workflow-thumbnail-fallback")).toBeNull();
  });

  it("shows loading placeholder instead of fallback while Mermaid is rendering", () => {
    mermaidRendererMock.buildMermaidCacheKey.mockReturnValue("cache-key");
    mermaidRendererMock.buildMermaidRenderId.mockReturnValue("render-id");
    mermaidRendererMock.renderMermaidSvg.mockImplementation(
      () =>
        new Promise(() => {
          // Keep promise pending to validate the loading state.
        }),
    );

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

    expect(
      container.querySelector(".workflow-thumbnail-loading"),
    ).not.toBeNull();
    expect(container.querySelector(".workflow-thumbnail-fallback")).toBeNull();
  });
});
