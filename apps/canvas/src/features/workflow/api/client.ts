import {
  CanvasGraphDefinition,
  WorkflowSummary,
  WorkflowVersionDiffResponse,
  WorkflowVersionRecord,
} from "./types";

const DEFAULT_BASE_URL = "/api";

const API_BASE_URL =
  (import.meta.env?.VITE_API_BASE_URL as string | undefined) ||
  DEFAULT_BASE_URL;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });

  if (!response.ok) {
    const message = await response
      .text()
      .catch(() => `Request failed with status ${response.status}`);
    throw new Error(message || `Request failed with status ${response.status}`);
  }

  return (await response.json()) as T;
}

export async function listWorkflows(): Promise<WorkflowSummary[]> {
  return request<WorkflowSummary[]>("/workflows");
}

export async function getWorkflow(
  workflowId: string,
): Promise<WorkflowSummary> {
  return request<WorkflowSummary>(`/workflows/${workflowId}`);
}

export async function createWorkflow(payload: {
  name: string;
  slug?: string | null;
  description?: string | null;
  tags?: string[];
  actor?: string;
}): Promise<WorkflowSummary> {
  return request<WorkflowSummary>("/workflows", {
    method: "POST",
    body: JSON.stringify({
      ...payload,
      actor: payload.actor ?? "canvas-ui",
    }),
  });
}

export async function updateWorkflow(
  workflowId: string,
  payload: {
    name?: string | null;
    description?: string | null;
    tags?: string[] | null;
    is_archived?: boolean | null;
    actor?: string;
  },
): Promise<WorkflowSummary> {
  return request<WorkflowSummary>(`/workflows/${workflowId}`, {
    method: "PUT",
    body: JSON.stringify({
      ...payload,
      actor: payload.actor ?? "canvas-ui",
    }),
  });
}

export async function createWorkflowVersion(
  workflowId: string,
  payload: {
    graph: CanvasGraphDefinition;
    metadata?: Record<string, unknown>;
    notes?: string | null;
    created_by?: string;
  },
): Promise<WorkflowVersionRecord> {
  return request<WorkflowVersionRecord>(`/workflows/${workflowId}/versions`, {
    method: "POST",
    body: JSON.stringify({
      graph: payload.graph,
      metadata: payload.metadata ?? {},
      notes: payload.notes ?? null,
      created_by: payload.created_by ?? "canvas-ui",
    }),
  });
}

export async function listWorkflowVersions(
  workflowId: string,
): Promise<WorkflowVersionRecord[]> {
  return request<WorkflowVersionRecord[]>(`/workflows/${workflowId}/versions`);
}

export async function getWorkflowVersion(
  workflowId: string,
  versionNumber: number,
): Promise<WorkflowVersionRecord> {
  return request<WorkflowVersionRecord>(
    `/workflows/${workflowId}/versions/${versionNumber}`,
  );
}

export async function diffWorkflowVersions(
  workflowId: string,
  baseVersion: number,
  targetVersion: number,
): Promise<WorkflowVersionDiffResponse> {
  return request<WorkflowVersionDiffResponse>(
    `/workflows/${workflowId}/versions/${baseVersion}/diff/${targetVersion}`,
  );
}
