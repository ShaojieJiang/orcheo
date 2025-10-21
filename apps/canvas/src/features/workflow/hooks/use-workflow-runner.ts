import { useCallback, useEffect, useRef, useState } from "react";
import { buildWorkflowWebSocketUrl } from "@/config/orcheo-backend";

type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

export interface WorkflowRunPayload {
  graphConfig: Record<string, unknown>;
  inputs: Record<string, unknown>;
  executionId?: string;
}

export interface WorkflowStreamMessage {
  status?: string;
  node?: string;
  event?: string;
  tokens?: Record<string, number> | { input?: number; output?: number };
  metrics?: {
    tokens?: Record<string, number> | { input?: number; output?: number };
  };
  [key: string]: JsonValue;
}

export interface TokenMetrics {
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  lastUpdatedAt?: string;
}

interface RunnerState {
  status: "idle" | "connecting" | "streaming" | "completed" | "error";
  executionId: string | null;
  error: string | null;
  messages: WorkflowStreamMessage[];
  metrics: TokenMetrics;
  startedAt: string | null;
  completedAt: string | null;
}

interface StreamContext {
  executionId: string;
}

export interface WorkflowRunnerOptions {
  onMessage?: (message: WorkflowStreamMessage, context: StreamContext) => void;
  onError?: (error: Error, context: StreamContext | null) => void;
  onComplete?: (context: StreamContext) => void;
}

const DEFAULT_METRICS: TokenMetrics = {
  inputTokens: 0,
  outputTokens: 0,
  totalTokens: 0,
};

const extractTokenCounts = (
  message: WorkflowStreamMessage,
): Partial<TokenMetrics> | null => {
  const candidate = message.metrics?.tokens ?? message.tokens;
  if (!candidate || typeof candidate !== "object") {
    return null;
  }
  const entries = Object.entries(candidate);
  if (entries.length === 0) {
    return null;
  }

  const normalised: Partial<TokenMetrics> = {};
  for (const [key, value] of entries) {
    if (typeof value !== "number") {
      continue;
    }
    const lower = key.toLowerCase();
    if (lower.includes("prompt") || lower.includes("input")) {
      normalised.inputTokens = (normalised.inputTokens ?? 0) + value;
    } else if (lower.includes("completion") || lower.includes("output")) {
      normalised.outputTokens = (normalised.outputTokens ?? 0) + value;
    } else if (lower.includes("total")) {
      normalised.totalTokens = (normalised.totalTokens ?? 0) + value;
    }
  }

  return Object.keys(normalised).length > 0 ? normalised : null;
};

const mergeTokenMetrics = (
  previous: TokenMetrics,
  incoming: Partial<TokenMetrics>,
  timestamp: string,
): TokenMetrics => {
  const inputTokens = previous.inputTokens + (incoming.inputTokens ?? 0);
  const outputTokens = previous.outputTokens + (incoming.outputTokens ?? 0);
  const totalTokensCandidate = incoming.totalTokens ?? 0;
  const totalTokens =
    totalTokensCandidate > 0
      ? totalTokensCandidate
      : inputTokens + outputTokens;
  return {
    inputTokens,
    outputTokens,
    totalTokens,
    lastUpdatedAt: timestamp,
  };
};

const createWebSocket = (url: string): WebSocket => {
  if (typeof WebSocket === "undefined") {
    throw new Error("WebSocket is not supported in this environment");
  }
  return new WebSocket(url);
};

const generateExecutionId = (): string => {
  if (
    typeof crypto !== "undefined" &&
    "randomUUID" in crypto &&
    typeof crypto.randomUUID === "function"
  ) {
    return crypto.randomUUID();
  }
  return `exec-${Math.random().toString(36).slice(2, 10)}`;
};

