import { describe, expect, it } from "vitest";
import {
  extractCronConfigFromVersionGraph,
  resolveWorkflowShareUrl,
} from "./workflow-storage-api";

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
});
