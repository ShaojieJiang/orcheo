import { toApiUrl } from "@/config/orcheo-backend";

interface FetchOptions {
  signal?: AbortSignal;
}

const parseJson = async <T>(response: Response): Promise<T> => {
  if (!response.ok) {
    const text = await response.text();
    const error = new Error(
      `Request failed with status ${response.status}: ${text || response.statusText}`,
    );
    throw error;
  }
  return (await response.json()) as T;
};

export interface RunHistoryStepResponse {
  index: number;
  at: string;
  payload: Record<string, unknown>;
}

export interface RunHistoryResponse {
  execution_id: string;
  workflow_id: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  error: string | null;
  inputs: Record<string, unknown>;
  steps: RunHistoryStepResponse[];
}

export const fetchExecutionHistory = async (
  executionId: string,
  options?: FetchOptions,
): Promise<RunHistoryResponse> => {
  const url = toApiUrl(
    `/executions/${encodeURIComponent(executionId)}/history`,
  );
  const response = await fetch(url, {
    method: "GET",
    signal: options?.signal,
    headers: {
      Accept: "application/json",
    },
  });
  return parseJson<RunHistoryResponse>(response);
};

export const replayExecution = async (
  executionId: string,
  fromStep = 0,
  options?: FetchOptions,
): Promise<RunHistoryResponse> => {
  const url = toApiUrl(`/executions/${encodeURIComponent(executionId)}/replay`);
  const response = await fetch(url, {
    method: "POST",
    signal: options?.signal,
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ from_step: fromStep }),
  });
  return parseJson<RunHistoryResponse>(response);
};
