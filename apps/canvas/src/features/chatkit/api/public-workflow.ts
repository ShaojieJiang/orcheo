import { buildBackendHttpUrl } from "@/lib/config";

export interface PublicWorkflowMetadata {
  id: string;
  name: string;
  is_public: boolean;
  require_login: boolean;
}

export class PublicWorkflowError extends Error {
  status: number;
  code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "PublicWorkflowError";
    this.status = status;
    this.code = code;
  }
}

const parseErrorPayload = async (
  response: Response,
): Promise<{
  message: string;
  code?: string;
}> => {
  try {
    const contentType = response.headers.get("Content-Type") ?? "";
    if (!contentType.includes("application/json")) {
      return { message: response.statusText || "Request failed" };
    }
    const payload = (await response.json()) as {
      detail?: string | { message?: string; code?: string };
      message?: string;
      code?: string;
    };
    if (!payload) {
      return { message: response.statusText || "Request failed" };
    }
    if (typeof payload.detail === "string") {
      return { message: payload.detail };
    }
    if (payload.detail && typeof payload.detail === "object") {
      return {
        message:
          payload.detail.message ?? (response.statusText || "Request failed"),
        code: payload.detail.code,
      };
    }
    return {
      message: payload.message ?? (response.statusText || "Request failed"),
      code: payload.code,
    };
  } catch {
    return { message: response.statusText || "Request failed" };
  }
};

export const fetchPublicWorkflow = async (
  workflowId: string,
  options: { signal?: AbortSignal } = {},
): Promise<PublicWorkflowMetadata> => {
  const resolvedId = workflowId.trim();
  if (!resolvedId) {
    throw new PublicWorkflowError("workflowId is required", 400);
  }

  const response = await fetch(
    buildBackendHttpUrl(`/api/chatkit/workflows/${resolvedId}`),
    {
      method: "GET",
      credentials: "include",
      signal: options.signal,
    },
  );

  if (!response.ok) {
    const detail = await parseErrorPayload(response);
    throw new PublicWorkflowError(detail.message, response.status, detail.code);
  }

  const payload = (await response.json()) as PublicWorkflowMetadata;
  return payload;
};
