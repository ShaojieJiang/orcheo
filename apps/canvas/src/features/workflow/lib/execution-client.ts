const DEFAULT_API_BASE = "http://localhost:8000/api";
const LANGGRAPH_SCRIPT_FORMAT = "langgraph_script";

const normaliseUrl = (value: string): string => value.replace(/\/+$/, "");

const resolveApiBase = () => {
  const envBase = import.meta.env.VITE_ORCHEO_API_BASE_URL;
  if (typeof envBase === "string" && envBase.trim().length > 0) {
    return normaliseUrl(envBase.trim());
  }
  return DEFAULT_API_BASE;
};

const resolveHttpHost = (apiBase: string): string => {
  const trimmed = normaliseUrl(apiBase);
  if (trimmed.endsWith("/api")) {
    return trimmed.slice(0, -4);
  }
  return trimmed;
};

const deriveWebSocketBase = (apiBase: string): string => {
  const envWs = import.meta.env.VITE_ORCHEO_WS_BASE_URL;
  if (typeof envWs === "string" && envWs.trim().length > 0) {
    return normaliseUrl(envWs.trim());
  }

  try {
    const httpHost = resolveHttpHost(apiBase);
    const url = new URL(httpHost);
    const protocol = url.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${url.host}/ws/workflow`;
  } catch (error) {
    console.warn("Failed to derive WebSocket base from API base", error);
    return "ws://localhost:8000/ws/workflow";
  }
};

export const API_BASE_URL = resolveApiBase();
export const WS_BASE_URL = deriveWebSocketBase(API_BASE_URL);

export const DEFAULT_LANGGRAPH_SOURCE = `from langgraph.graph import StateGraph


def greet_user(state):
    """Generate a greeting message based on the name in state."""
    name = state.get("name", "there")
    return {"greeting": f"Hello {name}!"}


def format_message(state):
    """Convert greeting message to uppercase."""
    greeting = state.get("greeting", "")
    return {"shout": greeting.upper()}


def build_graph():
    """Build and return the LangGraph workflow."""
    graph = StateGraph(dict)
    graph.add_node("greet_user", greet_user)
    graph.add_node("format_message", format_message)
    graph.add_edge("greet_user", "format_message")
    graph.set_entry_point("greet_user")
    graph.set_finish_point("format_message")
    return graph`.trim();

export const DEFAULT_LANGGRAPH_GRAPH_CONFIG = {
  format: LANGGRAPH_SCRIPT_FORMAT,
  source: DEFAULT_LANGGRAPH_SOURCE,
  entrypoint: "build_graph",
} satisfies Record<string, unknown>;

export interface ExecutionTokens {
  prompt: number;
  completion: number;
  total: number;
}

export interface ExecutionMetrics {
  tokens?: ExecutionTokens;
  [key: string]: unknown;
}

export interface ExecutionMessage {
  status?: string;
  node?: string;
  event?: string;
  payload?: Record<string, unknown>;
  data?: Record<string, unknown>;
  metrics?: ExecutionMetrics;
  [key: string]: unknown;
}

export interface RunHistoryStepResponse {
  index: number;
  at: string;
  payload: Record<string, unknown>;
}

export interface RunHistoryResponse {
  execution_id: string;
  workflow_id: string;
  status: string;
  started_at: string;
  completed_at?: string | null;
  error?: string | null;
  inputs: Record<string, unknown>;
  steps: RunHistoryStepResponse[];
}

const buildApiUrl = (path: string): string => `${API_BASE_URL}${path}`;

export const getWorkflowWebSocketUrl = (workflowId: string): string => {
  const sanitized = encodeURIComponent(workflowId.trim());
  return `${WS_BASE_URL}/${sanitized}`;
};

export const getBackendWorkflowId = (): string | null => {
  const value = import.meta.env.VITE_ORCHEO_BACKEND_WORKFLOW_ID;
  if (typeof value === "string" && value.trim().length > 0) {
    return value.trim();
  }
  return null;
};

const handleResponse = async <T>(response: Response): Promise<T> => {
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(
      `Request failed with status ${response.status}${text ? `: ${text}` : ""}`,
    );
  }
  return response.json() as Promise<T>;
};

export const fetchExecutionHistory = async (
  executionId: string,
): Promise<RunHistoryResponse> => {
  if (!executionId.trim()) {
    throw new Error("Execution ID is required to fetch history.");
  }

  if (typeof fetch === "undefined") {
    throw new Error("Fetch API is not available in this environment.");
  }

  const url = buildApiUrl(
    `/executions/${encodeURIComponent(executionId)}/history`,
  );
  const response = await fetch(url, { method: "GET" });
  return handleResponse<RunHistoryResponse>(response);
};

interface RunReplayRequestPayload {
  from_step: number;
}

export const replayExecution = async (
  executionId: string,
  fromStep: number,
): Promise<RunHistoryResponse> => {
  if (!executionId.trim()) {
    throw new Error("Execution ID is required to replay history.");
  }

  if (typeof fetch === "undefined") {
    throw new Error("Fetch API is not available in this environment.");
  }

  const payload: RunReplayRequestPayload = { from_step: fromStep };
  const response = await fetch(
    buildApiUrl(`/executions/${encodeURIComponent(executionId)}/replay`),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  return handleResponse<RunHistoryResponse>(response);
};

export type { ExecutionMessage as BackendExecutionMessage };
