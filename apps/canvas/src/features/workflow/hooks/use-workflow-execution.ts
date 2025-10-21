import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  type BackendExecutionMessage,
  DEFAULT_LANGGRAPH_GRAPH_CONFIG,
  type ExecutionMessage,
  type ExecutionMetrics,
  type ExecutionTokens,
  getWorkflowWebSocketUrl,
} from "@features/workflow/lib/execution-client";

export type ExecutionStatus =
  | "idle"
  | "connecting"
  | "running"
  | "completed"
  | "error"
  | "cancelled";

export interface ExecutionLogEntry {
  timestamp: string;
  level: "INFO" | "DEBUG" | "ERROR" | "WARNING";
  message: string;
}

export interface TokenMetrics {
  prompt: number;
  completion: number;
  total: number;
}

interface StartExecutionOverrides {
  inputs?: Record<string, unknown>;
  graphConfig?: Record<string, unknown>;
  executionId?: string;
}

interface UseWorkflowExecutionOptions {
  workflowId: string | null;
  graphConfig?: Record<string, unknown>;
  inputs?: Record<string, unknown>;
}

const INITIAL_TOKENS: TokenMetrics = { prompt: 0, completion: 0, total: 0 };

const normaliseStatus = (status: string | undefined): ExecutionStatus => {
  if (!status) {
    return "running";
  }

  const value = status.toLowerCase();
  if (value === "completed" || value === "success") {
    return "completed";
  }
  if (value === "error" || value === "failed") {
    return "error";
  }
  if (value === "cancelled") {
    return "cancelled";
  }
  if (value === "running") {
    return "running";
  }
  return "running";
};

const parseTokens = (
  metrics: ExecutionMetrics | undefined,
): ExecutionTokens | null => {
  if (!metrics || !metrics.tokens) {
    return null;
  }

  const { prompt = 0, completion = 0, total } = metrics.tokens;
  return {
    prompt,
    completion,
    total: typeof total === "number" ? total : prompt + completion,
  };
};

const nowIso = () => new Date().toISOString();

