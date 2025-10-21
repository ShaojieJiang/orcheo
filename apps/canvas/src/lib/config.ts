const DEFAULT_BACKEND_URL = "http://localhost:8000";
const DEFAULT_CHATKIT_DOMAIN_KEY = "domain_pk_orcheo_dev";
const DEFAULT_CHATKIT_PLACEHOLDER = "Describe what you want the workflow to do";

const trimTrailingSlash = (value: string) => value.replace(/\/+$/, "");

const isPermittedProtocol = (protocol: string): boolean =>
  ["http:", "https:", "ws:", "wss:"].includes(protocol);

const isValidUrl = (value: string): boolean => {
  if (!value.trim()) {
    return false;
  }
  try {
    const parsed = new URL(value);
    return isPermittedProtocol(parsed.protocol);
  } catch {
    return false;
  }
};

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
  const candidate = fromEnv || DEFAULT_BACKEND_URL;
  const normalised = normaliseBaseUrl(candidate);

  if (fromEnv && !isValidUrl(normalised)) {
    console.warn(
      "Invalid VITE_ORCHEO_BACKEND_URL provided, falling back to default backend URL.",
    );
    return normaliseBaseUrl(DEFAULT_BACKEND_URL);
  }

  return normalised;
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

const resolveEnvString = (value: unknown): string | undefined => {
  if (typeof value !== "string") {
    return undefined;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
};

export const getChatKitDomainKey = (): string => {
  return (
    resolveEnvString(import.meta.env?.VITE_ORCHEO_CHATKIT_DOMAIN_KEY) ??
    DEFAULT_CHATKIT_DOMAIN_KEY
  );
};

export const getChatKitComposerPlaceholder = (): string => {
  return (
    resolveEnvString(import.meta.env?.VITE_ORCHEO_CHATKIT_PLACEHOLDER) ??
    DEFAULT_CHATKIT_PLACEHOLDER
  );
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
