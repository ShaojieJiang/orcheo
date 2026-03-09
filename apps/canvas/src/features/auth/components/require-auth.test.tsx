import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

const { isAuthenticatedMock } = vi.hoisted(() => ({
  isAuthenticatedMock: vi.fn(),
}));

vi.mock("@features/auth/lib/auth-session", () => ({
  isAuthenticated: isAuthenticatedMock,
}));

describe("RequireAuth", () => {
  beforeEach(() => {
    isAuthenticatedMock.mockReset();
    isAuthenticatedMock.mockReturnValue(false);
  });
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  const renderWithAuth = async (issuerValue: string | undefined) => {
    vi.stubEnv("VITE_ORCHEO_AUTH_ISSUER", issuerValue ?? "");

    // Re-import to pick up the new env value
    vi.resetModules();
    const { default: RequireAuth } =
      await import("@features/auth/components/require-auth");

    return render(
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route element={<RequireAuth />}>
            <Route path="/" element={<div>protected content</div>} />
          </Route>
          <Route path="/login" element={<div>login page</div>} />
        </Routes>
      </MemoryRouter>,
    );
  };

  it("allows access when auth issuer is empty", async () => {
    await renderWithAuth("");
    expect(screen.getByText("protected content")).toBeInTheDocument();
  });

  it("allows access when auth issuer is undefined", async () => {
    await renderWithAuth(undefined);
    expect(screen.getByText("protected content")).toBeInTheDocument();
  });

  it("allows access when auth issuer is a placeholder string", async () => {
    await renderWithAuth("__VITE_ORCHEO_AUTH_ISSUER__");
    expect(screen.getByText("protected content")).toBeInTheDocument();
  });

  it("redirects to login when auth issuer is a valid URL and not authenticated", async () => {
    await renderWithAuth("https://auth.example.com");
    expect(screen.getByText("login page")).toBeInTheDocument();
  });

  it("allows access when auth issuer is valid and user is authenticated", async () => {
    isAuthenticatedMock.mockReturnValue(true);
    await renderWithAuth("https://auth.example.com");
    expect(screen.getByText("protected content")).toBeInTheDocument();
  });

  it("allows access when auth issuer is a non-URL string", async () => {
    await renderWithAuth("not-a-url");
    expect(screen.getByText("protected content")).toBeInTheDocument();
  });

  it("redirects to login with http localhost issuer when not authenticated", async () => {
    await renderWithAuth("http://localhost:8080");
    expect(screen.getByText("login page")).toBeInTheDocument();
  });
});
