import { describe, expect, it } from "vitest";

import { saveWorkflow } from "./workflow-storage";
import {
  getFetchMock,
  jsonResponse,
  queueResponses,
  setupFetchMock,
} from "./workflow-storage.test-helpers";

setupFetchMock();

describe("workflow-storage API integration - sanitized nodes", () => {
  it("saves nodes without runtime data or status when pre-sanitized", async () => {
    const mockFetch = getFetchMock();
    const timestamp = new Date().toISOString();
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

    const versionPayload = JSON.parse(
      (mockFetch.mock.calls[1]?.[1]?.body ?? "{}") as string,
    );

    const savedNode = versionPayload.metadata.canvas.snapshot.nodes[0];

    expect(savedNode).toBeDefined();
    expect(savedNode.data.runtime).toBeUndefined();
    expect(savedNode.data.status).toBeUndefined();
    expect(savedNode.data.label).toBe("AI Node");
    expect(savedNode.data.description).toBe("An AI node");
    expect(savedNode.data.prompt).toBe("Hello world");
    expect(savedNode.data.type).toBe("ai");
  });
});
