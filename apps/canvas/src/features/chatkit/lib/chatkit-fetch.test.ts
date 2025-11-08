import { afterAll, beforeEach, describe, expect, it, vi } from "vitest";

import { createChatKitFetch } from "./chatkit-fetch";

declare global {
  var fetch: typeof globalThis.fetch;
}

describe("createChatKitFetch", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
    global.fetch = vi
      .fn()
      .mockResolvedValue(
        new Response(null, { status: 200 }),
      ) as unknown as typeof global.fetch;
  });

  afterAll(() => {
    global.fetch = originalFetch;
  });

  it("augments JSON payloads with workflow metadata", async () => {
    const onAuthError = vi.fn();
    const onRateLimitChange = vi.fn();
    const fetchWrapper = createChatKitFetch({
      workflowId: "wf-123",
      publishToken: "token-xyz",
      onAuthError,
      onRateLimitChange,
    });

    await fetchWrapper("/api/chatkit", {
      method: "POST",
      body: JSON.stringify({ metadata: { foo: "bar" } }),
    });

    expect(global.fetch).toHaveBeenCalledTimes(1);
    const fetchMock = global.fetch as unknown as vi.Mock;
    const [, init] = fetchMock.mock.calls[0] as [RequestInfo, RequestInit];
    expect(init?.credentials).toBe("include");
    expect(init?.headers).toBeInstanceOf(Headers);
    const payload = init?.body ? JSON.parse(init.body as string) : null;
    expect(payload).toMatchObject({
      workflow_id: "wf-123",
      publish_token: "token-xyz",
      metadata: expect.objectContaining({ workflow_id: "wf-123", foo: "bar" }),
    });
    expect(onAuthError).not.toHaveBeenCalled();
    expect(onRateLimitChange).toHaveBeenCalledWith(null);
  });

  it("notifies rate limit listener on 429 responses", async () => {
    const onRateLimitChange = vi.fn();
    const rateLimitedResponse = new Response(null, { status: 429 });
    const fetchMock = global.fetch as unknown as vi.Mock;
    fetchMock.mockResolvedValue(rateLimitedResponse);

    const fetchWrapper = createChatKitFetch({
      workflowId: "wf-123",
      publishToken: "token-xyz",
      onRateLimitChange,
    });

    await fetchWrapper("/api/chatkit", { method: "POST", body: "{}" });

    expect(onRateLimitChange).toHaveBeenCalledWith(
      "You are sending messages too quickly. Please wait a few moments and try again.",
    );
  });

  it("parses authentication errors and forwards them", async () => {
    const onAuthError = vi.fn();
    const errorResponse = new Response(
      JSON.stringify({
        detail: {
          code: "chatkit.auth.oauth_required",
          message: "OAuth required",
        },
      }),
      { status: 401, headers: { "content-type": "application/json" } },
    );
    const fetchMock = global.fetch as unknown as vi.Mock;
    fetchMock.mockResolvedValue(errorResponse);

    const fetchWrapper = createChatKitFetch({
      workflowId: "wf-123",
      publishToken: "token-xyz",
      onAuthError,
    });

    await fetchWrapper("/api/chatkit", { method: "POST", body: "{}" });

    expect(onAuthError).toHaveBeenCalledWith({
      code: "chatkit.auth.oauth_required",
      message: "OAuth required",
      status: 401,
    });
  });
});
