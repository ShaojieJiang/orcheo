export type PublishFetchCallbacks = {
  onAuthError?: (status: number) => void;
  onRateLimit?: (status: number) => void;
};

export type PublishFetchOptions = PublishFetchCallbacks & {
  workflowId: string;
  publishToken: string;
  metadata?: Record<string, unknown>;
  baseFetch?: typeof fetch;
};

const toJson = async (request: Request): Promise<Record<string, unknown>> => {
  try {
    const text = await request.clone().text();
    if (!text) {
      return {};
    }
    const parsed = JSON.parse(text) as Record<string, unknown>;
    if (parsed && typeof parsed === "object") {
      return parsed;
    }
    return {};
  } catch {
    return {};
  }
};

const mergeMetadata = (
  metadata: Record<string, unknown> | undefined,
  workflowId: string,
): Record<string, unknown> | undefined => {
  if (!metadata) {
    return undefined;
  }

  return {
    ...metadata,
    workflow_id: metadata.workflow_id ?? workflowId,
  };
};

export const createPublishFetch = ({
  workflowId,
  publishToken,
  metadata,
  onAuthError,
  onRateLimit,
  baseFetch,
}: PublishFetchOptions): typeof fetch => {
  const fetchImpl = baseFetch ?? fetch;

  return async (
    input: RequestInfo | URL,
    init?: RequestInit,
  ): Promise<Response> => {
    const initialRequest = new Request(input, init);
    const headers = new Headers(initialRequest.headers);
    const method = initialRequest.method.toUpperCase();

    let finalRequest = initialRequest;

    if (method !== "GET" && method !== "HEAD") {
      headers.set("content-type", "application/json");
      const payload = await toJson(initialRequest);

      payload.workflow_id = workflowId;
      payload.publish_token = publishToken;

      const existingMetadata = payload.metadata as
        | Record<string, unknown>
        | undefined;
      const mergedMetadata = mergeMetadata(
        {
          ...metadata,
          ...existingMetadata,
        },
        workflowId,
      );
      if (mergedMetadata) {
        payload.metadata = mergedMetadata;
      }

      finalRequest = new Request(initialRequest, {
        headers,
        credentials: "include",
        body: JSON.stringify(payload),
      });
    } else {
      finalRequest = new Request(initialRequest, {
        headers,
        credentials: "include",
      });
    }

    const response = await fetchImpl(finalRequest);

    if (response.status === 401 || response.status === 403) {
      onAuthError?.(response.status);
    } else if (response.status === 429) {
      onRateLimit?.(response.status);
    }

    return response;
  };
};
