import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import AgentSettingsTab from "@features/account/components/settings/agent-settings-tab";
import {
  getExternalAgentLoginSession,
  getExternalAgents,
  refreshExternalAgents,
  startExternalAgentLogin,
  submitExternalAgentLoginInput,
} from "@/lib/api";

vi.mock("@/lib/api", () => ({
  getExternalAgents: vi.fn(),
  refreshExternalAgents: vi.fn(),
  startExternalAgentLogin: vi.fn(),
  getExternalAgentLoginSession: vi.fn(),
  submitExternalAgentLoginInput: vi.fn(),
}));

const mockProviders = [
  {
    provider: "claude_code" as const,
    display_name: "Claude Code",
    state: "needs_login" as const,
    installed: true,
    authenticated: false,
    supports_oauth: true,
    resolved_version: "1.0.0",
    executable_path: "/data/claude/bin/claude",
    checked_at: "2026-03-31T10:00:00Z",
    last_auth_ok_at: null,
    detail: "OAuth login is required on the worker.",
    active_session_id: null,
  },
  {
    provider: "codex" as const,
    display_name: "Codex",
    state: "not_installed" as const,
    installed: false,
    authenticated: false,
    supports_oauth: true,
    resolved_version: null,
    executable_path: null,
    checked_at: "2026-03-31T10:00:00Z",
    last_auth_ok_at: null,
    detail: "Runtime not installed on the worker yet.",
    active_session_id: null,
  },
];

describe("AgentSettingsTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getExternalAgents).mockResolvedValue({
      providers: mockProviders,
    });
    vi.mocked(refreshExternalAgents).mockResolvedValue({
      providers: mockProviders,
    });
    vi.mocked(startExternalAgentLogin).mockResolvedValue({
      session_id: "session-1",
      provider: "codex",
      display_name: "Codex",
      state: "pending",
      created_at: "2026-03-31T10:00:00Z",
      updated_at: "2026-03-31T10:00:00Z",
      completed_at: null,
      auth_url: null,
      device_code: null,
      detail: "Preparing the worker-side OAuth flow.",
      recent_output: null,
      resolved_version: null,
      executable_path: null,
    });
    vi.mocked(getExternalAgentLoginSession).mockResolvedValue({
      session_id: "session-1",
      provider: "codex",
      display_name: "Codex",
      state: "authenticated",
      created_at: "2026-03-31T10:00:00Z",
      updated_at: "2026-03-31T10:00:02Z",
      completed_at: "2026-03-31T10:00:02Z",
      auth_url: null,
      device_code: null,
      detail: "Worker authentication completed successfully.",
      recent_output: "Done",
      resolved_version: "0.30.0",
      executable_path: "/data/codex/bin/codex",
    });
    vi.mocked(submitExternalAgentLoginInput).mockResolvedValue({
      session_id: "session-claude",
      provider: "claude_code",
      display_name: "Claude Code",
      state: "awaiting_oauth",
      created_at: "2026-03-31T10:00:00Z",
      updated_at: "2026-03-31T10:00:02Z",
      completed_at: null,
      auth_url: "https://claude.ai",
      device_code: null,
      detail: "Auth code submitted to the worker. Waiting for completion.",
      recent_output: "Paste the code back into Claude Code",
      resolved_version: "2.1.89",
      executable_path: "/data/claude/bin/claude",
    });
    global.fetch = vi.fn().mockResolvedValue({
      json: async () => [],
    } as Response);
  });

  afterEach(() => {
    cleanup();
  });

  it("renders worker-scoped provider cards", async () => {
    render(<AgentSettingsTab />);

    expect(screen.getByText("External Agents")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Claude Code")).toBeInTheDocument();
      expect(screen.getByText("Codex")).toBeInTheDocument();
    });

    expect(
      screen.getByText(/OAuth happens on the execution worker/i),
    ).toBeInTheDocument();
    expect(screen.getByText("Local Agent Context Bridge")).toBeInTheDocument();
    expect(
      screen.getByText(
        /does not authenticate worker-side Claude Code or Codex workflow nodes/i,
      ),
    ).toBeInTheDocument();
  });

  it("starts the worker login flow from Canvas", async () => {
    const user = userEvent.setup();
    render(<AgentSettingsTab />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /install and connect/i }),
      ).toBeVisible();
    });

    await user.click(
      screen.getAllByRole("button", { name: /install and connect/i })[0],
    );

    await waitFor(() => {
      expect(startExternalAgentLogin).toHaveBeenCalledWith("codex");
    });
  });

  it("submits a Claude auth code back to the worker session", async () => {
    const user = userEvent.setup();
    vi.mocked(getExternalAgents).mockResolvedValue({
      providers: [
        {
          ...mockProviders[0],
          active_session_id: "session-claude",
        },
        mockProviders[1],
      ],
    });
    vi.mocked(refreshExternalAgents).mockResolvedValue({
      providers: [
        {
          ...mockProviders[0],
          active_session_id: "session-claude",
        },
        mockProviders[1],
      ],
    });
    vi.mocked(getExternalAgentLoginSession).mockResolvedValue({
      session_id: "session-claude",
      provider: "claude_code",
      display_name: "Claude Code",
      state: "awaiting_oauth",
      created_at: "2026-03-31T10:00:00Z",
      updated_at: "2026-03-31T10:00:02Z",
      completed_at: null,
      auth_url: "https://claude.ai",
      device_code: null,
      detail: "Complete the browser sign-in.",
      recent_output: "Paste the code back into Claude Code",
      resolved_version: "2.1.89",
      executable_path: "/data/claude/bin/claude",
    });

    render(<AgentSettingsTab />);

    const input = await screen.findByPlaceholderText(/paste claude auth code/i);
    await user.type(input, "ABCD-1234");
    await user.click(screen.getByRole("button", { name: /submit code/i }));

    await waitFor(() => {
      expect(submitExternalAgentLoginInput).toHaveBeenCalledWith(
        "session-claude",
        {
          input_text: "ABCD-1234",
        },
      );
    });
  });
});
