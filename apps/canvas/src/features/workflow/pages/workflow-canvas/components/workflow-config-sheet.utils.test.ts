import { describe, expect, it } from "vitest";

import {
  toFormData,
  toWorkflowConfig,
} from "@features/workflow/pages/workflow-canvas/components/workflow-config-sheet.utils";

describe("workflow-config-sheet utils", () => {
  it("preserves upload-time runnable config fields", () => {
    const formData = {
      configurable: { tenant: "acme", region: "us-east-1" },
      run_name: "  nightly-run  ",
      tags: ["prod", " prod ", "nightly"],
      metadata: { owner: "search-team" },
      callbacks: [{ type: "log" }],
      recursion_limit: 7,
      max_concurrency: 3,
      prompts: {
        summary_prompt: {
          template: "Summarize {topic}",
          input_variables: ["topic"],
          partial_variables: { tone: "brief" },
        },
      },
    } satisfies Record<string, unknown>;

    expect(toWorkflowConfig(formData)).toEqual({
      configurable: { tenant: "acme", region: "us-east-1" },
      run_name: "nightly-run",
      tags: ["prod", "nightly"],
      metadata: { owner: "search-team" },
      callbacks: [{ type: "log" }],
      recursion_limit: 7,
      max_concurrency: 3,
      prompts: {
        summary_prompt: {
          template: "Summarize {topic}",
          input_variables: ["topic"],
          partial_variables: { tone: "brief" },
        },
      },
    });
  });

  it("keeps all runnable config fields when hydrating form data", () => {
    const config = {
      configurable: { organization: "acme" },
      run_name: "upload-run",
      tags: ["upload"],
      metadata: { source: "cli" },
      callbacks: ["callback-a"],
      recursion_limit: 5,
      max_concurrency: 2,
      prompts: {
        review_prompt: {
          template: "Review {text}",
          input_variables: ["text"],
          optional_variables: ["style"],
        },
      },
    };

    expect(toFormData(config)).toEqual({
      configurable: { organization: "acme" },
      run_name: "upload-run",
      tags: ["upload"],
      metadata: { source: "cli" },
      callbacks: ["callback-a"],
      recursion_limit: 5,
      max_concurrency: 2,
      prompts: {
        review_prompt: {
          template: "Review {text}",
          input_variables: ["text"],
          optional_variables: ["style"],
        },
      },
    });
  });
});
