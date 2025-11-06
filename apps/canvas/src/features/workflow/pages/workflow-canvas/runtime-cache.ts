import type { NodeRuntimeCacheEntry } from "@features/workflow/components/panels/node-inspector";

const NODE_RUNTIME_CACHE_PREFIX = "orcheo:workflow-runtime-cache:";

export const getRuntimeCacheStorageKey = (workflowId?: string | null) => {
  return `${NODE_RUNTIME_CACHE_PREFIX}${workflowId ?? "unsaved"}`;
};

export const readRuntimeCacheFromSession = (
  key: string,
): Record<string, NodeRuntimeCacheEntry> => {
  if (typeof window === "undefined" || !window.sessionStorage) {
    return {};
  }

  const raw = window.sessionStorage.getItem(key);
  if (!raw) {
    return {};
  }

  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === "object") {
      return parsed as Record<string, NodeRuntimeCacheEntry>;
    }
  } catch (error) {
    console.warn(
      "Failed to parse node runtime cache from sessionStorage",
      error,
    );
  }

  return {};
};

export const persistRuntimeCacheToSession = (
  key: string,
  cache: Record<string, NodeRuntimeCacheEntry>,
) => {
  if (typeof window === "undefined" || !window.sessionStorage) {
    return;
  }

  if (Object.keys(cache).length === 0) {
    window.sessionStorage.removeItem(key);
    return;
  }

  try {
    const serialized = JSON.stringify(cache);
    window.sessionStorage.setItem(key, serialized);
  } catch (error) {
    console.warn(
      "Failed to persist node runtime cache to sessionStorage",
      error,
    );
  }
};

export const clearRuntimeCacheFromSession = (key: string) => {
  if (typeof window === "undefined" || !window.sessionStorage) {
    return;
  }

  window.sessionStorage.removeItem(key);
};
