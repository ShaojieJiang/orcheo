import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { executeNode } from "./api";

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
        headers: {
          "Content-Type": "application/json",
        },
        body: expect.stringContaining("SetVariableNode"),
      }),
    );
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
});
