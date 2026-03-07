import { describe, expect, it, vi } from "vitest";

import {
  WORKFLOW_STORAGE_EVENT,
  createWorkflowFromTemplate,
} from "./workflow-storage";
import {
  getFetchMock,
  jsonResponse,
  queueResponses,
  setupFetchMock,
} from "./workflow-storage.test-helpers";

setupFetchMock();

describe("workflow-storage API integration - template creation", () => {
  it("creates a workflow and ingests a Python version from template", async () => {
    const mockFetch = getFetchMock();
    const timestamp = new Date().toISOString();

    queueResponses([
      jsonResponse({
        id: "workflow-template-1",
        name: "Simple Agent Copy",
        slug: "workflow-template-1",
        description: "A single-node agent workflow seeded from `agent.py`.",
        tags: ["python", "agent"],
        is_archived: false,
        created_at: timestamp,
        updated_at: timestamp,
      }),
      jsonResponse({
        id: "workflow-template-1-version-1",
        workflow_id: "workflow-template-1",
        version: 1,
        graph: {
          format: "langgraph-script",
          source:
            "from langgraph.graph import StateGraph\nfrom orcheo.graph.state import State\n",
          entrypoint: null,
          index: { cron: [] },
        },
        metadata: {
          source: "canvas-template",
          template_id: "template-python-agent",
        },
        notes: "Template ingest",
        created_by: "canvas-app",
        created_at: timestamp,
        updated_at: timestamp,
      }),
      jsonResponse({
        id: "workflow-template-1",
        name: "Simple Agent Copy",
        slug: "workflow-template-1",
        description: "A single-node agent workflow seeded from `agent.py`.",
        tags: ["python", "agent"],
        is_archived: false,
        created_at: timestamp,
        updated_at: timestamp,
      }),
      jsonResponse([
        {
          id: "workflow-template-1-version-1",
          workflow_id: "workflow-template-1",
          version: 1,
          graph: {
            format: "langgraph-script",
            source:
              "from langgraph.graph import StateGraph\nfrom orcheo.graph.state import State\n",
            entrypoint: null,
            index: { cron: [] },
          },
          metadata: {
            source: "canvas-template",
            template_id: "template-python-agent",
          },
          notes: "Template ingest",
          created_by: "canvas-app",
          created_at: timestamp,
          updated_at: timestamp,
        },
      ]),
    ]);

    const listener = vi.fn();
    window.addEventListener(WORKFLOW_STORAGE_EVENT, listener);

    const created = await createWorkflowFromTemplate("template-python-agent");

    expect(created?.id).toBe("workflow-template-1");
    expect(created?.versions).toHaveLength(1);
    expect(listener).toHaveBeenCalledTimes(1);
    window.removeEventListener(WORKFLOW_STORAGE_EVENT, listener);

    expect(mockFetch).toHaveBeenCalledTimes(4);
    expect(String(mockFetch.mock.calls[1]?.[0])).toContain(
      "/api/workflows/workflow-template-1/versions/ingest",
    );

    const ingestBody = JSON.parse(
      String(mockFetch.mock.calls[1]?.[1]?.body ?? "{}"),
    ) as { script?: string; metadata?: { source?: string } };
    expect(ingestBody.script).toContain(
      "from orcheo.nodes.ai import AgentNode",
    );
    expect(ingestBody.metadata?.source).toBe("canvas-template");
  });
});
