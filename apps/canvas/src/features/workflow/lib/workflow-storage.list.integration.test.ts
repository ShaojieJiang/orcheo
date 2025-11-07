import { describe, expect, it } from "vitest";

import { listWorkflows } from "./workflow-storage";
import {
  getFetchMock,
  jsonResponse,
  queueResponses,
  setupFetchMock,
} from "./workflow-storage.test-helpers";

setupFetchMock();

describe("workflow-storage API integration - list workflows", () => {
  it("lists workflows by merging backing metadata", async () => {
    const mockFetch = getFetchMock();
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
});
