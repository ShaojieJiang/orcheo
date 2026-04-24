import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { requestWorkflowChatSession } from "@features/chatkit/lib/workflow-session";
import { useVibeChat } from "./use-vibe-chat";

vi.mock("@features/chatkit/lib/workflow-session", () => ({
  requestWorkflowChatSession: vi.fn(),
}));

describe("useVibeChat", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("tracks whether a usable session secret has been loaded", async () => {
    vi.mocked(requestWorkflowChatSession).mockResolvedValue({
      clientSecret: "secret-1",
      expiresAt: Date.now() + 60_000,
    });

    const { result } = renderHook(() => useVibeChat("workflow-1"));

    await waitFor(() => {
      expect(result.current.sessionStatus).toBe("ready");
    });

    expect(result.current.hasSession).toBe(true);
  });

  it("keeps the existing session marked available while refreshing", async () => {
    let resolveRefresh: (value: {
      clientSecret: string;
      expiresAt: number;
    }) => void = () => undefined;
    vi.mocked(requestWorkflowChatSession)
      .mockResolvedValueOnce({
        clientSecret: "secret-1",
        expiresAt: Date.now() - 1,
      })
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveRefresh = resolve;
          }),
      );

    const { result } = renderHook(() => useVibeChat("workflow-1"));

    await waitFor(() => {
      expect(result.current.sessionStatus).toBe("ready");
    });

    const refresh = result.current.getClientSecret(null);

    await waitFor(() => {
      expect(result.current.sessionStatus).toBe("loading");
    });
    expect(result.current.hasSession).toBe(true);

    resolveRefresh({
      clientSecret: "secret-2",
      expiresAt: Date.now() + 60_000,
    });

    await expect(refresh).resolves.toBe("secret-2");
  });

  it("clears cached secrets before refreshing after workflow switch", async () => {
    let resolveWorkflowTwo: (value: {
      clientSecret: string;
      expiresAt: number;
    }) => void = () => undefined;

    vi.mocked(requestWorkflowChatSession)
      .mockResolvedValueOnce({
        clientSecret: "secret-1",
        expiresAt: Date.now() + 60_000,
      })
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveWorkflowTwo = resolve;
          }),
      );

    const { result, rerender } = renderHook(
      ({ workflowId }: { workflowId: string | null }) =>
        useVibeChat(workflowId),
      {
        initialProps: { workflowId: "workflow-1" },
      },
    );

    await waitFor(() => {
      expect(result.current.sessionStatus).toBe("ready");
    });

    rerender({ workflowId: "workflow-2" });

    await waitFor(() => {
      expect(result.current.sessionStatus).toBe("loading");
    });
    expect(result.current.hasSession).toBe(false);

    resolveWorkflowTwo({
      clientSecret: "secret-2",
      expiresAt: Date.now() + 60_000,
    });

    await waitFor(() => {
      expect(result.current.sessionStatus).toBe("ready");
    });

    await expect(result.current.getClientSecret(null)).resolves.toBe(
      "secret-2",
    );
  });
});
