import { afterEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

const { toastMock } = vi.hoisted(() => ({
  toastMock: vi.fn(() => ({
    dismiss: vi.fn(),
    update: vi.fn(),
  })),
}));

vi.mock("@/hooks/use-toast", () => ({
  toast: toastMock,
}));

import {
  collectCredentialPlaceholderNames,
  describeCredentialVaultReadiness,
  describeRequiredCredentialPlaceholders,
  showCredentialReminderToast,
} from "./credential-vault-reminder";

afterEach(() => {
  vi.clearAllMocks();
  vi.useRealTimers();
});

describe("credential vault reminder helpers", () => {
  it("collects sorted unique placeholder names from nested values", () => {
    const placeholders = collectCredentialPlaceholderNames({
      script: `
        agent = AgentNode(model_kwargs={"api_key": "[[openai_api_key]]"})
        token = "[[telegram_token]]"
      `,
      runnableConfig: {
        configurable: {
          telegram_chat_id: "[[telegram_chat_id]]",
          nested: ["[[openai_api_key]]", "[[telegram_chat_id#value]]"],
        },
      },
    });

    expect(placeholders).toEqual([
      "openai_api_key",
      "telegram_chat_id",
      "telegram_token",
    ]);
  });

  it("describes readiness with exact placeholder names", () => {
    expect(
      describeCredentialVaultReadiness({
        workflow_id: "wf-1",
        status: "missing",
        referenced_credentials: [],
        available_credentials: ["openai_api_key"],
        missing_credentials: ["telegram_chat_id", "telegram_token"],
      }),
    ).toContain("telegram_chat_id, telegram_token");
    expect(
      describeCredentialVaultReadiness({
        workflow_id: "wf-1",
        status: "ready",
        referenced_credentials: [
          {
            name: "openai_api_key",
            placeholders: ["[[openai_api_key]]"],
            available: true,
          },
        ],
        available_credentials: ["openai_api_key"],
        missing_credentials: [],
      }),
    ).toBeNull();
    expect(
      describeCredentialVaultReadiness({
        workflow_id: "wf-1",
        status: "not_required",
        referenced_credentials: [],
        available_credentials: [],
        missing_credentials: [],
      }),
    ).toBeNull();
    expect(
      describeRequiredCredentialPlaceholders([
        "openai_api_key",
        "telegram_chat_id",
      ]),
    ).toContain("openai_api_key, telegram_chat_id");
  });

  it("shows the toast once and returns cleanup", () => {
    const cleanup = showCredentialReminderToast({
      title: "Workflow loaded",
      description: "Add telegram_token and openai_api_key.",
      highlightedCredentialNames: ["telegram_token", "openai_api_key"],
    });

    expect(toastMock).toHaveBeenCalledTimes(1);
    expect(
      renderToStaticMarkup(toastMock.mock.calls[0][0].description),
    ).toContain("<strong>telegram_token</strong>");
    expect(
      renderToStaticMarkup(toastMock.mock.calls[0][0].description),
    ).toContain("<strong>openai_api_key</strong>");

    cleanup();
  });
});
