import {
  afterAll,
  afterEach,
  beforeAll,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AddCredentialDialog } from "./add-credential-dialog";
import { EditCredentialDialog } from "./edit-credential-dialog";
import CredentialsVault from "./credentials-vault";
import type { Credential } from "@features/workflow/types/credential-vault";

const credential: Credential = {
  id: "cred-1",
  name: "Canvas API",
  provider: "openai",
  createdAt: "2026-03-10T00:00:00Z",
  updatedAt: "2026-03-10T00:00:00Z",
  access: "public",
  secrets: {
    secret: "super-secret-value",
  },
};

describe("Credential dialogs", () => {
  const hasPointerCapture = HTMLElement.prototype.hasPointerCapture;
  const setPointerCapture = HTMLElement.prototype.setPointerCapture;
  const releasePointerCapture = HTMLElement.prototype.releasePointerCapture;
  const scrollIntoView = HTMLElement.prototype.scrollIntoView;

  beforeAll(() => {
    Object.defineProperty(HTMLElement.prototype, "hasPointerCapture", {
      configurable: true,
      value: vi.fn(() => false),
    });
    Object.defineProperty(HTMLElement.prototype, "setPointerCapture", {
      configurable: true,
      value: vi.fn(),
    });
    Object.defineProperty(HTMLElement.prototype, "releasePointerCapture", {
      configurable: true,
      value: vi.fn(),
    });
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: vi.fn(),
    });
  });

  afterEach(() => {
    cleanup();
  });

  afterAll(() => {
    Object.defineProperty(HTMLElement.prototype, "hasPointerCapture", {
      configurable: true,
      value: hasPointerCapture,
    });
    Object.defineProperty(HTMLElement.prototype, "setPointerCapture", {
      configurable: true,
      value: setPointerCapture,
    });
    Object.defineProperty(HTMLElement.prototype, "releasePointerCapture", {
      configurable: true,
      value: releasePointerCapture,
    });
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView,
    });
  });

  it("limits the add dialog access options to private and public", async () => {
    const user = userEvent.setup();

    render(<AddCredentialDialog />);

    await user.click(screen.getByRole("button", { name: "Add Credential" }));
    await user.click(screen.getByRole("combobox", { name: "Access" }));

    expect(screen.getByRole("option", { name: "Private" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Public" })).toBeInTheDocument();
    expect(
      screen.queryByRole("option", { name: "Shared" }),
    ).not.toBeInTheDocument();
  });

  it("uses a scrollable vault list container", () => {
    render(<CredentialsVault credentials={[credential]} />);

    expect(screen.getByTestId("credentials-vault-list")).toHaveClass(
      "min-h-0",
      "flex-1",
      "overflow-y-auto",
    );
  });

  it("shows an explicit Show button in the edit dialog", async () => {
    const user = userEvent.setup();

    render(
      <EditCredentialDialog
        credential={credential}
        open
        onOpenChange={() => undefined}
      />,
    );

    const secretInput = screen.getByLabelText("Secret");
    expect(secretInput).toHaveAttribute("type", "password");

    await user.click(screen.getByRole("button", { name: "Show secret value" }));
    expect(secretInput).toHaveAttribute("type", "text");
    expect(
      screen.getByRole("button", { name: "Hide secret value" }),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("combobox", { name: "Access" }));
    expect(screen.getByRole("option", { name: "Private" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Public" })).toBeInTheDocument();
    expect(
      screen.queryByRole("option", { name: "Shared" }),
    ).not.toBeInTheDocument();
  });

  it("keeps legacy shared access visible for existing credentials", async () => {
    const user = userEvent.setup();

    render(
      <EditCredentialDialog
        credential={{ ...credential, access: "shared" }}
        open
        onOpenChange={() => undefined}
      />,
    );

    await user.click(screen.getByRole("combobox", { name: "Access" }));

    expect(
      screen.getByRole("option", { name: "Shared (legacy)" }),
    ).toHaveAttribute("aria-disabled", "true");
  });
});
