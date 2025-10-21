const DEFAULT_BACKEND_URL = "http://localhost:8000";

const trimTrailingSlash = (value: string) => value.replace(/\/+$/, "");

const normaliseBaseUrl = (value: string): string => {
  if (!value) {
    return DEFAULT_BACKEND_URL;
  }
  const trimmed = value.trim();
  if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
    return trimTrailingSlash(trimmed);
  }
  if (trimmed.startsWith("ws://") || trimmed.startsWith("wss://")) {
    return trimTrailingSlash(trimmed);
  }
  return trimTrailingSlash(`http://${trimmed}`);
};

export const getBackendBaseUrl = (): string => {
  const fromEnv = (import.meta.env?.VITE_ORCHEO_BACKEND_URL ?? "") as string;
  return normaliseBaseUrl(fromEnv || DEFAULT_BACKEND_URL);
};

const ensureHttpProtocol = (baseUrl: string): string => {
  if (baseUrl.startsWith("http://") || baseUrl.startsWith("https://")) {
    return baseUrl;
  }
  if (baseUrl.startsWith("ws://")) {
    return `http://${baseUrl.slice(5)}`;
  }
  if (baseUrl.startsWith("wss://")) {
    return `https://${baseUrl.slice(6)}`;
  }
  return `http://${baseUrl}`;
};

export const buildBackendHttpUrl = (path: string, baseUrl?: string): string => {
  const resolved = ensureHttpProtocol(baseUrl ?? getBackendBaseUrl());
  const normalised = trimTrailingSlash(resolved);
  const suffix = path.startsWith("/") ? path : `/${path}`;
  return `${normalised}${suffix}`;
};

export const buildWorkflowWebSocketUrl = (
  workflowId: string,
  baseUrl?: string,
): string => {
  const resolvedId = workflowId.trim();
  if (!resolvedId) {
    throw new Error("workflowId is required to create a WebSocket URL");
  }
  const resolved = normaliseBaseUrl(baseUrl ?? getBackendBaseUrl());
  if (resolved.startsWith("ws://") || resolved.startsWith("wss://")) {
    return `${trimTrailingSlash(resolved)}/ws/workflow/${resolvedId}`;
  }
  const protocol = resolved.startsWith("https://") ? "wss://" : "ws://";
  const host = resolved.replace(/^https?:\/\//, "").replace(/^ws?:\/\//, "");
  return `${protocol}${trimTrailingSlash(host)}/ws/workflow/${resolvedId}`;
};
