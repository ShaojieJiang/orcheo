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
const HEARTBEAT_ACTIVE_MS = 5_000;
const HEARTBEAT_IDLE_MS = 30_000;
const MAX_RETRIES = 3;
const INITIAL_BACKOFF_MS = 500;

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
  const body = JSON.stringify({
    session_id: sessionId,
    page: ctx.page,
    workflow_id: ctx.workflowId ?? null,
    workflow_name: ctx.workflowName ?? null,
    focused,
    timestamp: new Date().toISOString(),
  });

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      const res = await fetch(CONTEXT_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
      });
      if (res.ok || res.status < 500) return;
    } catch {
      // Network error — retry with backoff if attempts remain.
    }
    if (attempt < MAX_RETRIES) {
      await new Promise((r) =>
        setTimeout(r, INITIAL_BACKOFF_MS * 2 ** attempt),
      );
    }
  }
}

export function useBrowserContext() {
  const sessionIdRef = useRef<string>(getOrCreateSessionId());
  const contextRef = useRef<PageContext>({ page: "other" });
  const heartbeatRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const startHeartbeat = useCallback(() => {
    if (heartbeatRef.current) return;

    const tick = () => {
      postContext(
        sessionIdRef.current,
        contextRef.current,
        document.hasFocus(),
      );
      // Reduce frequency when the tab is not focused.
      const interval = document.hasFocus()
        ? HEARTBEAT_ACTIVE_MS
        : HEARTBEAT_IDLE_MS;
      heartbeatRef.current = setTimeout(tick, interval);
    };
    heartbeatRef.current = setTimeout(tick, HEARTBEAT_ACTIVE_MS);
  }, []);

  const stopHeartbeat = useCallback(() => {
    if (heartbeatRef.current) {
      clearTimeout(heartbeatRef.current);
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
