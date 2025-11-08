import { buildBackendHttpUrl } from "@/lib/config";

export interface PublicChatHttpError {
  status: number;
  message: string;
  code?: string;
}

interface PublicChatFetchOptions {
  workflowId: string;
  backendBaseUrl?: string;
  onHttpError?: (error: PublicChatHttpError) => void;
  metadata?: Record<string, unknown>;
}

type RuntimeConfig = {
  chatkitDomainKey?: unknown;
};

const safeString = (value: unknown): string | undefined => {
  if (typeof value === "string" && value.trim()) {
    return value.trim();
  }
  return undefined;
};

const DEFAULT_DOMAIN_KEY =
  safeString(import.meta.env?.VITE_ORCHEO_CHATKIT_DEFAULT_DOMAIN_KEY) ??
  "domain_pk_localhost_dev";

const getRuntimeDomainKey = (): string | undefined => {
  if (typeof window === "undefined") {
    return undefined;
  }
  const runtimeConfig = (
    window as typeof window & {
      __ORCHEO_CONFIG__?: RuntimeConfig;
    }
  ).__ORCHEO_CONFIG__;
  return safeString(runtimeConfig?.chatkitDomainKey);
};

const parseErrorPayload = async (
  response: Response,
): Promise<Pick<PublicChatHttpError, "message" | "code">> => {
  try {
    const body = await response.json();
    if (!body) {
      return {
        message: response.statusText || "ChatKit request failed.",
      };
    }
    if (typeof body === "string") {
      return { message: body };
    }
    if (typeof body === "object") {
      const detail =
        (("detail" in body ? body.detail : undefined) as Record<
          string,
          unknown
        >) ?? (body as Record<string, unknown>);
      const message =
        safeString(detail?.message) ??
        safeString((body as Record<string, unknown>).message);
      const code =
        safeString(detail?.code) ??
        safeString((body as Record<string, unknown>).code);
      return {
        message:
          message ??
          (response.statusText ||
            "ChatKit request failed. Please retry shortly."),
        code,
      };
    }
    return {
      message: response.statusText || "ChatKit request failed.",
    };
  } catch {
    return {
      message: response.statusText || "ChatKit request failed.",
    };
  }
};

export const getChatKitDomainKey = (): string => {
  const fromEnv = safeString(import.meta.env?.VITE_ORCHEO_CHATKIT_DOMAIN_KEY);
  const fromRuntime = getRuntimeDomainKey();
  return fromEnv ?? fromRuntime ?? DEFAULT_DOMAIN_KEY;
};

export const buildPublicChatFetch = ({
  workflowId,
  backendBaseUrl,
  onHttpError,
  metadata,
}: PublicChatFetchOptions): typeof fetch => {
  const baseFetch = window.fetch.bind(window);
  const resolvedUrl = buildBackendHttpUrl("/api/chatkit", backendBaseUrl);

  const emitError = async (response: Response) => {
    if (!onHttpError) {
      return;
    }
    const detail = await parseErrorPayload(response);
    onHttpError({
      status: response.status,
      message: detail.message,
      code: detail.code,
    });
  };

  return async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const nextInit: RequestInit = {
      ...init,
      credentials: "include",
    };
    // Ensure OAuth HttpOnly cookies are sent with every ChatKit request.

    const headers = new Headers(nextInit.headers ?? {});
    const contentType = headers.get("Content-Type") ?? "";
    const expectsJson = contentType.includes("application/json");
    const stringBody = typeof nextInit.body === "string";

    const augmentPayload = (serialized: string | null) => {
      if (!serialized) {
        return JSON.stringify({
          workflow_id: workflowId,
          metadata: {
            ...(metadata ?? {}),
            workflow_id: workflowId,
          },
        });
      }
      try {
        const payload = JSON.parse(serialized);
        if (payload && typeof payload === "object") {
          if (!payload.workflow_id) {
            payload.workflow_id = workflowId;
          }
          const payloadMetadata =
            payload.metadata && typeof payload.metadata === "object"
              ? { ...(payload.metadata as Record<string, unknown>) }
              : {};
          if (metadata) {
            Object.assign(payloadMetadata, metadata);
          }
          payloadMetadata.workflow_id = workflowId;
          payload.metadata = payloadMetadata;
        }
        return JSON.stringify(payload);
      } catch {
        return serialized;
      }
    };

    if (expectsJson || stringBody || !nextInit.body) {
      nextInit.body = augmentPayload(
        stringBody ? (nextInit.body as string) : null,
      );
      headers.set("Content-Type", "application/json");
    }

    nextInit.headers = headers;

    const requestInfo = input ?? resolvedUrl;
    const response = await baseFetch(requestInfo, nextInit);

    if (!response.ok) {
      await emitError(response.clone());
    }

    return response;
  };
};
