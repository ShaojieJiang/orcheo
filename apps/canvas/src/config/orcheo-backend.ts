const DEFAULT_BACKEND_BASE_URL = "http://localhost:8000";

type Maybe<T> = T | null | undefined;

const ENV_BACKEND_URL_KEYS = [
  "VITE_ORCHEO_BACKEND_BASE_URL",
  "VITE_BACKEND_BASE_URL",
  "VITE_API_BASE_URL",
] as const;

const stripTrailingSlash = (value: string): string => {
  if (value.endsWith("/")) {
    return value.slice(0, -1);
  }
  return value;
};

const resolveEnvBackendUrl = (): string | undefined => {
  for (const key of ENV_BACKEND_URL_KEYS) {
    const envValue = (import.meta.env as Record<string, Maybe<string>>)[key];
    if (typeof envValue === "string" && envValue.trim().length > 0) {
      return envValue.trim();
    }
  }
  return undefined;
};

const resolveBrowserBase = (): string | undefined => {
  if (typeof window === "undefined") {
    return undefined;
  }
  try {
    const { protocol, host } = window.location;
    if (protocol && host) {
      return `${protocol}//${host}`;
    }
  } catch (error) {
    console.warn("Failed to resolve browser origin", error);
  }
  return undefined;
};

const normaliseToUrl = (value: string): URL => {
  try {
    return new URL(value);
  } catch {
    if (typeof window !== "undefined") {
      return new URL(value, window.location.origin);
    }
    return new URL(DEFAULT_BACKEND_BASE_URL);
  }
};

export const getBackendBaseUrl = (): string => {
  const envUrl = resolveEnvBackendUrl();
  if (envUrl) {
    return stripTrailingSlash(envUrl);
  }
  const browserUrl = resolveBrowserBase();
  if (browserUrl) {
    return stripTrailingSlash(browserUrl);
  }
  return DEFAULT_BACKEND_BASE_URL;
};

export const getHttpApiBaseUrl = (): string => {
  const base = normaliseToUrl(getBackendBaseUrl());
  const apiPath = stripTrailingSlash(base.pathname);
  const resolvedPath = apiPath ? `${apiPath}/api` : "/api";
  const apiUrl = new URL(base.toString());
  apiUrl.pathname = resolvedPath;
  return stripTrailingSlash(apiUrl.toString());
};

export const buildWorkflowWebSocketUrl = (workflowId: string): string => {
  const trimmed = workflowId.trim();
  if (!trimmed) {
    throw new Error("workflowId is required to build a WebSocket URL");
  }
  const base = normaliseToUrl(getBackendBaseUrl());
  const wsProtocol = base.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = new URL(base.toString());
  wsUrl.protocol = wsProtocol;
  wsUrl.pathname = `${stripTrailingSlash(wsUrl.pathname)}/ws/workflow/${encodeURIComponent(trimmed)}`;
  wsUrl.search = "";
  wsUrl.hash = "";
  return wsUrl.toString();
};

export const toApiUrl = (path: string): string => {
  const normalisedPath = path.startsWith("/") ? path : `/${path}`;
  const apiBase = getHttpApiBaseUrl();
  const apiUrl = new URL(apiBase);
  apiUrl.pathname = `${stripTrailingSlash(apiUrl.pathname)}${normalisedPath}`;
  return apiUrl.toString();
};
