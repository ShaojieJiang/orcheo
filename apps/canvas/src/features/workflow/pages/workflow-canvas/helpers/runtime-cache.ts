const NODE_RUNTIME_CACHE_PREFIX = "orcheo:workflow-runtime-cache:";

export const getRuntimeCacheStorageKey = (
  workflowId?: string | null,
): string => {
  return `${NODE_RUNTIME_CACHE_PREFIX}${workflowId ?? "unsaved"}`;
};

export const readRuntimeCacheFromSession = <
  TValue extends Record<string, unknown>,
>(
  key: string,
): TValue => {
  if (typeof window === "undefined" || !window.sessionStorage) {
    return {} as TValue;
  }

  const raw = window.sessionStorage.getItem(key);
  if (!raw) {
    return {} as TValue;
  }

  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === "object") {
      return parsed as TValue;
    }
  } catch (error) {
    console.warn(
      "Failed to parse node runtime cache from sessionStorage",
      error,
    );
  }

  return {} as TValue;
};

export const persistRuntimeCacheToSession = <TValue extends Record<
  string,
  unknown
>>(
  key: string,
  cache: TValue,
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
