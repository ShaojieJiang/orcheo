import { buildBackendHttpUrl } from "@/lib/config";
import type {
  WorkflowExecution,
  WorkflowNode as HistoryWorkflowNode,
  WorkflowEdge as HistoryWorkflowEdge,
} from "@features/workflow/components/panels/workflow-execution-history";
import type {
  StoredWorkflow,
  WorkflowVersionRecord,
} from "@features/workflow/lib/workflow-storage";

interface RunHistoryStepResponse {
  index: number;
  at: string;
  payload: Record<string, unknown>;
}

interface RunHistoryResponse {
  execution_id: string;
  workflow_id: string;
  status: string;
  started_at: string;
  completed_at?: string | null;
  error?: string | null;
  inputs?: Record<string, unknown>;
  steps: RunHistoryStepResponse[];
}

type LogLevel = "INFO" | "DEBUG" | "ERROR" | "WARNING";
type NodeStatus = "idle" | "running" | "success" | "error" | "warning";

type SnapshotNode = StoredWorkflow["nodes"][number];
type SnapshotEdge = StoredWorkflow["edges"][number];

type WorkflowLookup = {
  defaultNodes: SnapshotNode[];
  defaultEdges: SnapshotEdge[];
  defaultMapping: Record<string, string>;
  versions: Map<string, WorkflowVersionRecord>;
};

const toExecutionStatus = (status: string): WorkflowExecution["status"] => {
  const normalised = status.toLowerCase();
  switch (normalised) {
    case "completed":
    case "success":
      return "success";
    case "error":
    case "failed":
      return "failed";
    case "cancelled":
    case "partial":
      return "partial";
    case "running":
    default:
      return "running";
  }
};

const toNodeStatus = (status: WorkflowExecution["status"]): NodeStatus => {
  switch (status) {
    case "running":
      return "running";
    case "failed":
      return "error";
    case "partial":
      return "warning";
    case "success":
    default:
      return "success";
  }
};

const determineLogLevel = (payload: Record<string, unknown>): LogLevel => {
  const explicit = payload.level ?? payload.log_level;
  if (typeof explicit === "string") {
    const level = explicit.trim().toLowerCase();
    if (level === "debug") {
      return "DEBUG";
    }
    if (level === "error") {
      return "ERROR";
    }
    if (level === "warning" || level === "warn") {
      return "WARNING";
    }
  }

  if (typeof payload.error === "string" && payload.error.trim()) {
    return "ERROR";
  }

  const status =
    typeof payload.status === "string" ? payload.status.toLowerCase() : null;
  if (status === "error" || status === "failed") {
    return "ERROR";
  }
  if (status === "warning" || status === "cancelled" || status === "partial") {
    return "WARNING";
  }
  if (status === "debug") {
    return "DEBUG";
  }
  return "INFO";
};

const resolveNodeLabel = (
  nodeId: string,
  nodes: Map<string, HistoryWorkflowNode>,
): string => nodes.get(nodeId)?.name ?? nodeId;

const describePayload = (
  payload: Record<string, unknown>,
  graphToCanvas: Record<string, string>,
  nodes: Map<string, HistoryWorkflowNode>,
): string => {
  if (typeof payload.error === "string" && payload.error.trim()) {
    return `Run error: ${payload.error.trim()}`;
  }

  if (typeof payload.message === "string" && payload.message.trim()) {
    return payload.message.trim();
  }

  const nodeKey = ["node", "step", "name"].find(
    (key) => typeof payload[key] === "string" && payload[key],
  );

  const status =
    typeof payload.status === "string"
      ? payload.status.toLowerCase()
      : undefined;

  if (nodeKey) {
    const graphNode = String(payload[nodeKey]);
    const canvasNodeId = graphToCanvas[graphNode] ?? graphNode;
    const label = resolveNodeLabel(canvasNodeId, nodes);
    if (status) {
      return `Node ${label} ${status}`;
    }
    return `Node ${label} emitted an update`;
  }

  if (status) {
    return `Run status changed to ${status}`;
  }

  try {
    return JSON.stringify(payload);
  } catch {
    return String(payload);
  }
};

const formatTimestamp = (isoString: string): string => {
  const date = new Date(isoString);
  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
};

