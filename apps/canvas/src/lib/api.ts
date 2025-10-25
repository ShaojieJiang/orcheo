import { buildBackendHttpUrl } from "./config";

export interface NodeExecutionRequest {
  node_config: Record<string, unknown>;
  inputs?: Record<string, unknown>;
  workflow_id?: string;
}

export interface NodeExecutionResponse {
  status: "success" | "error";
  result?: unknown;
  error?: string;
}

/**
 * Execute a single node in isolation for testing/preview purposes.
 *
 * @param request - Node execution request containing node_config, inputs, and optional workflow_id
 * @param baseUrl - Optional backend base URL (defaults to configured backend URL)
 * @returns Promise resolving to the node execution response
 * @throws Error if the request fails
 */
export async function executeNode(
  request: NodeExecutionRequest,
  baseUrl?: string,
): Promise<NodeExecutionResponse> {
  const url = buildBackendHttpUrl("/api/nodes/execute", baseUrl);

  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({
      detail: "Failed to execute node",
    }));
    throw new Error(errorData.detail || `HTTP ${response.status}`);
  }

  return response.json();
}
