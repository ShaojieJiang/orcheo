import { useCallback, useEffect, useRef, useState } from "react";
import { requestWorkflowChatSession } from "@features/chatkit/lib/workflow-session";

export type VibeChatSessionStatus = "idle" | "loading" | "ready" | "error";

const SESSION_REFRESH_BUFFER_MS = 30_000;
const MAX_REFRESH_RETRIES = 3;
const RETRY_BASE_DELAY_MS = 2_000;

export function useVibeChat(workflowId: string | null) {
  const [sessionStatus, setSessionStatus] =
    useState<VibeChatSessionStatus>("idle");
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [hasSession, setHasSession] = useState(false);
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

    let lastErr: unknown;
    for (let attempt = 0; attempt < MAX_REFRESH_RETRIES; attempt++) {
      if (attempt > 0) {
        await new Promise((resolve) =>
          setTimeout(resolve, RETRY_BASE_DELAY_MS * attempt),
        );
      }
      try {
        const session = await requestWorkflowChatSession(workflowId);
        secretRef.current = session.clientSecret;
        expiresAtRef.current = session.expiresAt;
        setHasSession(true);
        setSessionStatus("ready");
        refreshingRef.current = false;
        return session.clientSecret;
      } catch (err) {
        lastErr = err;
      }
    }

    const message =
      lastErr instanceof Error
        ? lastErr.message
        : "Chat session request failed";
    secretRef.current = null;
    expiresAtRef.current = null;
    setHasSession(false);
    setSessionStatus("error");
    setSessionError(message);
    refreshingRef.current = false;
    throw lastErr;
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
      setHasSession(false);
      setSessionStatus("idle");
      setSessionError(null);
      return;
    }
    void refreshSession();
  }, [workflowId, refreshSession]);

  return {
    getClientSecret,
    sessionStatus,
    sessionError,
    hasSession,
    refreshSession,
  };
}
