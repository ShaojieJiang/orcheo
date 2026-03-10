import { describe, expect, it } from "vitest";
import {
  extractCronConfigFromVersionGraph,
  fetchWorkflowCredentialReadiness,
  resolveWorkflowShareUrl,
  selectLatestWorkflowVersion,
  triggerWorkflowRun,
} from "./workflow-storage-api";
import {
  getFetchMock,
  jsonResponse,
  queueResponses,
  setupFetchMock,
} from "./workflow-storage.test-helpers";

setupFetchMock();

describe("workflow-storage-api helpers", () => {
  it("uses explicit share_url for published workflows", () => {
    const shareUrl = resolveWorkflowShareUrl({
      id: "wf-1",
      handle: "my-flow",
      is_public: true,
      share_url: "https://canvas.example/chat/my-flow",
    });

    expect(shareUrl).toBe("https://canvas.example/chat/my-flow");
  });

  it("extracts cron config from graph index", () => {
    const config = extractCronConfigFromVersionGraph({
      index: {
        cron: [
          {
            expression: "0 9 * * MON-FRI",
            timezone: "UTC",
            allow_overlapping: false,
          },
        ],
      },
    });

    expect(config).toEqual({
      expression: "0 9 * * MON-FRI",
      timezone: "UTC",
      allow_overlapping: false,
      start_at: undefined,
      end_at: undefined,
    });
  });

  it("extracts cron config from graph nodes", () => {
    const config = extractCronConfigFromVersionGraph({
      nodes: [
        {
          type: "CronTriggerNode",
          expression: "*/15 * * * *",
          timezone: "Europe/Amsterdam",
          allow_overlapping: true,
        },
      ],
    });

    expect(config).toEqual({
      expression: "*/15 * * * *",
      timezone: "Europe/Amsterdam",
      allow_overlapping: true,
      start_at: undefined,
      end_at: undefined,
    });
  });

  it("extracts cron config from script graph summary nodes", () => {
    const config = extractCronConfigFromVersionGraph({
      format: "langgraph-script",
      summary: {
        nodes: [
          {
            type: "CronTriggerNode",
            expression: "0 12 * * *",
            timezone: "UTC",
            allow_overlapping: false,
          },
        ],
      },
    });

    expect(config).toEqual({
      expression: "0 12 * * *",
      timezone: "UTC",
      allow_overlapping: false,
      start_at: undefined,
      end_at: undefined,
    });
  });

  it("throws when multiple cron triggers exist", () => {
    expect(() =>
      extractCronConfigFromVersionGraph({
        nodes: [
          { type: "CronTriggerNode", expression: "0 * * * *" },
          { type: "CronTriggerNode", expression: "30 * * * *" },
        ],
      }),
    ).toThrow("Workflow contains multiple cron triggers.");
  });

  it("triggers a workflow run using the latest version", async () => {
    const mockFetch = getFetchMock();
    queueResponses([
      jsonResponse([
        {
          id: "v1",
          workflow_id: "wf-1",
          version: 1,
          graph: { format: "langgraph-script", source: "print('old')" },
          metadata: {},
          runnable_config: null,
          notes: null,
          created_by: "canvas",
          created_at: "2026-03-10T09:00:00Z",
          updated_at: "2026-03-10T09:00:00Z",
        },
        {
          id: "v2",
          workflow_id: "wf-1",
          version: 2,
          graph: { format: "langgraph-script", source: "print('new')" },
          metadata: {},
          runnable_config: null,
          notes: null,
          created_by: "canvas",
          created_at: "2026-03-10T10:00:00Z",
          updated_at: "2026-03-10T10:00:00Z",
        },
      ]),
      jsonResponse(
        {
          id: "run-1",
          workflow_id: "wf-1",
          workflow_version_id: "v2",
          status: "pending",
          triggered_by: "canvas",
          input_payload: {},
        },
        201,
      ),
    ]);

    const payload = await triggerWorkflowRun("wf-1");

    expect(payload.id).toBe("run-1");
    expect(mockFetch).toHaveBeenCalledTimes(2);
    expect(String(mockFetch.mock.calls[1]?.[0])).toContain(
      "/api/workflows/wf-1/runs",
    );

    const requestBody = JSON.parse(
      String(mockFetch.mock.calls[1]?.[1]?.body ?? "{}"),
    ) as { workflow_version_id?: string; triggered_by?: string };
    expect(requestBody.workflow_version_id).toBe("v2");
    expect(requestBody.triggered_by).toBe("canvas");
  });

  it("selects the highest workflow version even when the API response is unsorted", () => {
    const latest = selectLatestWorkflowVersion([
      {
        id: "v2",
        workflow_id: "wf-1",
        version: 2,
        graph: { format: "langgraph-script", source: "print('mid')" },
        metadata: {},
        runnable_config: null,
        notes: null,
        created_by: "canvas",
        created_at: "2026-03-10T10:00:00Z",
        updated_at: "2026-03-10T10:00:00Z",
      },
      {
        id: "v1",
        workflow_id: "wf-1",
        version: 1,
        graph: { format: "langgraph-script", source: "print('old')" },
        metadata: {},
        runnable_config: null,
        notes: null,
        created_by: "canvas",
        created_at: "2026-03-10T09:00:00Z",
        updated_at: "2026-03-10T09:00:00Z",
      },
      {
        id: "v3",
        workflow_id: "wf-1",
        version: 3,
        graph: { format: "langgraph-script", source: "print('new')" },
        metadata: {},
        runnable_config: null,
        notes: null,
        created_by: "canvas",
        created_at: "2026-03-10T11:00:00Z",
        updated_at: "2026-03-10T11:00:00Z",
      },
    ]);

    expect(latest?.id).toBe("v3");
  });

  it("fetches workflow credential readiness", async () => {
    const mockFetch = getFetchMock();
    queueResponses([
      jsonResponse({
        workflow_id: "wf-1",
        status: "missing",
        referenced_credentials: [
          {
            name: "openai_api_key",
            placeholders: ["[[openai_api_key]]"],
            available: true,
            credential_id: "cred-1",
            provider: "openai",
          },
        ],
        available_credentials: ["openai_api_key"],
        missing_credentials: ["telegram_chat_id"],
      }),
    ]);

    const payload = await fetchWorkflowCredentialReadiness("wf-1");

    expect(payload?.status).toBe("missing");
    expect(payload?.missing_credentials).toEqual(["telegram_chat_id"]);
    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(String(mockFetch.mock.calls[0]?.[0])).toContain(
      "/api/workflows/wf-1/credentials/readiness",
    );
  });
});
