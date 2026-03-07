import { describe, expect, it } from "vitest";

import {
  applyTraceResponse,
  buildTraceViewerData,
  createEmptyTraceEntry,
  type TraceResponse,
} from "./trace";

const traceResponse: TraceResponse = {
  execution: {
    id: "exec-1",
    status: "completed",
    trace_id: "trace-1",
    token_usage: { input: 1, output: 1 },
  },
  spans: [
    {
      span_id: "span-1",
      name: "node-1",
      attributes: {
        "orcheo.node.id": "node-1",
        "orcheo.workflow.state.before": { count: 1 },
        "orcheo.workflow.state.after": { count: 2, result: "ok" },
        "orcheo.workflow.state.redacted": true,
        "orcheo.workflow.state.truncated": true,
      },
      events: [],
      status: { code: "OK" },
    },
  ],
  page_info: { has_next_page: false, cursor: null },
};

describe("trace helpers", () => {
  it("extracts workflow state metadata from span attributes", () => {
    const entry = applyTraceResponse(
      createEmptyTraceEntry("exec-1"),
      traceResponse,
    );
    const metadata = entry.spanMetadata["span-1"];

    expect(metadata?.workflowStateBefore).toEqual({ count: 1 });
    expect(metadata?.workflowStateAfter).toEqual({ count: 2, result: "ok" });
    expect(metadata?.workflowStateRedacted).toBe(true);
    expect(metadata?.workflowStateTruncated).toBe(true);
  });

  it("attaches workflow state metadata to rendered trace spans", () => {
    const entry = applyTraceResponse(
      createEmptyTraceEntry("exec-1"),
      traceResponse,
    );
    const viewer = buildTraceViewerData(entry);
    const spanMetadata = viewer?.spans[0]?.metadata as
      | {
          workflowStateBefore?: unknown;
          workflowStateAfter?: unknown;
        }
      | undefined;

    expect(spanMetadata?.workflowStateBefore).toEqual({ count: 1 });
    expect(spanMetadata?.workflowStateAfter).toEqual({
      count: 2,
      result: "ok",
    });
  });
});
