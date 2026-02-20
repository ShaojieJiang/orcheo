import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { CredentialsTable } from "./credentials-table";
import type { Credential } from "@features/workflow/types/credential-vault";

const credentials: Credential[] = [
  {
    id: "cred-1",
    name: "wecom_app_secret_eventually",
    type: "WeCom",
    createdAt: "2026-02-20T00:00:00Z",
    updatedAt: "2026-02-20T00:00:00Z",
    access: "public",
    status: "healthy",
    secrets: {
      token: "super-secret-value",
    },
  },
];

describe("CredentialsTable", () => {
  it("uses overflow-safe layout classes in the vault modal", () => {
    const { container } = render(
      <CredentialsTable
        credentials={credentials}
        searchQuery=""
        onDeleteCredential={vi.fn()}
      />,
    );

    expect(container.firstChild).toHaveClass("min-w-0");
    expect(container.firstChild).toHaveClass("overflow-hidden");
    expect(screen.getByRole("table")).toHaveClass("min-w-[900px]");
  });
});
