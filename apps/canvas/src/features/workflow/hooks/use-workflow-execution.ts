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
const MAX_LOG_ENTRIES = 200;

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const isExecutionTokens = (value: unknown): value is ExecutionTokens => {
  if (!isRecord(value)) {
    return false;
  }

  const { prompt, completion, total } = value;
  return (
    typeof prompt === "number" &&
    typeof completion === "number" &&
    (typeof total === "number" || typeof total === "undefined")
  );
};

const isExecutionMetrics = (value: unknown): value is ExecutionMetrics => {
  if (!isRecord(value)) {
    return false;
  }

  if ("tokens" in value && value.tokens !== undefined) {
    return isExecutionTokens(value.tokens);
  }

  return true;
};

const isExecutionPayload = (
  value: unknown,
): value is ExecutionMessage | BackendExecutionMessage => {
  if (!isRecord(value)) {
    return false;
  }

  const { status, node, event, metrics, payload: nestedPayload } = value;

  const hasValidStatus =
    typeof status === "undefined" || typeof status === "string";
  const hasValidNode = typeof node === "undefined" || typeof node === "string";
  const hasValidEvent =
    typeof event === "undefined" || typeof event === "string";
  const hasValidMetrics =
    typeof metrics === "undefined" || isExecutionMetrics(metrics);
  const hasValidNestedMetrics =
    typeof nestedPayload === "undefined" ||
    !isRecord(nestedPayload) ||
    typeof nestedPayload.metrics === "undefined" ||
    isExecutionMetrics(nestedPayload.metrics);

  return (
    hasValidStatus &&
    hasValidNode &&
    hasValidEvent &&
    hasValidMetrics &&
    hasValidNestedMetrics
  );
};

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
      if (next.length > MAX_LOG_ENTRIES) {
        return next.slice(next.length - MAX_LOG_ENTRIES);
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
          const parsed = JSON.parse(event.data);
          if (isExecutionPayload(parsed)) {
            payload = parsed;
          } else {
            appendLog({
              timestamp,
              level: "ERROR",
              message: "Received execution payload with unexpected structure.",
            });
            return;
          }
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
          (payload.metrics && isExecutionMetrics(payload.metrics)
            ? payload.metrics
            : undefined) ??
          (isRecord(payload.payload) &&
          "metrics" in payload.payload &&
          isExecutionMetrics(payload.payload.metrics)
            ? payload.payload.metrics
            : undefined);
        const tokens = parseTokens(metrics);
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
