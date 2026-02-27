import { describe, expect, it, vi } from "vitest";

import { WORKFLOW_STORAGE_EVENT, saveWorkflow } from "./workflow-storage";
import {
  getFetchMock,
  jsonResponse,
  queueResponses,
  setupFetchMock,
} from "./workflow-storage.test-helpers";

setupFetchMock();

describe("workflow-storage API integration - save workflow", () => {
  it("saves workflows by invoking the backend endpoints", async () => {
    const mockFetch = getFetchMock();
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

  it("uses default actor when no explicit actor is provided", async () => {
    const mockFetch = getFetchMock();
    const timestamp = new Date().toISOString();
    const subject = "auth0|user-123";
    const tokenPayload = btoa(
      JSON.stringify({
        sub: subject,
        scope: "workflows:read workflows:execute",
      }),
    )
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/, "");
    const token = `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.${tokenPayload}.sig`;
    window.localStorage.setItem(
      "orcheo_canvas_auth_tokens",
      JSON.stringify({ accessToken: token }),
    );

    queueResponses([
      jsonResponse({
        id: "workflow-actor",
        name: "Workflow with token subject actor",
        slug: "workflow-actor",
        description: "",
        tags: ["draft"],
        is_archived: false,
        created_at: timestamp,
        updated_at: timestamp,
      }),
      jsonResponse({
        id: "version-1",
        workflow_id: "workflow-actor",
        version: 1,
        graph: { nodes: [], edges: [] },
        metadata: {},
        notes: "Initial draft",
        created_by: subject,
        created_at: timestamp,
        updated_at: timestamp,
      }),
      jsonResponse({
        id: "workflow-actor",
        name: "Workflow with token subject actor",
        slug: "workflow-actor",
        description: "",
        tags: ["draft"],
        is_archived: false,
        created_at: timestamp,
        updated_at: timestamp,
      }),
      jsonResponse([
        {
          id: "version-1",
          workflow_id: "workflow-actor",
          version: 1,
          graph: { nodes: [], edges: [] },
          metadata: {
            canvas: {
              snapshot: {
                name: "Workflow with token subject actor",
                description: "",
                nodes: [],
                edges: [],
              },
              summary: { added: 0, removed: 0, modified: 0 },
              message: "Initial draft",
            },
          },
          notes: "Initial draft",
          created_by: subject,
          created_at: timestamp,
          updated_at: timestamp,
        },
      ]),
    ]);

    await saveWorkflow(
      {
        name: "Workflow with token subject actor",
        description: "",
        tags: ["draft"],
        nodes: [],
        edges: [],
      },
      { versionMessage: "Initial draft" },
    );

    const createPayload = JSON.parse(
      (mockFetch.mock.calls[0]?.[1]?.body ?? "{}") as string,
    ) as { actor?: string };
    expect(createPayload.actor).toBe("canvas-app");
    window.localStorage.removeItem("orcheo_canvas_auth_tokens");
  });
});
