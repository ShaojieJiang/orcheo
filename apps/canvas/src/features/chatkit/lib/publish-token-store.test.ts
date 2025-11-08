import { beforeEach, describe, expect, it } from "vitest";

import {
  clearPublishToken,
  readPublishToken,
  rememberPublishToken,
  resetPublishTokens,
} from "./publish-token-store";

describe("publish-token-store", () => {
  beforeEach(() => {
    resetPublishTokens();
  });

  it("remembers tokens per workflow", () => {
    rememberPublishToken("workflow-1", "token-a");
    rememberPublishToken("workflow-2", "token-b");

    expect(readPublishToken("workflow-1")).toBe("token-a");
    expect(readPublishToken("workflow-2")).toBe("token-b");
  });

  it("returns null for unknown workflow ids", () => {
    expect(readPublishToken("missing")).toBeNull();
  });

  it("clears stored tokens", () => {
    rememberPublishToken("workflow-1", "token-a");
    clearPublishToken("workflow-1");

    expect(readPublishToken("workflow-1")).toBeNull();
  });
});
