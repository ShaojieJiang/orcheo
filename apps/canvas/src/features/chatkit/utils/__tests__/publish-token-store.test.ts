import { beforeEach, describe, expect, it } from "vitest";

import {
  clearPublishToken,
  ensurePublishToken,
  getPublishToken,
  setPublishToken,
} from "../publish-token-store";

const resetUrl = (path: string) => {
  const origin = window.location.origin;
  const normalised = path.startsWith("/") ? path : `/${path}`;
  window.history.replaceState({}, "", `${origin}${normalised}`);
};

describe("publish-token-store", () => {
  beforeEach(() => {
    clearPublishToken();
    resetUrl("/chat/workflow-123");
    delete (window as typeof window & {
      __ORCHEO_CHATKIT_PUBLISH_TOKEN__?: string;
    }).__ORCHEO_CHATKIT_PUBLISH_TOKEN__;
  });

  it("reads token from query string and removes it from the URL", () => {
    resetUrl("/chat/workflow-123?token=secret&foo=bar");

    const token = ensurePublishToken();

    expect(token).toBe("secret");
    expect(getPublishToken()).toBe("secret");
    expect(window.location.search).toBe("?foo=bar");
  });

  it("prefers history state token over other sources", () => {
    resetUrl("/chat/workflow-123");
    window.history.replaceState(
      { chatkitPublishToken: "history-token" },
      "",
      "/chat/workflow-123?token=query-token",
    );
    (window as typeof window & {
      __ORCHEO_CHATKIT_PUBLISH_TOKEN__?: string;
    }).__ORCHEO_CHATKIT_PUBLISH_TOKEN__ = "global-token";

    const token = ensurePublishToken();

    expect(token).toBe("history-token");
  });

  it("falls back to global token when history is empty", () => {
    (window as typeof window & {
      __ORCHEO_CHATKIT_PUBLISH_TOKEN__?: string;
    }).__ORCHEO_CHATKIT_PUBLISH_TOKEN__ = "global-token";

    const token = ensurePublishToken();

    expect(token).toBe("global-token");
  });

  it("keeps the resolved token in memory until cleared", () => {
    setPublishToken("initial");
    expect(getPublishToken()).toBe("initial");

    setPublishToken(null);
    expect(getPublishToken()).toBeNull();

    resetUrl("/chat/workflow-123?token=another");
    const token = ensurePublishToken();
    expect(token).toBe("another");
    expect(getPublishToken()).toBe("another");

    clearPublishToken();
    expect(getPublishToken()).toBeNull();
  });
});