export const useWorkflowRunner = (
  workflowId: string | null,
  options?: WorkflowRunnerOptions,
) => {
  const websocketRef = useRef<WebSocket | null>(null);
  const completionTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(
    null,
  );
  const [state, setState] = useState<RunnerState>({
    status: "idle",
    executionId: null,
    error: null,
    messages: [],
    metrics: DEFAULT_METRICS,
    startedAt: null,
    completedAt: null,
  });

  const clearCompletionTimer = useCallback(() => {
    if (completionTimeoutRef.current !== null) {
      clearTimeout(completionTimeoutRef.current);
      completionTimeoutRef.current = null;
    }
  }, []);

  const closeWebSocket = useCallback(() => {
    clearCompletionTimer();
    const websocket = websocketRef.current;
    if (websocket) {
      const { readyState } = websocket;
      if (
        readyState === WebSocket.CONNECTING ||
        readyState === WebSocket.OPEN ||
        readyState === WebSocket.CLOSING
      ) {
        websocket.close();
      }
    }
    websocketRef.current = null;
  }, [clearCompletionTimer]);

  useEffect(() => closeWebSocket, [closeWebSocket]);

  const runWorkflow = useCallback(
    async ({ graphConfig, inputs, executionId }: WorkflowRunPayload) => {
      if (!workflowId) {
        throw new Error("Workflow identifier is required to run a workflow");
      }

      closeWebSocket();

      const runId = executionId ?? generateExecutionId();

      setState({
        status: "connecting",
        executionId: runId,
        error: null,
        messages: [],
        metrics: { ...DEFAULT_METRICS },
        startedAt: null,
        completedAt: null,
      });

      const websocketUrl = buildWorkflowWebSocketUrl(workflowId);
      const ws = createWebSocket(websocketUrl);
      websocketRef.current = ws;

      return await new Promise<string>((resolve, reject) => {
        const rejectWithError = (error: Error) => {
          closeWebSocket();
          const context: StreamContext | null = runId
            ? { executionId: runId }
            : null;
          options?.onError?.(error, context);
          setState((previous) => ({
            ...previous,
            status: "error",
            error: error.message,
            executionId: runId,
          }));
          reject(error);
        };

        ws.onopen = () => {
          setState({
            status: "streaming",
            executionId: runId,
            error: null,
            messages: [],
            metrics: { ...DEFAULT_METRICS },
            startedAt: new Date().toISOString(),
            completedAt: null,
          });

          const payload = {
            type: "run_workflow",
            graph_config: graphConfig,
            inputs,
            execution_id: runId,
          } satisfies Record<string, unknown>;

          ws.send(JSON.stringify(payload));
          resolve(runId);
        };

        ws.onerror = () => {
          rejectWithError(new Error("WebSocket connection error"));
        };

        ws.onclose = (event) => {
          if (event.code !== 1000) {
            const reason = event.reason || "WebSocket closed unexpectedly";
            rejectWithError(new Error(reason));
            return;
          }
          clearCompletionTimer();
          setState((previous) => {
            if (previous.status === "completed") {
              return previous;
            }
            return {
              ...previous,
              status: "completed",
              completedAt: previous.completedAt ?? new Date().toISOString(),
            };
          });
        };

        ws.onmessage = (event: MessageEvent<string>) => {
          try {
            const data = JSON.parse(event.data) as WorkflowStreamMessage;
            const timestamp = new Date().toISOString();
            setState((previous) => {
              const updatedMessages = [...previous.messages, data];
              const tokenUpdate = extractTokenCounts(data);
              const metrics = tokenUpdate
                ? mergeTokenMetrics(previous.metrics, tokenUpdate, timestamp)
                : previous.metrics;
              let status: RunnerState["status"] = previous.status;
              let completedAt = previous.completedAt;
              if (typeof data.status === "string") {
                const normalised = data.status.toLowerCase();
                if (["completed", "success"].includes(normalised)) {
                  status = "completed";
                  completedAt = timestamp;
                  completionTimeoutRef.current = setTimeout(() => {
                    closeWebSocket();
                    options?.onComplete?.({ executionId: runId });
                  }, 100);
                } else if (["error", "failed"].includes(normalised)) {
                  status = "error";
                  completedAt = timestamp;
                }
              }
              return {
                ...previous,
                messages: updatedMessages,
                metrics,
                status,
                completedAt,
              };
            });
            options?.onMessage?.(data, { executionId: runId });
          } catch (error) {
            console.error("Failed to parse workflow stream message", error);
          }
        };
      });
    },
    [clearCompletionTimer, closeWebSocket, options, workflowId],
  );

  const cancel = useCallback(() => {
    closeWebSocket();
    setState((previous) => ({
      ...previous,
      status: "idle",
      completedAt: new Date().toISOString(),
    }));
  }, [closeWebSocket]);

  return {
    status: state.status,
    executionId: state.executionId,
    error: state.error,
    messages: state.messages,
    metrics: state.metrics,
    startedAt: state.startedAt,
    completedAt: state.completedAt,
    runWorkflow,
    cancel,
  } as const;
};
