import { describe, expect, it } from "vitest";

import { buildWorkflowWebSocketUrl } from "./config";

describe("buildWorkflowWebSocketUrl", () => {
  it("appends an access token query parameter when provided", () => {
    expect(
      buildWorkflowWebSocketUrl("wf-1", "http://localhost:8000", "token-123"),
    ).toBe("ws://localhost:8000/ws/workflow/wf-1?access_token=token-123");
  });
});
