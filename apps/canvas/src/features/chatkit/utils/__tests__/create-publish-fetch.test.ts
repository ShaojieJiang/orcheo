import { describe, expect, it, vi } from "vitest";

import { createPublishFetch } from "../create-publish-fetch";

describe("createPublishFetch", () => {
  it("injects workflow_id and publish_token into JSON payloads", async () => {
    const baseFetch = vi
      .fn()
      .mockResolvedValue(new Response("{}", { status: 200 }));
    const publishFetch = createPublishFetch({
      workflowId: "wf-123",
      publishToken: "secret-token",
      baseFetch,
    });

    await publishFetch("https://example.com/api/chatkit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: [{ role: "user", content: "hi" }] }),
    });

    expect(baseFetch).toHaveBeenCalledTimes(1);
    const request = baseFetch.mock.calls[0][0] as Request;
    const body = await request.clone().text();
    expect(JSON.parse(body)).toMatchObject({
      workflow_id: "wf-123",
      publish_token: "secret-token",
    });
    expect(request.credentials).toBe("include");
  });

  it("merges metadata from options with existing payload metadata", async () => {
    const baseFetch = vi
      .fn()
      .mockResolvedValue(new Response("{}", { status: 200 }));
    const publishFetch = createPublishFetch({
      workflowId: "wf-123",
      publishToken: "secret-token",
      metadata: { workflow_name: "Sample Workflow" },
      baseFetch,
    });

    await publishFetch("https://example.com/api/chatkit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ metadata: { source: "widget" } }),
    });

    const request = baseFetch.mock.calls[0][0] as Request;
    const body = await request.clone().text();
    expect(JSON.parse(body)).toMatchObject({
      metadata: {
        source: "widget",
        workflow_name: "Sample Workflow",
        workflow_id: "wf-123",
      },
    });
  });

  it("calls callbacks when authentication errors occur", async () => {
    const baseFetch = vi
      .fn()
      .mockResolvedValue(
        new Response("{}", { status: 401, statusText: "Unauthorized" }),
      );
    const onAuthError = vi.fn();
    const publishFetch = createPublishFetch({
      workflowId: "wf-123",
      publishToken: "secret-token",
      baseFetch,
      onAuthError,
    });

    await publishFetch("https://example.com/api/chatkit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });

    expect(onAuthError).toHaveBeenCalledWith(401);
  });

  it("calls rate limit handler when 429 responses are returned", async () => {
    const baseFetch = vi
      .fn()
      .mockResolvedValue(
        new Response("{}", { status: 429, statusText: "Too Many Requests" }),
      );
    const onRateLimit = vi.fn();
    const publishFetch = createPublishFetch({
      workflowId: "wf-123",
      publishToken: "secret-token",
      baseFetch,
      onRateLimit,
    });

    await publishFetch("https://example.com/api/chatkit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });

    expect(onRateLimit).toHaveBeenCalledWith(429);
  });
});
