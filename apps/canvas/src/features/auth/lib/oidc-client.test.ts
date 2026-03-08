import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { startOidcLogin } from "@features/auth/lib/oidc-client";

const mutableEnv = import.meta.env as unknown as Record<string, unknown>;
const originalEnv = { ...mutableEnv };

const setEnv = (key: string, value: string | undefined): void => {
  if (value === undefined) {
    delete mutableEnv[key];
    return;
  }
  mutableEnv[key] = value;
};

const restoreEnv = (): void => {
  Object.keys(mutableEnv).forEach((key) => {
    if (!(key in originalEnv)) {
      delete mutableEnv[key];
    }
  });
  Object.entries(originalEnv).forEach(([key, value]) => {
    mutableEnv[key] = value;
  });
};

describe("startOidcLogin organization precedence", () => {
  beforeEach(() => {
    setEnv("VITE_ORCHEO_AUTH_ISSUER", "https://issuer.example.com");
    setEnv("VITE_ORCHEO_AUTH_CLIENT_ID", "canvas-client");
    setEnv(
      "VITE_ORCHEO_AUTH_REDIRECT_URI",
      "https://canvas.example.com/auth/callback",
    );
    setEnv("VITE_ORCHEO_AUTH_SCOPES", "openid profile email");

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          authorization_endpoint: "https://issuer.example.com/authorize",
          token_endpoint: "https://issuer.example.com/token",
        }),
      }),
    );
  });

  afterEach(() => {
    restoreEnv();
    window.sessionStorage.clear();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("uses configured organization even when a different one is passed", async () => {
    setEnv("VITE_ORCHEO_AUTH_ORGANIZATION", "org_configured");
    const assignMock = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign: assignMock });

    await startOidcLogin({
      organization: "org_attacker",
      organizationName: "attacker-name",
    });

    const [redirectUrl] = assignMock.mock.calls[0] as [string];
    const authUrl = new URL(redirectUrl);

    expect(authUrl.searchParams.get("organization")).toBe("org_configured");
    expect(authUrl.searchParams.get("organization_name")).toBeNull();
  });

  it("uses runtime organization when no configured organization is set", async () => {
    setEnv("VITE_ORCHEO_AUTH_ORGANIZATION", undefined);
    const assignMock = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign: assignMock });

    await startOidcLogin({
      organization: "org_runtime",
      organizationName: "runtime-name",
    });

    const [redirectUrl] = assignMock.mock.calls[0] as [string];
    const authUrl = new URL(redirectUrl);

    expect(authUrl.searchParams.get("organization")).toBe("org_runtime");
    expect(authUrl.searchParams.get("organization_name")).toBe("runtime-name");
  });
});
