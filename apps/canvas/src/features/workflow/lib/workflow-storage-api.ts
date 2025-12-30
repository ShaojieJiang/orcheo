import { authFetch } from "@/lib/auth-fetch";
import { buildBackendHttpUrl } from "@/lib/config";
import type {
  ApiWorkflow,
  ApiWorkflowVersion,
  RequestOptions,
} from "./workflow-storage.types";

export const API_BASE = "/api/workflows";

const JSON_HEADERS = {
  Accept: "application/json",
  "Content-Type": "application/json",
};

export class ApiRequestError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
  }
}

const readText = async (response: Response): Promise<string> => {
  try {
    return await response.text();
  } catch {
    return "";
  }
};

export const request = async <T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> => {
  const expectJson = options.expectJson ?? true;
  const url = buildBackendHttpUrl(path);

  const response = await authFetch(url, {
    ...options,
    headers: options.body ? JSON_HEADERS : options.headers,
  });

  if (!response.ok) {
    const detail = (await readText(response)) || response.statusText;
    throw new ApiRequestError(detail, response.status);
  }

  if (!expectJson || response.status === 204) {
    return undefined as T;
  }

  const payload = await readText(response);
  if (!payload) {
    return undefined as T;
  }
  return JSON.parse(payload) as T;
};

export const fetchWorkflow = async (
  workflowId: string,
): Promise<ApiWorkflow | undefined> => {
  try {
    return await request<ApiWorkflow>(`${API_BASE}/${workflowId}`);
  } catch (error) {
    if (
      error instanceof ApiRequestError &&
      (error.status === 404 || error.status === 410)
    ) {
      return undefined;
    }
    throw error;
  }
};

export const fetchWorkflowVersions = async (
  workflowId: string,
): Promise<ApiWorkflowVersion[]> => {
  try {
    return await request<ApiWorkflowVersion[]>(
      `${API_BASE}/${workflowId}/versions`,
    );
  } catch (error) {
    if (
      error instanceof ApiRequestError &&
      (error.status === 404 || error.status === 410)
    ) {
      return [];
    }
    throw error;
  }
};

export const upsertWorkflow = async (
  input: Pick<ApiWorkflow, "id" | "name" | "description" | "tags">,
  actor: string,
): Promise<string> => {
  if (!input.id) {
    const created = await request<ApiWorkflow>(API_BASE, {
      method: "POST",
      body: JSON.stringify({
        name: input.name,
        description: input.description,
        tags: input.tags ?? [],
        actor,
      }),
    });
    return created.id;
  }

  await request<ApiWorkflow>(`${API_BASE}/${input.id}`, {
    method: "PUT",
    body: JSON.stringify({
      name: input.name,
      description: input.description,
      tags: input.tags ?? [],
      actor,
    }),
  });
  return input.id;
};