export const useWorkflowExecution = (options: UseWorkflowExecutionOptions) => {
  const { workflowId, graphConfig, inputs } = options;

  const [status, setStatus] = useState<ExecutionStatus>("idle");
  const [executionId, setExecutionId] = useState<string | null>(null);
  const [logs, setLogs] = useState<ExecutionLogEntry[]>([]);
  const [tokenMetrics, setTokenMetrics] =
    useState<TokenMetrics>(INITIAL_TOKENS);
  const [lastError, setLastError] = useState<string | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const statusRef = useRef<ExecutionStatus>("idle");
  const payloadRef = useRef({
    graphConfig: graphConfig ?? DEFAULT_LANGGRAPH_GRAPH_CONFIG,
    inputs: inputs ?? {},
  });

  useEffect(() => {
    payloadRef.current = {
      graphConfig: graphConfig ?? DEFAULT_LANGGRAPH_GRAPH_CONFIG,
      inputs: inputs ?? {},
    };
  }, [graphConfig, inputs]);

  useEffect(() => {
    statusRef.current = status;
  }, [status]);

  const appendLog = useCallback((entry: ExecutionLogEntry) => {
    setLogs((previous) => {
      const next = [...previous, entry];
      if (next.length > 200) {
        return next.slice(next.length - 200);
      }
      return next;
    });
  }, []);

  const closeSocket = useCallback(() => {
    const socket = socketRef.current;
    if (socket) {
      try {
        socket.close();
      } catch (error) {
        console.warn("Failed to close execution socket", error);
      }
    }
    socketRef.current = null;
  }, []);

  const resetState = useCallback(() => {
    setLogs([]);
    setTokenMetrics(INITIAL_TOKENS);
    setExecutionId(null);
    setLastError(null);
    setStatus("idle");
  }, []);

  useEffect(() => () => closeSocket(), [closeSocket]);

  const startExecution = useCallback(
    async (overrides?: StartExecutionOverrides): Promise<string | null> => {
      if (!workflowId) {
        setLastError("Backend workflow ID is not configured for execution.");
        setStatus("error");
        return null;
      }

      if (typeof window === "undefined" || typeof WebSocket === "undefined") {
        setLastError(
          "WebSocket streaming is not available in this environment.",
        );
        setStatus("error");
        return null;
      }

      closeSocket();
      setLogs([]);
      setTokenMetrics(INITIAL_TOKENS);
      setLastError(null);

      const executionIdentifier =
        overrides?.executionId ??
        globalThis.crypto?.randomUUID?.() ??
        `execution-${Math.random().toString(36).slice(2)}`;

      setExecutionId(executionIdentifier);
      setStatus("connecting");

      let socket: WebSocket;
      try {
        socket = new WebSocket(getWorkflowWebSocketUrl(workflowId));
      } catch (error) {
        const message =
          error instanceof Error
            ? error.message
            : "Unable to initialise WebSocket connection.";
        setLastError(message);
        setStatus("error");
        return null;
      }

      const resolvedPayload = {
        type: "run_workflow",
        graph_config: overrides?.graphConfig ?? payloadRef.current.graphConfig,
        inputs: overrides?.inputs ?? payloadRef.current.inputs,
        execution_id: executionIdentifier,
      } satisfies Record<string, unknown>;

      socket.addEventListener("open", () => {
        try {
          socket.send(JSON.stringify(resolvedPayload));
          appendLog({
            timestamp: nowIso(),
            level: "INFO",
            message: "Started backend execution stream.",
          });
          setStatus("running");
        } catch (error) {
          const message =
            error instanceof Error
              ? error.message
              : "Failed to send execution payload.";
          setLastError(message);
          appendLog({ timestamp: nowIso(), level: "ERROR", message });
          setStatus("error");
        }
      });

      socket.addEventListener("message", (event) => {
        const timestamp = nowIso();

        let payload: ExecutionMessage | BackendExecutionMessage | null = null;
        try {
          payload = JSON.parse(event.data);
        } catch {
          appendLog({
            timestamp,
            level: "ERROR",
            message: "Received non-JSON execution payload.",
          });
          return;
        }

        if (!payload || typeof payload !== "object") {
          return;
        }

        const metrics =
          payload.metrics ??
          (typeof payload.payload === "object"
            ? payload.payload?.metrics
            : undefined);
        const tokens = parseTokens(metrics as ExecutionMetrics | undefined);
        if (tokens) {
          setTokenMetrics(tokens);
        }

        if (payload.status) {
          const nextStatus = normaliseStatus(payload.status);
          appendLog({
            timestamp,
            level: nextStatus === "error" ? "ERROR" : "INFO",
            message: `Status update: ${payload.status}`,
          });
          setStatus(nextStatus);
          return;
        }

        if (payload.node || payload.event) {
          appendLog({
            timestamp,
            level: "DEBUG",
            message: `[${payload.event ?? "update"}] ${payload.node ?? "node"}`,
          });
          return;
        }

        appendLog({
          timestamp,
          level: "INFO",
          message: `Update: ${JSON.stringify(payload)}`,
        });
      });

      socket.addEventListener("error", (event) => {
        console.error("Workflow execution socket error", event);
        setLastError("Encountered an error while streaming execution updates.");
        setStatus("error");
      });

      socket.addEventListener("close", () => {
        if (!socketRef.current || statusRef.current === "idle") {
          return;
        }
        setStatus((previous) => {
          if (
            previous === "completed" ||
            previous === "error" ||
            previous === "cancelled"
          ) {
            return previous;
          }
          appendLog({
            timestamp: nowIso(),
            level: "WARNING",
            message: "Execution stream closed by remote host.",
          });
          return "idle";
        });
      });

      socketRef.current = socket;
      return executionIdentifier;
    },
    [appendLog, closeSocket, workflowId],
  );

  const stopExecution = useCallback(() => {
    closeSocket();
    setStatus("idle");
  }, [closeSocket]);

  return useMemo(
    () => ({
      status,
      executionId,
      logs,
      tokenMetrics,
      lastError,
      startExecution,
      stopExecution,
      reset: resetState,
    }),
    [
      executionId,
      lastError,
      logs,
      resetState,
      startExecution,
      status,
      stopExecution,
      tokenMetrics,
    ],
  );
};

export type { ExecutionMessage };