const buildNodesFromSnapshot = (
  nodes: SnapshotNode[],
  status: WorkflowExecution["status"],
): HistoryWorkflowNode[] => {
  const resolvedStatus = toNodeStatus(status);
  return nodes.map((node) => ({
    id: node.id,
    type: node.type,
    name:
      typeof node.data?.label === "string" && node.data.label.trim()
        ? node.data.label
        : node.id,
    position: { ...node.position },
    status: resolvedStatus,
    iconKey:
      typeof node.data?.iconKey === "string" ? node.data.iconKey : undefined,
    details: node.data ? { ...node.data } : undefined,
  }));
};

const buildEdgesFromSnapshot = (edges: SnapshotEdge[]): HistoryWorkflowEdge[] =>
  edges.map((edge) => ({
    id: edge.id ?? `${edge.source}-${edge.target}`,
    source: edge.source,
    target: edge.target,
  }));

const computeIssues = (
  logs: WorkflowExecution["logs"],
  error: string | null | undefined,
): number => {
  const issueCount = logs.filter(
    (log) => log.level !== "INFO" && log.level !== "DEBUG",
  ).length;
  return error ? issueCount + 1 : issueCount;
};

const extractVersionRecord = (
  history: RunHistoryResponse,
  lookup: WorkflowLookup,
): WorkflowVersionRecord | undefined => {
  const inputs = history.inputs ?? {};
  const metadata = (inputs.metadata ?? inputs.canvas ?? {}) as Record<
    string,
    unknown
  >;
  const versionIdRaw = metadata?.workflow_version_id;
  if (typeof versionIdRaw === "string" && versionIdRaw) {
    return lookup.versions.get(versionIdRaw);
  }
  return undefined;
};

const mapHistoryToExecution = (
  history: RunHistoryResponse,
  lookup: WorkflowLookup,
): WorkflowExecution => {
  const status = toExecutionStatus(history.status);
  const version = extractVersionRecord(history, lookup);
  const snapshotNodes = version?.snapshot.nodes ?? lookup.defaultNodes;
  const snapshotEdges = version?.snapshot.edges ?? lookup.defaultEdges;
  const graphMapping = version?.graphToCanvas ?? lookup.defaultMapping;

  const nodes = buildNodesFromSnapshot(snapshotNodes, status);
  const nodeMap = new Map(nodes.map((node) => [node.id, node]));
  const edges = buildEdgesFromSnapshot(snapshotEdges);

  const logs = history.steps.map((step) => ({
    timestamp: formatTimestamp(step.at),
    level: determineLogLevel(step.payload),
    message: describePayload(step.payload, graphMapping, nodeMap),
  }));

  const startTime = history.started_at;
  const completedAt = history.completed_at ?? undefined;
  const start = new Date(startTime).getTime();
  const end = completedAt ? new Date(completedAt).getTime() : Date.now();
  const duration = Number.isFinite(start) ? Math.max(0, end - start) : 0;

  return {
    id: history.execution_id,
    runId: history.execution_id,
    status,
    startTime,
    endTime: completedAt,
    duration,
    issues: computeIssues(logs, history.error ?? undefined),
    nodes,
    edges,
    logs,
    metadata: { graphToCanvas: graphMapping },
  };
};

export interface LoadWorkflowExecutionsOptions {
  workflow?: StoredWorkflow;
  limit?: number;
  backendBaseUrl?: string;
}

export const loadWorkflowExecutions = async (
  workflowId: string,
  options: LoadWorkflowExecutionsOptions = {},
): Promise<WorkflowExecution[]> => {
  if (!workflowId) {
    return [];
  }
  if (typeof fetch === "undefined") {
    throw new Error("Fetch API is not available in this environment.");
  }

  const limit = options.limit ?? 50;
  const url = buildBackendHttpUrl(
    `/api/workflows/${workflowId}/executions?limit=${encodeURIComponent(String(limit))}`,
    options.backendBaseUrl,
  );

  const response = await fetch(url);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(
      detail || `Failed to load execution history (${response.status})`,
    );
  }

  const histories = (await response.json()) as RunHistoryResponse[];
  const workflow = options.workflow;
  const lookup: WorkflowLookup = {
    defaultNodes: workflow?.nodes ?? [],
    defaultEdges: workflow?.edges ?? [],
    defaultMapping: workflow?.versions?.at(-1)?.graphToCanvas ?? {},
    versions: new Map(
      (workflow?.versions ?? []).map((version) => [version.id, version]),
    ),
  };

  const executions = histories.map((history) =>
    mapHistoryToExecution(history, lookup),
  );

  return executions.sort(
    (a, b) => new Date(b.startTime).getTime() - new Date(a.startTime).getTime(),
  );
};
