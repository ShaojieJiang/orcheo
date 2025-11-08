import type { ChatKitOptions } from "@openai/chatkit";

export interface PublishAuthError {
  code: string;
  message: string;
  status: number;
}

interface CreateChatKitFetchOptions {
  workflowId: string;
  publishToken: string;
  onAuthError?: (error: PublishAuthError) => void;
  onRateLimitChange?: (message: string | null) => void;
}

const ensureMetadataPayload = (
  payload: Record<string, unknown>,
  workflowId: string,
): Record<string, unknown> => {
  const existingMetadata =
    typeof payload.metadata === "object" && payload.metadata !== null
      ? (payload.metadata as Record<string, unknown>)
      : {};

  return {
    ...payload,
    workflow_id: payload.workflow_id ?? workflowId,
    publish_token: payload.publish_token ?? undefined,
    metadata: {
      ...existingMetadata,
      workflow_id: existingMetadata.workflow_id ?? workflowId,
    },
  };
};

const augmentJsonBody = (
  body: string,
  workflowId: string,
  publishToken: string,
): string => {
  try {
    const parsed = JSON.parse(body) as Record<string, unknown>;
    const augmented = ensureMetadataPayload(parsed, workflowId);
    augmented.publish_token = publishToken;
    return JSON.stringify(augmented);
  } catch {
    return body;
  }
};

const extractErrorDetail = async (
  response: Response,
): Promise<PublishAuthError | null> => {
  try {
    const clone = response.clone();
    const contentType = clone.headers.get("content-type") ?? "";
    if (!contentType.includes("application/json")) {
      return null;
    }
    const payload = (await clone.json()) as {
      detail?: unknown;
    };
    if (!payload.detail || typeof payload.detail !== "object") {
      if (typeof payload.detail === "string") {
        return {
          code: "chatkit.auth.unknown",
          message: payload.detail,
          status: response.status,
        };
      }
      return null;
    }
    const detail = payload.detail as Record<string, unknown>;
    const code =
      typeof detail.code === "string" ? detail.code : "chatkit.auth.unknown";
    const message =
      typeof detail.message === "string"
        ? detail.message
        : "Unable to authenticate with the provided publish token.";
    return { code, message, status: response.status };
  } catch {
    return null;
  }
};

export const createChatKitFetch = ({
  workflowId,
  publishToken,
  onAuthError,
  onRateLimitChange,
}: CreateChatKitFetchOptions): ChatKitOptions["api"]["fetch"] => {
  const baseFetch = globalThis.fetch.bind(globalThis);

  return async (input, init = {}) => {
    const nextInit: RequestInit = {
      ...init,
      credentials: "include",
    };

    const headers = new Headers(nextInit.headers ?? undefined);

    if (typeof nextInit.body === "string" && nextInit.body.trim()) {
      nextInit.body = augmentJsonBody(nextInit.body, workflowId, publishToken);
      if (!headers.has("content-type")) {
        headers.set("content-type", "application/json");
      }
    }

    nextInit.headers = headers;

    const response = await baseFetch(input, nextInit);

    if (response.ok) {
      onRateLimitChange?.(null);
      return response;
    }

    if (response.status === 429) {
      onRateLimitChange?.(
        "You are sending messages too quickly. Please wait a few moments and try again.",
      );
    }

    if (response.status === 401 || response.status === 403) {
      const detail = await extractErrorDetail(response);
      if (detail) {
        if (!detail.code) {
          detail.code = "chatkit.auth.unknown";
        }
        onAuthError?.({
          code: detail.code,
          message: detail.message,
          status: response.status,
        });
      } else {
        onAuthError?.({
          code: "chatkit.auth.unknown",
          message: "Unable to authenticate with the provided publish token.",
          status: response.status,
        });
      }
    }

    return response;
  };
};
