import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Workflow } from "@features/workflow/data/workflow-data";
import { listWorkflows } from "@features/workflow/lib/workflow-storage";
import type { StoredWorkflow } from "@features/workflow/lib/workflow-storage.types";
import { useWorkflowGalleryState } from "./use-workflow-gallery-state";

vi.mock("@features/workflow/data/workflow-data", () => ({
  SAMPLE_WORKFLOWS: [
    {
      id: "template-1",
      name: "Agent Template",
      description: "Starter template",
      createdAt: "2026-01-05T00:00:00.000Z",
      updatedAt: "2026-01-06T00:00:00.000Z",
      owner: { id: "user-1", name: "Owner", avatar: "" },
      tags: ["template"],
      nodes: [],
      edges: [],
    },
    {
      id: "template-2",
      name: "Notifier Template",
      description: "Another starter",
      createdAt: "2026-01-07T00:00:00.000Z",
      updatedAt: "2026-01-08T00:00:00.000Z",
      owner: { id: "user-1", name: "Owner", avatar: "" },
      tags: ["template"],
      nodes: [],
      edges: [],
    },
  ] satisfies Workflow[],
}));

vi.mock("@features/workflow/lib/workflow-storage", () => ({
  listWorkflows: vi.fn(),
  WORKFLOW_STORAGE_EVENT: "workflow-storage-updated",
}));

const mockedListWorkflows = vi.mocked(listWorkflows);

const STORED_WORKFLOWS: StoredWorkflow[] = [
  {
    id: "workflow-1",
    name: "Agent Ops",
    description: "Favorite internal workflow",
    createdAt: "2026-01-01T00:00:00.000Z",
    updatedAt: "2026-01-04T00:00:00.000Z",
    owner: { id: "user-1", name: "Owner", avatar: "" },
    tags: ["favorite"],
    nodes: [],
    edges: [],
    versions: [],
  },
  {
    id: "workflow-2",
    name: "Shared Inbox",
    description: "Shared with the team",
    createdAt: "2026-01-02T00:00:00.000Z",
    updatedAt: "2026-01-03T00:00:00.000Z",
    owner: { id: "user-2", name: "Teammate", avatar: "" },
    tags: [],
    nodes: [],
    edges: [],
    versions: [],
  },
  {
    id: "workflow-3",
    name: "Reporter",
    description: "Daily reporting",
    createdAt: "2026-01-03T00:00:00.000Z",
    updatedAt: "2026-01-02T00:00:00.000Z",
    owner: { id: "user-1", name: "Owner", avatar: "" },
    tags: [],
    nodes: [],
    edges: [],
    versions: [],
  },
];

describe("useWorkflowGalleryState", () => {
  beforeEach(() => {
    mockedListWorkflows.mockReset();
    mockedListWorkflows.mockResolvedValue(STORED_WORKFLOWS);
  });

  it("computes tab counts for workspace workflows and templates", async () => {
    const { result } = renderHook(() => useWorkflowGalleryState());

    await waitFor(() => {
      expect(result.current.isLoadingWorkflows).toBe(false);
    });

    expect(result.current.tabCounts).toEqual({
      all: 3,
      favorites: 1,
      shared: 1,
      templates: 2,
    });

    act(() => {
      result.current.setSearchQuery("agent");
    });

    await waitFor(() => {
      expect(result.current.tabCounts).toEqual({
        all: 1,
        favorites: 1,
        shared: 0,
        templates: 1,
      });
    });
  });
});
