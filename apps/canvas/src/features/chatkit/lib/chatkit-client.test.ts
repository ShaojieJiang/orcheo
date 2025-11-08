import { afterEach, describe, expect, it, vi } from "vitest";
import { buildPublishFetch } from "./chatkit-client";

const originalFetch = window.fetch;

afterEach(() => {
  window.fetch = originalFetch;
  vi.restoreAllMocks();
});

const createResponse = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

describe("buildPublishFetch", () => {
  it("injects publish token and workflow id into JSON bodies", async () => {
    const fetchMock = vi.fn(async () => createResponse(200, { ok: true }));
    window.fetch = fetchMock as unknown as typeof window.fetch;

    const handler = buildPublishFetch({
      workflowId: "wf-123",
      publishToken: "secret-token",
      backendBaseUrl: "http://localhost:8000",
    });

    await handler("http://localhost:8000/api/chatkit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ foo: "bar" }),
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, options] = fetchMock.mock.calls[0]!;
    expect(options?.credentials).toBe("include");

    const payload = JSON.parse((options?.body as string) ?? "{}");
    expect(payload.workflow_id).toBe("wf-123");
    expect(payload.publish_token).toBe("secret-token");
    expect(payload.foo).toBe("bar");
  });

  it("emits structured errors when the backend rejects a request", async () => {
    const fetchMock = vi.fn(async () =>
      createResponse(401, {
        code: "chatkit.auth.invalid_publish_token",
        message: "invalid token",
      }),
    );
    window.fetch = fetchMock as unknown as typeof window.fetch;

    const onHttpError = vi.fn();
    const handler = buildPublishFetch({
      workflowId: "wf-123",
      publishToken: "bad-token",
      onHttpError,
    });

    await handler("http://localhost:8000/api/chatkit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });

    expect(onHttpError).toHaveBeenCalledWith({
      status: 401,
      message: "invalid token",
      code: "chatkit.auth.invalid_publish_token",
    });
  });
});
