interface AuthTokens {
  accessToken: string;
  idToken?: string;
  refreshToken?: string;
  tokenType?: string;
  expiresAt?: number;
}

const AUTH_TOKENS_KEY = "orcheo_canvas_auth_tokens";
const TOKEN_EXPIRY_SKEW_MS = 60_000;

const safeLocalStorageGet = (key: string): string | null => {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
};

const safeLocalStorageSet = (key: string, value: string | null): void => {
  if (typeof window === "undefined") {
    return;
  }

  try {
    if (value === null) {
      window.localStorage.removeItem(key);
      return;
    }

    window.localStorage.setItem(key, value);
  } catch {
    return;
  }
};

const parseTokens = (raw: string | null): AuthTokens | null => {
  if (!raw) {
    return null;
  }
  try {
    const parsed = JSON.parse(raw) as Partial<AuthTokens>;
    if (!parsed.accessToken) {
      return null;
    }
    return {
      accessToken: parsed.accessToken,
      idToken: parsed.idToken,
      refreshToken: parsed.refreshToken,
      tokenType: parsed.tokenType,
      expiresAt: parsed.expiresAt,
    };
  } catch {
    return null;
  }
};

const isTokenFresh = (tokens: AuthTokens | null): boolean => {
  if (!tokens?.accessToken) {
    return false;
  }
  if (!tokens.expiresAt) {
    return true;
  }
  return Date.now() < tokens.expiresAt - TOKEN_EXPIRY_SKEW_MS;
};

export const getAuthTokens = (): AuthTokens | null =>
  parseTokens(safeLocalStorageGet(AUTH_TOKENS_KEY));

export const setAuthTokens = (tokens: AuthTokens): void => {
  safeLocalStorageSet(AUTH_TOKENS_KEY, JSON.stringify(tokens));
};

export const clearAuthSession = (): void => {
  safeLocalStorageSet(AUTH_TOKENS_KEY, null);
};

export const getAccessToken = (): string | null => {
  const tokens = getAuthTokens();
  if (!isTokenFresh(tokens)) {
    clearAuthSession();
    return null;
  }
  return tokens.accessToken;
};

export const isAuthenticated = (): boolean => Boolean(getAccessToken());
