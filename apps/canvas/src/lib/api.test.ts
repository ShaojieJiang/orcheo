import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { executeNode, getSystemInfo } from "./api";

describe("executeNode", () => {
  beforeEach(() => {
    global.fetch = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should successfully execute a node", async () => {
    const mockResponse = {
      status: "success",
      result: { foo: "bar", count: 42 },
      error: null,
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    const result = await executeNode({
      node_config: {
        type: "SetVariableNode",
        name: "test_node",
        variables: { foo: "bar", count: 42 },
      },
      inputs: {},
    });

    expect(result).toEqual(mockResponse);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/nodes/execute"),
      expect.objectContaining({
        method: "POST",
        body: expect.stringContaining("SetVariableNode"),
      }),
    );
    const [, options] = (global.fetch as ReturnType<typeof vi.fn>).mock
      .calls[0];
    const headers = options?.headers as Headers;
    expect(headers).toBeInstanceOf(Headers);
    expect(headers.get("Content-Type")).toBe("application/json");
  });

  it("should handle error responses", async () => {
    const mockErrorResponse = {
      status: "error",
      result: null,
      error: "Node execution failed",
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockErrorResponse,
    });

    const result = await executeNode({
      node_config: {
        type: "InvalidNode",
        name: "test",
      },
      inputs: {},
    });

    expect(result.status).toBe("error");
    expect(result.error).toBe("Node execution failed");
  });

  it("should throw error on HTTP failure", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: async () => ({ detail: "Bad Request" }),
    });

    await expect(
      executeNode({
        node_config: { type: "Test", name: "test" },
        inputs: {},
      }),
    ).rejects.toThrow("Bad Request");
  });

  it("should include workflow_id when provided", async () => {
    const mockResponse = {
      status: "success",
      result: {},
      error: null,
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    const workflowId = "550e8400-e29b-41d4-a716-446655440000";
    await executeNode({
      node_config: { type: "Test", name: "test" },
      inputs: {},
      workflow_id: workflowId,
    });

    const callArgs = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    const body = JSON.parse(callArgs[1].body);
    expect(body.workflow_id).toBe(workflowId);
  });

  it("should use custom base URL when provided", async () => {
    const mockResponse = {
      status: "success",
      result: {},
      error: null,
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    await executeNode(
      {
        node_config: { type: "Test", name: "test" },
        inputs: {},
      },
      "http://custom-backend:9000",
    );

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("http://custom-backend:9000"),
      expect.any(Object),
    );
  });

  it("should fetch system info", async () => {
    const mockResponse = {
      backend: {
        package: "orcheo-backend",
        current_version: "0.1.0",
        latest_version: "0.2.0",
        minimum_recommended_version: null,
        release_notes_url: null,
        update_available: true,
      },
      cli: {
        package: "orcheo-sdk",
        current_version: "0.1.0",
        latest_version: "0.2.0",
        minimum_recommended_version: null,
        release_notes_url: null,
        update_available: true,
      },
      canvas: {
        package: "orcheo-canvas",
        current_version: "0.1.0",
        latest_version: "0.2.0",
        minimum_recommended_version: null,
        release_notes_url: null,
        update_available: true,
      },
      checked_at: "2026-02-21T12:00:00Z",
    };
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    const result = await getSystemInfo();
    expect(result.backend.package).toBe("orcheo-backend");
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/system/info"),
      expect.objectContaining({ method: "GET" }),
    );
  });
});
