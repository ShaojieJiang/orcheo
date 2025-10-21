import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  WORKFLOW_STORAGE_EVENT,
  clearWorkflowStorage,
  createWorkflow,
  createWorkflowFromTemplate,
  deleteWorkflow,
  duplicateWorkflow,
  getVersionSnapshot,
  listWorkflows,
  saveWorkflow,
} from "./workflow-storage";

const baseNode = {
  id: "trigger-1",
  type: "trigger" as const,
  position: { x: 0, y: 0 },
  data: {
    type: "trigger" as const,
    label: "Webhook trigger",
    description: "Starts the workflow when a webhook fires.",
    status: "idle" as const,
  },
};

const updatedNode = {
  ...baseNode,
  data: {
    ...baseNode.data,
    label: "Webhook trigger (updated)",
  },
};

beforeEach(() => {
  clearWorkflowStorage();
  window.localStorage.clear();
});

describe("workflow-storage", () => {
  it("creates and persists workflows while notifying listeners", () => {
    const listener = vi.fn();
    window.addEventListener(WORKFLOW_STORAGE_EVENT, listener);

    const workflow = createWorkflow({
      name: "Marketing qualification",
      description: "Scores inbound leads and routes them to reps.",
      nodes: [baseNode],
      edges: [],
    });

    expect(workflow.id).toMatch(/^workflow-/);
    expect(listWorkflows()).toHaveLength(1);
    expect(listener).toHaveBeenCalled();

    window.removeEventListener(WORKFLOW_STORAGE_EVENT, listener);
  });

  it("tracks version history whenever the workflow graph changes", () => {
    const workflow = createWorkflow({
      name: "Onboarding journey",
      description: "Collects documents and provisions access.",
      nodes: [baseNode],
      edges: [],
    });

    const firstSave = saveWorkflow(
      {
        id: workflow.id,
        name: "Onboarding journey",
        description: "Collects documents and provisions access.",
        nodes: [baseNode],
        edges: [],
      },
      { versionMessage: "Initial draft" },
    );

    expect(firstSave.versions).toHaveLength(1);
    expect(firstSave.versions[0]?.message).toContain("Initial draft");

    const secondSave = saveWorkflow(
      {
        id: workflow.id,
        name: "Onboarding journey",
        description: "Collects documents and provisions access.",
        nodes: [updatedNode],
        edges: [],
      },
      { versionMessage: "Updated webhook copy" },
    );

    expect(secondSave.versions).toHaveLength(2);
    const latest = secondSave.versions.at(-1);
    expect(latest?.summary.modified).toBeGreaterThanOrEqual(1);
    expect(getVersionSnapshot(secondSave.id, latest?.id ?? "")).toMatchObject({
      name: "Onboarding journey",
      nodes: [updatedNode],
    });
  });

  it("duplicates and removes workflows to support CRUD operations", () => {
    const original = createWorkflow({
      name: "Support triage",
      nodes: [baseNode],
      edges: [],
    });

    const copy = duplicateWorkflow(original.id);
    expect(copy).toBeTruthy();
    expect(copy?.id).not.toEqual(original.id);
    expect(listWorkflows()).toHaveLength(2);

    if (copy) {
      deleteWorkflow(copy.id);
    }

    expect(listWorkflows()).toHaveLength(1);
  });

  it("creates workflows from curated templates", () => {
    const template = createWorkflowFromTemplate("workflow-quickstart");
    expect(template).toBeTruthy();
    expect(template?.tags).not.toContain("template");
  });
});
