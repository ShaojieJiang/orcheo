const TOKEN_QUERY_KEY = "token";
const HISTORY_STATE_KEYS = ["chatkitPublishToken", "publishToken"] as const;
let inMemoryToken: string | null = null;

const normaliseToken = (value: unknown): string | null => {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
};

const readFromHistory = (state: unknown): string | null => {
  if (!state || typeof state !== "object") {
    return null;
  }
  for (const key of HISTORY_STATE_KEYS) {
    const candidate = normaliseToken((state as Record<string, unknown>)[key]);
    if (candidate) {
      return candidate;
    }
  }
  return null;
};

const readFromGlobal = (): string | null => {
  if (typeof window === "undefined") {
    return null;
  }
  const globalValue = (
    window as typeof window & { __ORCHEO_CHATKIT_PUBLISH_TOKEN__?: string }
  ).__ORCHEO_CHATKIT_PUBLISH_TOKEN__;
  return normaliseToken(globalValue);
};

const readFromQuery = (currentUrl: URL): string | null => {
  const queryValue = currentUrl.searchParams.get(TOKEN_QUERY_KEY);
  return normaliseToken(queryValue);
};

const scrubTokenFromUrl = (currentUrl: URL) => {
  if (typeof window === "undefined") {
    return;
  }
  currentUrl.searchParams.delete(TOKEN_QUERY_KEY);
  const replacement = `${currentUrl.pathname}${currentUrl.search}${currentUrl.hash}`;
  try {
    window.history.replaceState(window.history.state, "", replacement);
  } catch (error) {
    console.warn("Failed to scrub publish token from URL", error);
  }
};

export const setPublishToken = (value: string | null) => {
  inMemoryToken = normaliseToken(value);
};

export const getPublishToken = (): string | null => inMemoryToken;

export const clearPublishToken = () => {
  inMemoryToken = null;
};

const resolveFromEnvironment = (): string | null => {
  if (typeof window === "undefined") {
    return null;
  }
  const historyToken = readFromHistory(window.history?.state ?? null);
  if (historyToken) {
    return historyToken;
  }

  const globalToken = readFromGlobal();
  if (globalToken) {
    return globalToken;
  }

  const currentUrl = new URL(window.location.href);
  const queryToken = readFromQuery(currentUrl);
  if (queryToken) {
    scrubTokenFromUrl(currentUrl);
    return queryToken;
  }

  return null;
};

export const ensurePublishToken = (): string | null => {
  if (inMemoryToken) {
    return inMemoryToken;
  }
  const resolved = resolveFromEnvironment();
  setPublishToken(resolved);
  return resolved;
};
