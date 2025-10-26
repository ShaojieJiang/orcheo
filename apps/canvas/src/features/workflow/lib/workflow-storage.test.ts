import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  WORKFLOW_STORAGE_EVENT,
  listWorkflows,
  saveWorkflow,
} from "./workflow-storage";

const mockFetch = vi.fn<Parameters<typeof fetch>, ReturnType<typeof fetch>>();

const jsonResponse = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });

const queueResponses = (responses: Response[]) => {
  const queue = [...responses];
  mockFetch.mockImplementation(() => {
    const next = queue.shift();
    if (!next) {
      throw new Error("No more mocked responses available");
    }
    return Promise.resolve(next);
  });
};

beforeEach(() => {
  mockFetch.mockReset();
  globalThis.fetch = mockFetch as unknown as typeof fetch;
});

describe("workflow-storage API integration", () => {
  it("saves workflows by invoking the backend endpoints", async () => {
    const timestamp = new Date().toISOString();
    const snapshot = {
      name: "Marketing qualification",
      description: "Scores inbound leads and routes them to reps.",
      nodes: [
        {
          id: "trigger-1",
          type: "trigger",
          position: { x: 0, y: 0 },
          data: {
            type: "trigger",
            label: "Webhook trigger",
            description: "Starts the workflow when a webhook fires.",
            status: "idle" as const,
          },
        },
      ],
      edges: [],
    };

    queueResponses([
      jsonResponse({
        id: "workflow-123",
        name: snapshot.name,
        slug: "workflow-123",
        description: snapshot.description,
        tags: ["draft"],
        is_archived: false,
        created_at: timestamp,
        updated_at: timestamp,
      }),
      jsonResponse({
        id: "version-1",
        workflow_id: "workflow-123",
        version: 1,
        graph: { nodes: [], edges: [] },
        metadata: {},
        notes: "Initial draft",
        created_by: "canvas-app",
        created_at: timestamp,
        updated_at: timestamp,
      }),
      jsonResponse({
        id: "workflow-123",
        name: snapshot.name,
        slug: "workflow-123",
        description: snapshot.description,
        tags: ["draft"],
        is_archived: false,
        created_at: timestamp,
        updated_at: timestamp,
      }),
      jsonResponse([
        {
          id: "version-1",
          workflow_id: "workflow-123",
          version: 1,
          graph: { nodes: [], edges: [] },
          metadata: {
            canvas: {
              snapshot,
              summary: { added: 0, removed: 0, modified: 0 },
              message: "Initial draft",
            },
          },
          notes: "Initial draft",
          created_by: "canvas-app",
          created_at: timestamp,
          updated_at: timestamp,
        },
      ]),
    ]);

    const listener = vi.fn();
    window.addEventListener(WORKFLOW_STORAGE_EVENT, listener);

    const saved = await saveWorkflow(
      {
        name: snapshot.name,
        description: snapshot.description,
        tags: ["draft"],
        nodes: snapshot.nodes,
        edges: snapshot.edges,
      },
      { versionMessage: "Initial draft" },
    );

    expect(saved.id).toBe("workflow-123");
    expect(saved.versions).toHaveLength(1);
    expect(saved.nodes).toHaveLength(1);
    expect(listener).toHaveBeenCalled();

    const versionPayload = JSON.parse(
      (mockFetch.mock.calls[1]?.[1]?.body ?? "{}") as string,
    );

    expect(versionPayload.metadata.canvas.snapshot.nodes[0]?.id).toBe(
      "trigger-1",
    );

    window.removeEventListener(WORKFLOW_STORAGE_EVENT, listener);

    expect(mockFetch).toHaveBeenCalledTimes(4);
    expect(String(mockFetch.mock.calls[0]?.[0])).toContain("/api/workflows");
    expect(String(mockFetch.mock.calls[1]?.[0])).toContain(
      "/api/workflows/workflow-123/versions",
    );
  });

  it("lists workflows by merging backing metadata", async () => {
    const timestamp = new Date().toISOString();
    queueResponses([
      jsonResponse([
        {
          id: "workflow-abc",
          name: "Support triage",
          slug: "workflow-abc",
          description: "Routes support tickets to the right queue.",
          tags: ["support"],
          is_archived: false,
          created_at: timestamp,
          updated_at: timestamp,
        },
      ]),
      jsonResponse([
        {
          id: "version-1",
          workflow_id: "workflow-abc",
          version: 1,
          graph: {},
          metadata: {
            canvas: {
              snapshot: {
                name: "Support triage",
                description: "Routes support tickets to the right queue.",
                nodes: [
                  {
                    id: "start",
                    type: "trigger",
                    position: { x: 0, y: 0 },
                    data: { label: "Start" },
                  },
                ],
                edges: [],
              },
              summary: { added: 0, removed: 0, modified: 0 },
              message: "Initial draft",
            },
          },
          notes: null,
          created_by: "canvas-app",
          created_at: timestamp,
          updated_at: timestamp,
        },
      ]),
    ]);

    const workflows = await listWorkflows();

    expect(workflows).toHaveLength(1);
    expect(workflows[0]?.nodes).toHaveLength(1);
    expect(workflows[0]?.versions[0]?.summary.modified).toBe(0);
    expect(mockFetch).toHaveBeenCalledTimes(2);
  });

  it("saves nodes without runtime data or status when pre-sanitized", async () => {
    const timestamp = new Date().toISOString();
    // This test verifies that saveWorkflow preserves node data as-is.
    // In the real flow, workflow-canvas.tsx sanitizes nodes via toPersistedNode()
    // before calling saveWorkflow(), which excludes the runtime and status fields.
    const sanitizedNodes = [
      {
        id: "node-1",
        type: "default",
        position: { x: 100, y: 100 },
        data: {
          type: "ai",
          label: "AI Node",
          description: "An AI node",
          prompt: "Hello world",
          // Runtime data and status have already been stripped by toPersistedNode()
        },
      },
    ];

    const snapshot = {
      name: "Test Workflow",
      description: "Test workflow with sanitized data",
      nodes: sanitizedNodes,
      edges: [],
    };

    queueResponses([
      jsonResponse({
        id: "workflow-456",
        name: snapshot.name,
        slug: "workflow-456",
        description: snapshot.description,
        tags: [],
        is_archived: false,
        created_at: timestamp,
        updated_at: timestamp,
      }),
      jsonResponse({
        id: "version-1",
        workflow_id: "workflow-456",
        version: 1,
        graph: { nodes: [], edges: [] },
        metadata: {},
        notes: "Test save",
        created_by: "canvas-app",
        created_at: timestamp,
        updated_at: timestamp,
      }),
      jsonResponse({
        id: "workflow-456",
        name: snapshot.name,
        slug: "workflow-456",
        description: snapshot.description,
        tags: [],
        is_archived: false,
        created_at: timestamp,
        updated_at: timestamp,
      }),
      jsonResponse([
        {
          id: "version-1",
          workflow_id: "workflow-456",
          version: 1,
          graph: { nodes: [], edges: [] },
          metadata: {
            canvas: {
              snapshot,
              summary: { added: 0, removed: 0, modified: 0 },
              message: "Test save",
            },
          },
          notes: "Test save",
          created_by: "canvas-app",
          created_at: timestamp,
          updated_at: timestamp,
        },
      ]),
    ]);

    await saveWorkflow(
      {
        name: snapshot.name,
        description: snapshot.description,
        tags: [],
        nodes: sanitizedNodes,
        edges: snapshot.edges,
      },
      { versionMessage: "Test save" },
    );

    // Get the version creation payload
    const versionPayload = JSON.parse(
      (mockFetch.mock.calls[1]?.[1]?.body ?? "{}") as string,
    );

    const savedNode = versionPayload.metadata.canvas.snapshot.nodes[0];

    // Verify runtime data and status are not present
    expect(savedNode).toBeDefined();
    expect(savedNode.data.runtime).toBeUndefined();
    expect(savedNode.data.status).toBeUndefined();

    // Verify expected data was preserved
    expect(savedNode.data.label).toBe("AI Node");
    expect(savedNode.data.description).toBe("An AI node");
    expect(savedNode.data.prompt).toBe("Hello world");
    expect(savedNode.data.type).toBe("ai");
  });
});
