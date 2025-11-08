import { describe, expect, it, beforeEach } from "vitest";

import {
  clearPublishToken,
  getPublishToken,
  getPublishTokenCount,
  resetPublishTokenStore,
  storePublishToken,
} from "./publish-token-store";

describe("publish-token-store", () => {
  beforeEach(() => {
    resetPublishTokenStore();
  });

  it("stores and retrieves publish tokens", () => {
    storePublishToken("workflow-123", "token-abc");

    expect(getPublishToken("workflow-123")).toBe("token-abc");
    expect(getPublishTokenCount()).toBe(1);
  });

  it("ignores empty workflow identifiers and tokens", () => {
    storePublishToken("", "token");
    storePublishToken("workflow", "");

    expect(getPublishTokenCount()).toBe(0);
  });

  it("clears individual tokens", () => {
    storePublishToken("workflow-1", "token-a");
    storePublishToken("workflow-2", "token-b");

    clearPublishToken("workflow-1");

    expect(getPublishToken("workflow-1")).toBeNull();
    expect(getPublishToken("workflow-2")).toBe("token-b");
    expect(getPublishTokenCount()).toBe(1);
  });
});
