import { useCallback, useEffect, useRef, useState } from "react";
import { requestWorkflowChatSession } from "@features/chatkit/lib/workflow-session";

export type VibeChatSessionStatus = "idle" | "loading" | "ready" | "error";

const SESSION_REFRESH_BUFFER_MS = 30_000;

export function useVibeChat(workflowId: string | null) {
  const [sessionStatus, setSessionStatus] =
    useState<VibeChatSessionStatus>("idle");
  const [sessionError, setSessionError] = useState<string | null>(null);
  const secretRef = useRef<string | null>(null);
  const expiresAtRef = useRef<number | null>(null);
  const refreshingRef = useRef(false);

  const refreshSession = useCallback(async (): Promise<string> => {
    if (!workflowId) {
      throw new Error("No workflow ID for chat session");
    }

    refreshingRef.current = true;
    setSessionStatus("loading");
    setSessionError(null);

    try {
      const session = await requestWorkflowChatSession(workflowId);
      secretRef.current = session.clientSecret;
      expiresAtRef.current = session.expiresAt;
      setSessionStatus("ready");
      return session.clientSecret;
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Chat session request failed";
      secretRef.current = null;
      expiresAtRef.current = null;
      setSessionStatus("error");
      setSessionError(message);
      throw err;
    } finally {
      refreshingRef.current = false;
    }
  }, [workflowId]);

  const getClientSecret = useCallback(
    async (/* currentSecret */): Promise<string> => {
      const now = Date.now();
      const isExpired =
        expiresAtRef.current !== null &&
        now >= expiresAtRef.current - SESSION_REFRESH_BUFFER_MS;

      if (secretRef.current && !isExpired) {
        return secretRef.current;
      }
      return refreshSession();
    },
    [refreshSession],
  );

  useEffect(() => {
    if (!workflowId) {
      secretRef.current = null;
      expiresAtRef.current = null;
      setSessionStatus("idle");
      setSessionError(null);
      return;
    }
    void refreshSession();
  }, [workflowId, refreshSession]);

  return { getClientSecret, sessionStatus, sessionError, refreshSession };
}
