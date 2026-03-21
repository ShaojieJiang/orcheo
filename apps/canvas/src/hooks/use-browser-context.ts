/**
 * BrowserContextProvider — relays Canvas page context to the local
 * `orcheo browser-aware` HTTP server so coding agents stay in sync.
 *
 * Usage:
 *   const { setPageContext } = useBrowserContext();
 *   setPageContext({ page: "canvas", workflowId: "abc", workflowName: "My Flow" });
 */

import { useCallback, useEffect, useRef } from "react";

const CONTEXT_URL = "http://localhost:3333/context";
const HEARTBEAT_INTERVAL_MS = 5_000;

interface PageContext {
  page: "gallery" | "canvas" | "other";
  workflowId?: string | null;
  workflowName?: string | null;
}

function getOrCreateSessionId(): string {
  const key = "orcheo_browser_session_id";
  let id = sessionStorage.getItem(key);
  if (!id) {
    id = crypto.randomUUID();
    sessionStorage.setItem(key, id);
  }
  return id;
}

async function postContext(
  sessionId: string,
  ctx: PageContext,
  focused: boolean,
): Promise<void> {
  try {
    await fetch(CONTEXT_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        page: ctx.page,
        workflow_id: ctx.workflowId ?? null,
        workflow_name: ctx.workflowName ?? null,
        focused,
        timestamp: new Date().toISOString(),
      }),
    });
  } catch {
    // Server not running — silently ignore.
  }
}

export function useBrowserContext() {
  const sessionIdRef = useRef<string>(getOrCreateSessionId());
  const contextRef = useRef<PageContext>({ page: "other" });
  const heartbeatRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startHeartbeat = useCallback(() => {
    if (heartbeatRef.current) return;
    heartbeatRef.current = setInterval(() => {
      postContext(
        sessionIdRef.current,
        contextRef.current,
        document.hasFocus(),
      );
    }, HEARTBEAT_INTERVAL_MS);
  }, []);

  const stopHeartbeat = useCallback(() => {
    if (heartbeatRef.current) {
      clearInterval(heartbeatRef.current);
      heartbeatRef.current = null;
    }
  }, []);

  // Visibility / focus listeners — start/stop heartbeat.
  useEffect(() => {
    const handleVisibility = () => {
      if (document.visibilityState === "visible") {
        // Fire immediately on becoming visible, then start heartbeat.
        postContext(
          sessionIdRef.current,
          contextRef.current,
          document.hasFocus(),
        );
        startHeartbeat();
      } else {
        stopHeartbeat();
      }
    };

    const handleFocus = () => {
      postContext(sessionIdRef.current, contextRef.current, true);
    };

    const handleBlur = () => {
      postContext(sessionIdRef.current, contextRef.current, false);
    };

    document.addEventListener("visibilitychange", handleVisibility);
    window.addEventListener("focus", handleFocus);
    window.addEventListener("blur", handleBlur);

    // Start heartbeat if tab is already visible.
    if (document.visibilityState === "visible") {
      startHeartbeat();
    }

    return () => {
      document.removeEventListener("visibilitychange", handleVisibility);
      window.removeEventListener("focus", handleFocus);
      window.removeEventListener("blur", handleBlur);
      stopHeartbeat();
    };
  }, [startHeartbeat, stopHeartbeat]);

  const setPageContext = useCallback((ctx: PageContext) => {
    contextRef.current = ctx;
    // Fire immediately on context change.
    postContext(sessionIdRef.current, ctx, document.hasFocus());
  }, []);

  return { setPageContext };
}
