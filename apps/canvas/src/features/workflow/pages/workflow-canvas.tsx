import React, {
  useState,
  useCallback,
  useRef,
  useEffect,
  useLayoutEffect,
  useMemo,
} from "react";
import { useNavigate, useParams } from "react-router-dom";
import type {
  Connection,
  Edge,
  EdgeChange,
  Node,
  NodeChange,
  ReactFlowInstance,
} from "@xyflow/react";
import {
  Panel,
  addEdge,
  useNodesState,
  useEdgesState,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { Button } from "@/design-system/ui/button";
import { Tabs, TabsContent } from "@/design-system/ui/tabs";
import { Separator } from "@/design-system/ui/separator";
import {
  buildBackendHttpUrl,
  buildWorkflowWebSocketUrl,
  getBackendBaseUrl,
} from "@/lib/config";

import TopNavigation from "@features/shared/components/top-navigation";
import SidebarPanel from "@features/workflow/components/panels/sidebar-panel";
import WorkflowControls from "@features/workflow/components/canvas/workflow-controls";
import WorkflowSearch from "@features/workflow/components/canvas/workflow-search";
import { EdgeHoverContext } from "@features/workflow/components/canvas/edge-hover-context";
import type {
  StickyNoteColor,
  StickyNoteNodeData,
} from "@features/workflow/components/nodes/sticky-note-node";
import NodeInspector, {
  type NodeRuntimeCacheEntry,
} from "@features/workflow/components/panels/node-inspector";
import ChatInterface from "@features/shared/components/chat-interface";
import WorkflowFlow from "@features/workflow/components/canvas/workflow-flow";
import WorkflowExecutionHistory, {
  type WorkflowExecution as HistoryWorkflowExecution,
} from "@features/workflow/components/panels/workflow-execution-history";
import WorkflowTabs from "@features/workflow/components/panels/workflow-tabs";
import WorkflowHistory from "@features/workflow/components/panels/workflow-history";
import { loadWorkflowExecutions } from "@features/workflow/lib/workflow-execution-storage";
import ConnectionValidator, {
  validateConnection,
  validateNodeCredentials,
  type ValidationError,
} from "@features/workflow/components/canvas/connection-validator";
import WorkflowGovernancePanel, {
  type SubworkflowTemplate,
} from "@features/workflow/components/panels/workflow-governance-panel";
import {
  SAMPLE_WORKFLOWS,
  type WorkflowEdge as PersistedWorkflowEdge,
  type WorkflowNode as PersistedWorkflowNode,
} from "@features/workflow/data/workflow-data";
import {
  getVersionSnapshot,
  getWorkflowById,
  saveWorkflow as persistWorkflow,
  type StoredWorkflow,
  WORKFLOW_STORAGE_EVENT,
} from "@features/workflow/lib/workflow-storage";
import { toast } from "@/hooks/use-toast";
import type {
  Credential,
  CredentialInput,
  CredentialVaultEntryResponse,
} from "@features/workflow/types/credential-vault";
import { buildGraphConfigFromCanvas } from "@features/workflow/lib/graph-config";
import {
  getNodeIcon,
  inferNodeIconKey,
} from "@features/workflow/lib/node-icons";
import {
  DEFAULT_STICKY_NOTE_COLOR,
  DEFAULT_STICKY_NOTE_HEIGHT,
  DEFAULT_STICKY_NOTE_WIDTH,
  STICKY_NOTE_MIN_HEIGHT,
  STICKY_NOTE_MIN_WIDTH,
  defaultNodeStyle,
  clampStickyDimension,
  generateNodeId,
  generateRandomId,
  isStickyNoteColor,
  sanitizeStickyNoteContent,
  sanitizeStickyNoteDimension,
} from "./workflow-canvas/utils";
import {
  clearRuntimeCacheFromSession,
  getRuntimeCacheStorageKey,
  persistRuntimeCacheToSession,
  readRuntimeCacheFromSession,
} from "./workflow-canvas/runtime-cache";
import { SUBWORKFLOW_LIBRARY } from "./workflow-canvas/subworkflow-library";

interface NodeRuntimeData {
  inputs?: unknown;
  outputs?: unknown;
  messages?: unknown;
  raw?: unknown;
  updatedAt: string;
}

interface NodeData {
  type: string;
  label: string;
  description?: string;
  status: "idle" | "running" | "success" | "error" | "warning";
  iconKey?: string;
  icon?: React.ReactNode;
  onOpenChat?: () => void;
  onDelete?: (id: string) => void;
  isDisabled?: boolean;
  runtime?: NodeRuntimeData;
  code?: string;
  [key: string]: unknown;
}

type CanvasNode = Node<NodeData>;
type CanvasEdge = Edge<Record<string, unknown>>;

const PERSISTED_NODE_FIELDS = new Set([
  "label",
  "description",
  "type",
  "isDisabled",
]);

const DEFAULT_NODE_LABEL = "New Node";

const normaliseLabelInput = (value: unknown): string => {
  if (typeof value !== "string") {
    return "";
  }
  return value.trim();
};

const sanitizeLabel = (
  value: unknown,
  fallback = DEFAULT_NODE_LABEL,
): string => {
  const normalised = normaliseLabelInput(value);
  return normalised.length > 0 ? normalised : fallback;
};

const slugifyLabel = (label: string): string => {
  return label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
};

const buildExistingNameSet = (
  nodes: CanvasNode[],
  excludeId?: string,
): Set<string> => {
  const names = new Set<string>();
  for (const node of nodes) {
    if (excludeId && node.id === excludeId) {
      continue;
    }
    const label = sanitizeLabel(
      (node.data?.label as string) ?? node.id ?? DEFAULT_NODE_LABEL,
    );
    names.add(label.toLowerCase());
  }
  return names;
};

const buildExistingIdSet = (
  nodes: CanvasNode[],
  excludeId?: string,
): Set<string> => {
  const ids = new Set<string>();
  for (const node of nodes) {
    if (excludeId && node.id === excludeId) {
      continue;
    }
    ids.add(node.id);
  }
  return ids;
};

const assignUniqueIdentity = (
  desiredLabel: string,
  nameSet: Set<string>,
  idSet: Set<string>,
) => {
  const baseLabel = sanitizeLabel(desiredLabel);
  let candidateLabel = baseLabel;
  let attempt = 2;
  while (nameSet.has(candidateLabel.toLowerCase())) {
    candidateLabel = `${baseLabel} (${attempt})`;
    attempt += 1;
  }
  nameSet.add(candidateLabel.toLowerCase());

  const baseSlug = slugifyLabel(candidateLabel) || "node";
  let candidateId = baseSlug;
  attempt = 2;
  while (idSet.has(candidateId)) {
    candidateId = `${baseSlug}-${attempt}`;
    attempt += 1;
  }
  idSet.add(candidateId);

  return { id: candidateId, label: candidateLabel };
};

const createIdentityAllocator = (
  nodes: CanvasNode[],
  options: { excludeId?: string } = {},
) => {
  const nameSet = buildExistingNameSet(nodes, options.excludeId);
  const idSet = buildExistingIdSet(nodes, options.excludeId);
  return (desiredLabel: string) =>
    assignUniqueIdentity(desiredLabel, nameSet, idSet);
};

const sanitizeNodeDataForPersist = (
  data?: NodeData,
): PersistedWorkflowNode["data"] => {
  const sanitized: PersistedWorkflowNode["data"] = {
    label:
      typeof data?.label === "string"
        ? data.label
        : data?.label !== undefined
          ? String(data.label)
          : "New Node",
  };

  if (typeof data?.description === "string") {
    sanitized.description = data.description;
  }

  if (typeof data?.type === "string") {
    sanitized.type = data.type;
  }

  if (typeof data?.isDisabled === "boolean") {
    sanitized.isDisabled = data.isDisabled;
  }

  Object.entries(data ?? {}).forEach(([key, value]) => {
    if (
      PERSISTED_NODE_FIELDS.has(key) ||
      key === "onOpenChat" ||
      key === "icon" ||
      key === "runtime" ||
      key === "status"
    ) {
      return;
    }

    if (
      value === null ||
      typeof value === "string" ||
      typeof value === "number" ||
      typeof value === "boolean"
    ) {
      sanitized[key] = value;
      return;
    }

    if (Array.isArray(value)) {
      sanitized[key] = value;
      return;
    }

    if (
      typeof value === "object" &&
      value !== null &&
      !(value as { $$typeof?: unknown }).$$typeof
    ) {
      sanitized[key] = value;
    }
  });

  return sanitized;
};

const toPersistedNode = (node: CanvasNode): PersistedWorkflowNode => ({
  id: node.id,
  type:
    typeof node.data?.type === "string"
      ? node.data.type
      : (node.type ?? "default"),
  position: {
    x: node.position?.x ?? 0,
    y: node.position?.y ?? 0,
  },
  data: sanitizeNodeDataForPersist(node.data),
});

const toPersistedEdge = (edge: CanvasEdge): PersistedWorkflowEdge => ({
  id: edge.id,
  source: edge.source,
  target: edge.target,
  sourceHandle: edge.sourceHandle,
  targetHandle: edge.targetHandle,
  label: edge.label,
  type: edge.type,
  animated: edge.animated,
  style: edge.style,
});

const resolveReactFlowType = (
  persistedType?: string,
): "default" | "chatTrigger" | "startEnd" | "stickyNote" => {
  if (!persistedType) {
    return "default";
  }

  if (persistedType === "chatTrigger") {
    return "chatTrigger";
  }

  if (persistedType === "stickyNote" || persistedType === "annotation") {
    return "stickyNote";
  }

  if (
    persistedType === "start" ||
    persistedType === "end" ||
    persistedType === "startEnd"
  ) {
    return "startEnd";
  }

  return "default";
};

const toCanvasNodeBase = (node: PersistedWorkflowNode): CanvasNode => {
  const extraEntries = Object.entries(node.data ?? {}).filter(
    ([key]) => !PERSISTED_NODE_FIELDS.has(key),
  );

  const extraData = Object.fromEntries(extraEntries);
  const semanticType = node.data?.type ?? node.type ?? "default";
  const extraDataRecord = { ...extraData } as Record<string, unknown>;
  const storedIconKeyRaw = extraDataRecord.iconKey;
  delete extraDataRecord.iconKey;
  delete extraDataRecord.icon;
  const otherExtraData = extraDataRecord;

  const label =
    typeof node.data?.label === "string" ? node.data.label : "New Node";
  const description =
    typeof node.data?.description === "string" ? node.data.description : "";

  const storedIconKey =
    typeof storedIconKeyRaw === "string" ? storedIconKeyRaw : undefined;
  const resolvedIconKey =
    inferNodeIconKey({
      iconKey: storedIconKey,
      label,
      type: semanticType,
    }) ?? storedIconKey;
  const icon = getNodeIcon(resolvedIconKey);

  return {
    id: node.id,
    type: resolveReactFlowType(node.type),
    position: node.position ?? { x: 0, y: 0 },
    style: defaultNodeStyle,
    data: {
      type: semanticType,
      label,
      description,
      status: (node.data?.status ?? "idle") as NodeStatus,
      isDisabled: node.data?.isDisabled,
      iconKey: resolvedIconKey,
      icon,
      ...otherExtraData,
    } as NodeData,
    draggable: true,
  };
};

const toCanvasEdge = (edge: PersistedWorkflowEdge): CanvasEdge => ({
  id: edge.id ?? `edge-${edge.source}-${edge.target}`,
  source: edge.source,
  target: edge.target,
  sourceHandle: edge.sourceHandle,
  targetHandle: edge.targetHandle,
  label: edge.label,
  type: edge.type ?? "default",
  animated: edge.animated ?? false,
  markerEnd: {
    type: MarkerType.ArrowClosed,
    width: 12,
    height: 12,
  },
  style: edge.style ?? { stroke: "#99a1b3", strokeWidth: 2 },
});

const convertPersistedEdgesToCanvas = (edges: PersistedWorkflowEdge[]) =>
  edges.map(toCanvasEdge);

interface WorkflowSnapshot {
  nodes: CanvasNode[];
  edges: CanvasEdge[];
}

interface WorkflowCanvasProps {
  initialNodes?: CanvasNode[];
  initialEdges?: CanvasEdge[];
}

const HISTORY_LIMIT = 50;

const WORKFLOW_CLIPBOARD_HEADER = "ORCHEO_WORKFLOW_CLIPBOARD_V1:";
const PASTE_BASE_OFFSET = 40;
const PASTE_OFFSET_INCREMENT = 24;
const PASTE_OFFSET_MAX_STEPS = 5;

type WorkflowClipboardPayload = {
  version: 1;
  type: "workflow-selection";
  nodes: PersistedWorkflowNode[];
  edges: PersistedWorkflowEdge[];
  copiedAt?: number;
};

type CopyClipboardOptions = {
  skipSuccessToast?: boolean;
};

type CopyClipboardResult = {
  success: boolean;
  nodeCount: number;
  edgeCount: number;
  usedFallback: boolean;
};

const encodeClipboardPayload = (payload: WorkflowClipboardPayload) =>
  `${WORKFLOW_CLIPBOARD_HEADER}${JSON.stringify(payload)}`;

const decodeClipboardPayloadString = (
  serialized: string,
): WorkflowClipboardPayload | null => {
  if (typeof serialized !== "string") {
    return null;
  }
  const trimmed = serialized.trim();
  if (trimmed.length === 0) {
    return null;
  }

  const payloadString = trimmed.startsWith(WORKFLOW_CLIPBOARD_HEADER)
    ? trimmed.slice(WORKFLOW_CLIPBOARD_HEADER.length)
    : trimmed;

  try {
    const parsed = JSON.parse(
      payloadString,
    ) as Partial<WorkflowClipboardPayload>;
    if (
      parsed &&
      parsed.version === 1 &&
      parsed.type === "workflow-selection" &&
      Array.isArray(parsed.nodes) &&
      Array.isArray(parsed.edges)
    ) {
      return {
        version: 1,
        type: "workflow-selection",
        nodes: parsed.nodes as PersistedWorkflowNode[],
        edges: parsed.edges as PersistedWorkflowEdge[],
        copiedAt:
          typeof parsed.copiedAt === "number" ? parsed.copiedAt : undefined,
      };
    }
  } catch {
    return null;
  }

  return null;
};

const buildClipboardPayload = (
  nodesToPersist: PersistedWorkflowNode[],
  edgesToPersist: PersistedWorkflowEdge[],
): WorkflowClipboardPayload => ({
  version: 1,
  type: "workflow-selection",
  nodes: nodesToPersist,
  edges: edgesToPersist,
  copiedAt: Date.now(),
});

const signatureFromClipboardPayload = (payload: WorkflowClipboardPayload) =>
  typeof payload.copiedAt === "number"
    ? `ts:${payload.copiedAt}`
    : `ids:${payload.nodes
        .map((node) => node.id)
        .sort()
        .join("|")}`;

const cloneNode = (node: CanvasNode): CanvasNode => ({
  ...node,
  position: node.position ? { ...node.position } : node.position,
  data: node.data ? { ...node.data } : node.data,
});

const cloneEdge = (edge: CanvasEdge): CanvasEdge => ({
  ...edge,
  data: edge.data ? { ...edge.data } : edge.data,
});

// Update the WorkflowExecution interface to match the component's expectations
type WorkflowExecutionStatus = "running" | "success" | "failed" | "partial";
type NodeStatus = "idle" | "running" | "success" | "error" | "warning";

interface WorkflowExecutionNode {
  id: string;
  type: string;
  name: string;
  position: { x: number; y: number };
  status: NodeStatus;
  iconKey?: string;
  details?: Record<string, unknown>;
}

interface WorkflowExecution {
  id: string;
  runId: string;
  status: WorkflowExecutionStatus;
  startTime: string;
  endTime?: string;
  duration: number;
  issues: number;
  nodes: WorkflowExecutionNode[];
  edges: WorkflowEdge[];
  logs: {
    timestamp: string;
    level: "INFO" | "DEBUG" | "ERROR" | "WARNING";
    message: string;
  }[];
  metadata?: {
    graphToCanvas?: Record<string, string>;
  };
}

interface RunHistoryStep {
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
  steps: RunHistoryStep[];
}

const nodeStatusFromValue = (value?: string): NodeStatus => {
  const normalised = value?.toLowerCase();
  switch (normalised) {
    case "running":
      return "running";
    case "error":
    case "failed":
      return "error";
    case "warning":
    case "cancelled":
    case "partial":
      return "warning";
    default:
      return "success";
  }
};

const executionStatusFromValue = (
  value?: string,
): WorkflowExecutionStatus | null => {
  const normalised = value?.toLowerCase();
  switch (normalised) {
    case "running":
      return "running";
    case "completed":
    case "success":
      return "success";
    case "error":
    case "failed":
      return "failed";
    case "cancelled":
    case "partial":
      return "partial";
    default:
      return null;
  }
};

interface SidebarNodeDefinition {
  id?: string;
  type?: string;
  name?: string;
  description?: string;
  iconKey?: string;
  icon?: React.ReactNode;
  data?: Record<string, unknown>;
}

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return typeof value === "object" && value !== null;
};

const determineNodeType = (nodeId?: string) => {
  if (nodeId?.includes("chat-trigger")) {
    return "chatTrigger" as const;
  }
  if (nodeId === "sticky-note") {
    return "stickyNote" as const;
  }
  if (nodeId === "start-node" || nodeId === "end-node") {
    return "startEnd" as const;
  }
  return "default" as const;
};

const validateWorkflowData = (data: unknown) => {
  if (!isRecord(data)) {
    throw new Error("Invalid workflow file structure.");
  }

  const { nodes, edges } = data;

  if (!Array.isArray(nodes)) {
    throw new Error("Invalid nodes array in workflow file.");
  }

  nodes.forEach((node, index) => {
    if (!isRecord(node)) {
      throw new Error(`Invalid node at index ${index}.`);
    }
    if (!isRecord(node.position)) {
      throw new Error(`Node ${node.id ?? index} is missing position data.`);
    }
    const { x, y } = node.position as Record<string, unknown>;
    if (typeof x !== "number" || typeof y !== "number") {
      throw new Error(`Node ${node.id ?? index} has invalid coordinates.`);
    }
  });

  if (!Array.isArray(edges)) {
    throw new Error("Invalid edges array in workflow file.");
  }

  edges.forEach((edge, index) => {
    if (!isRecord(edge)) {
      throw new Error(`Invalid edge at index ${index}.`);
    }
    if (typeof edge.source !== "string" || typeof edge.target !== "string") {
      throw new Error(`Edge ${edge.id ?? index} has invalid connections.`);
    }
  });
};

export default function WorkflowCanvas({
  initialNodes = [],
  initialEdges = [],
}: WorkflowCanvasProps) {
  const { workflowId } = useParams<{ workflowId?: string }>();
  const navigate = useNavigate();

  // Initialize with empty arrays instead of sample workflow
  const [nodes, setNodesState, onNodesChangeState] =
    useNodesState<CanvasNode>(initialNodes);
  const [edges, setEdgesState, onEdgesChangeState] =
    useEdgesState<CanvasEdge>(initialEdges);
  const [workflowName, setWorkflowName] = useState("New Workflow");
  const [workflowDescription, setWorkflowDescription] = useState("");
  const [currentWorkflowId, setCurrentWorkflowId] = useState<string | null>(
    workflowId ?? null,
  );
  const [workflowVersions, setWorkflowVersions] = useState<
    StoredWorkflow["versions"]
  >([]);
  const [workflowTags, setWorkflowTags] = useState<string[]>(["draft"]);
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [isCredentialsLoading, setIsCredentialsLoading] = useState(true);
  const [subworkflows, setSubworkflows] = useState<SubworkflowTemplate[]>([
    {
      id: "subflow-customer-onboarding",
      name: "Customer Onboarding Foundation",
      description:
        "Qualify leads, enrich CRM details, and orchestrate the welcome sequence.",
      tags: ["crm", "sales", "email"],
      version: "1.3.0",
      status: "stable",
      usageCount: 18,
      lastUpdated: new Date(Date.now() - 1000 * 60 * 60 * 24 * 2).toISOString(),
    },
    {
      id: "subflow-incident-response",
      name: "Incident Response Escalation",
      description:
        "Route Sev1 incidents, notify stakeholders, and collect on-call context.",
      tags: ["ops", "pagerduty", "slack"],
      version: "0.9.2",
      status: "beta",
      usageCount: 7,
      lastUpdated: new Date(Date.now() - 1000 * 60 * 60 * 8).toISOString(),
    },
    {
      id: "subflow-content-qa",
      name: "Content QA & Publishing",
      description:
        "Score AI-generated drafts, request revisions, and schedule approved posts.",
      tags: ["marketing", "ai", "review"],
      version: "2.0.0",
      status: "stable",
      usageCount: 11,
      lastUpdated: new Date(Date.now() - 1000 * 60 * 60 * 24 * 6).toISOString(),
    },
  ]);
  const [validationErrors, setValidationErrors] = useState<ValidationError[]>(
    [],
  );
  const [isValidating, setIsValidating] = useState(false);
  const [lastValidationRun, setLastValidationRun] = useState<string | null>(
    null,
  );
  const [executions, setExecutions] = useState<WorkflowExecution[]>([]);
  const [activeExecutionId, setActiveExecutionId] = useState<string | null>(
    null,
  );
  const websocketRef = useRef<WebSocket | null>(null);
  const isMountedRef = useRef(true);
  const latestNodesRef = useRef(nodes);
  const runtimeCacheKey = getRuntimeCacheStorageKey(workflowId ?? null);
  const [nodeRuntimeCache, setNodeRuntimeCache] = useState<
    Record<string, NodeRuntimeCacheEntry>
  >(() => readRuntimeCacheFromSession(runtimeCacheKey));
  const previousRuntimeCacheKeyRef = useRef(runtimeCacheKey);

  useEffect(() => {
    const controller = new AbortController();
    let isActive = true;

    const fetchCredentials = async () => {
      if (!isActive) {
        return;
      }

      setIsCredentialsLoading(true);
      try {
        const url = new URL(buildBackendHttpUrl("/api/credentials"));
        if (workflowId) {
          url.searchParams.set("workflow_id", workflowId);
        }

        const response = await fetch(url.toString(), {
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(
            `Failed to load credentials (status ${response.status})`,
          );
        }

        const payload =
          (await response.json()) as CredentialVaultEntryResponse[];

        if (!isActive) {
          return;
        }

        const mapped = payload.map<Credential>((entry) => ({
          id: entry.id,
          name: entry.name,
          type: entry.provider ?? entry.kind,
          createdAt: entry.created_at,
          updatedAt: entry.updated_at,
          owner: entry.owner ?? null,
          access: entry.access,
          secrets: entry.secret_preview
            ? { secret: entry.secret_preview }
            : undefined,
          status: entry.status,
        }));

        setCredentials((previous) => {
          const remoteIds = new Set(mapped.map((item) => item.id));
          const localOnly = previous.filter((item) => !remoteIds.has(item.id));
          return [...mapped, ...localOnly];
        });
      } catch (error) {
        if (controller.signal.aborted) {
          return;
        }

        console.error("Failed to load credential vault", error);
        toast({
          title: "Unable to load credentials",
          description:
            error instanceof Error
              ? error.message
              : "An unexpected error occurred while loading credentials.",
          variant: "destructive",
        });
      } finally {
        if (isActive) {
          setIsCredentialsLoading(false);
        }
      }
    };

    fetchCredentials();

    return () => {
      isActive = false;
      controller.abort();
    };
  }, [workflowId]);

  // State for UI controls
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("canvas");
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [searchMatches, setSearchMatches] = useState<string[]>([]);
  const [currentSearchIndex, setCurrentSearchIndex] = useState(0);
  const [hoveredEdgeId, setHoveredEdgeId] = useState<string | null>(null);
  const selectedNode = useMemo(() => {
    if (!selectedNodeId) {
      return null;
    }
    return nodes.find((node) => node.id === selectedNodeId) ?? null;
  }, [nodes, selectedNodeId]);

  // Chat interface state
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [activeChatNodeId, setActiveChatNodeId] = useState<string | null>(null);
  const [chatTitle, setChatTitle] = useState("Chat");
  const backendBaseUrl = getBackendBaseUrl();
  const user = useMemo(
    () => ({
      id: "user-1",
      name: "Avery Chen",
      avatar: "https://avatar.vercel.sh/avery",
    }),
    [],
  );
  const ai = useMemo(
    () => ({
      id: "ai-1",
      name: "Orcheo Canvas Assistant",
      avatar: "https://avatar.vercel.sh/orcheo-canvas",
    }),
    [],
  );
  const setHoveredEdgeIdValue = useCallback(
    (edgeId: string | null) => {
      setHoveredEdgeId(edgeId);
    },
    [setHoveredEdgeId],
  );
  const edgeHoverContextValue = useMemo(
    () => ({
      hoveredEdgeId,
      setHoveredEdgeId: setHoveredEdgeIdValue,
    }),
    [hoveredEdgeId, setHoveredEdgeIdValue],
  );

  useEffect(() => {
    setActiveExecutionId((current) => {
      if (executions.length === 0) {
        return null;
      }
      if (current && executions.some((execution) => execution.id === current)) {
        return current;
      }
      return executions[0]?.id ?? null;
    });
  }, [executions]);

  const undoStackRef = useRef<WorkflowSnapshot[]>([]);
  const redoStackRef = useRef<WorkflowSnapshot[]>([]);
  const isRestoringRef = useRef(false);
  const nodesRef = useRef<CanvasNode[]>(nodes);
  const edgesRef = useRef<CanvasEdge[]>(edges);
  const clipboardRef = useRef<WorkflowClipboardPayload | null>(null);
  const pasteOffsetStepRef = useRef(0);
  const lastClipboardSignatureRef = useRef<string | null>(null);

  useEffect(() => {
    latestNodesRef.current = nodes;
  }, [nodes]);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      if (websocketRef.current) {
        websocketRef.current.close();
        websocketRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (previousRuntimeCacheKeyRef.current !== runtimeCacheKey) {
      clearRuntimeCacheFromSession(previousRuntimeCacheKeyRef.current);
      previousRuntimeCacheKeyRef.current = runtimeCacheKey;
      setNodeRuntimeCache(readRuntimeCacheFromSession(runtimeCacheKey));
    }
  }, [runtimeCacheKey]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const handle = window.setTimeout(() => {
      persistRuntimeCacheToSession(runtimeCacheKey, nodeRuntimeCache);
    }, 200);

    return () => {
      window.clearTimeout(handle);
    };
  }, [nodeRuntimeCache, runtimeCacheKey]);

  useEffect(() => {
    return () => {
      clearRuntimeCacheFromSession(runtimeCacheKey);
    };
  }, [runtimeCacheKey]);

  const handleAddCredential = useCallback(
    async (credential: CredentialInput) => {
      const secret = credential.secrets?.apiKey?.trim();
      if (!secret) {
        const message = "API key is required to save a credential.";
        toast({
          title: "Missing credential secret",
          description: message,
          variant: "destructive",
        });
        throw new Error(message);
      }

      const response = await fetch(
        buildBackendHttpUrl("/api/credentials", backendBaseUrl),
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            name: credential.name,
            provider: credential.type ?? "custom", // default provider label
            secret,
            actor: user.name,
            access: credential.access,
            workflow_id: currentWorkflowId,
            scopes: [],
          }),
        },
      );

      if (!response.ok) {
        let detail = `Failed to save credential (status ${response.status})`;
        try {
          const payload = (await response.json()) as { detail?: unknown };
          if (typeof payload?.detail === "string") {
            detail = payload.detail;
          } else if (
            payload?.detail &&
            typeof (payload.detail as { message?: unknown }).message ===
              "string"
          ) {
            detail = (payload.detail as { message?: string }).message as string;
          }
        } catch (error) {
          console.warn("Failed to parse credential creation error", error);
        }

        toast({
          title: "Unable to save credential",
          description: detail,
          variant: "destructive",
        });
        throw new Error(detail);
      }

      const payload = (await response.json()) as CredentialVaultEntryResponse;

      const credentialRecord: Credential = {
        id: payload.id,
        name: payload.name,
        type: payload.provider ?? payload.kind,
        createdAt: payload.created_at,
        updatedAt: payload.updated_at,
        owner: payload.owner,
        access: payload.access,
        secrets: credential.secrets,
        status: payload.status,
      };

      setCredentials((prev) => {
        const withoutDuplicate = prev.filter(
          (existing) => existing.id !== credentialRecord.id,
        );
        return [...withoutDuplicate, credentialRecord];
      });

      toast({
        title: "Credential added to vault",
        description: `${credentialRecord.name} is now available for nodes that require secure access.`,
      });
    },
    [backendBaseUrl, currentWorkflowId, user.name],
  );

  const handleDeleteCredential = useCallback(
    async (id: string) => {
      const url = new URL(
        buildBackendHttpUrl(`/api/credentials/${id}`, backendBaseUrl),
      );
      if (currentWorkflowId) {
        url.searchParams.set("workflow_id", currentWorkflowId);
      }

      try {
        const response = await fetch(url.toString(), {
          method: "DELETE",
        });

        if (!response.ok && response.status !== 404) {
          throw new Error(
            `Failed to delete credential (status ${response.status})`,
          );
        }

        setCredentials((prev) =>
          prev.filter((credential) => credential.id !== id),
        );
        toast({
          title: "Credential removed",
          description:
            "Nodes referencing this credential will require reconfiguration before publish.",
        });
      } catch (error) {
        console.error("Failed to delete credential", error);
        const message =
          error instanceof Error ? error.message : "Credential removal failed.";
        toast({
          title: "Unable to delete credential",
          description: message,
          variant: "destructive",
        });
        return;
      }
    },
    [backendBaseUrl, currentWorkflowId],
  );

  const handleCreateSubworkflow = useCallback(() => {
    const selectedNodes = nodes.filter((node) => node.selected);
    const timestamp = new Date().toISOString();
    const inferredTags = Array.from(
      new Set(
        selectedNodes
          .map((node) =>
            typeof node.data.type === "string" ? node.data.type : "workflow",
          )
          .filter(Boolean),
      ),
    ).slice(0, 4);

    const template: SubworkflowTemplate = {
      id: generateRandomId("subflow"),
      name:
        selectedNodes.length > 0
          ? `${selectedNodes.length}-step sub-workflow`
          : "Draft sub-workflow",
      description:
        selectedNodes.length > 0
          ? "Captured the selected nodes so the pattern can be reused across projects."
          : "Start from an empty template and drag nodes into the canvas to define the steps.",
      tags: inferredTags.length > 0 ? inferredTags : ["workflow"],
      version: "0.1.0",
      status: "beta",
      usageCount: 0,
      lastUpdated: timestamp,
    };

    setSubworkflows((prev) => [template, ...prev]);
    toast({
      title: "Sub-workflow draft created",
      description:
        "Find it in the Readiness tab to document, version, and share with your team.",
    });
  }, [nodes]);

  const handleDeleteSubworkflow = useCallback((id: string) => {
    setSubworkflows((prev) =>
      prev.filter((subworkflow) => subworkflow.id !== id),
    );
    toast({
      title: "Sub-workflow removed",
      description:
        "It will remain available in version history for audit purposes.",
    });
  }, []);

  const runPublishValidation = useCallback(() => {
    setIsValidating(true);

    window.setTimeout(() => {
      const normalizedNodes = nodes.map((node) => ({
        ...node,
        data: {
          ...node.data,
          label:
            typeof node.data.label === "string"
              ? node.data.label
              : ((node.data as { label?: unknown; name?: unknown }).label ??
                (node.data as { name?: unknown }).name ??
                node.id),
          credentials:
            (node.data as { credentials?: { id?: string } | null })
              .credentials ?? null,
        },
      }));

      const evaluatedEdges: Edge<Record<string, unknown>>[] = [];
      const connectionErrors = edges
        .map((edge) => {
          const error = validateConnection(
            {
              source: edge.source,
              target: edge.target,
              sourceHandle: edge.sourceHandle ?? null,
              targetHandle: edge.targetHandle ?? null,
            } as Connection,
            normalizedNodes as unknown as Node<{
              type?: string;
              label?: string;
              credentials?: { id?: string } | null;
            }>[],
            evaluatedEdges,
          );

          evaluatedEdges.push(edge as Edge<Record<string, unknown>>);

          return error;
        })
        .filter((error): error is ValidationError => Boolean(error));

      const credentialErrors = normalizedNodes
        .map((node) =>
          validateNodeCredentials(
            node as unknown as Node<{
              type?: string;
              label?: string;
              credentials?: { id?: string } | null;
            }>,
          ),
        )
        .filter((error): error is ValidationError => Boolean(error));

      const readinessErrors = [...connectionErrors, ...credentialErrors];

      if (nodes.length === 0) {
        readinessErrors.push({
          id: generateRandomId("validation"),
          type: "node",
          message: "Add at least one node before publishing the workflow.",
        });
      }

      setValidationErrors(readinessErrors);
      setIsValidating(false);
      const completedAt = new Date().toISOString();
      setLastValidationRun(completedAt);

      toast({
        title:
          readinessErrors.length === 0
            ? "Workflow passed all validation checks"
            : `Validation found ${readinessErrors.length} issue${
                readinessErrors.length === 1 ? "" : "s"
              }`,
        description:
          readinessErrors.length === 0
            ? "You can proceed to publish once final reviews are complete."
            : "Resolve the flagged items from the Readiness tab or directly on the canvas.",
      });
    }, 250);
  }, [edges, nodes]);

  const handleDismissValidation = useCallback((id: string) => {
    setValidationErrors((prev) => prev.filter((error) => error.id !== id));
  }, []);

  const handleFixValidation = useCallback(
    (error: ValidationError) => {
      setActiveTab("canvas");

      if (error.nodeId) {
        const nodeToFocus = nodes.find((node) => node.id === error.nodeId);
        if (nodeToFocus) {
          setSelectedNodeId(nodeToFocus.id);
          requestAnimationFrame(() => {
            reactFlowInstance.current?.setCenter(
              nodeToFocus.position.x + (nodeToFocus.width ?? 0) / 2,
              nodeToFocus.position.y + (nodeToFocus.height ?? 0) / 2,
              { zoom: 1.15, duration: 400 },
            );
          });
        }
      } else if (error.sourceId && error.targetId) {
        toast({
          title: "Review the highlighted connection",
          description: `${error.sourceId} → ${error.targetId} needs to be updated before publishing.`,
        });
      }
    },
    [nodes, setActiveTab, setSelectedNodeId],
  );

  const handleOpenChat = useCallback((nodeId: string) => {
    const chatNode = nodesRef.current.find((node) => node.id === nodeId);
    if (chatNode) {
      setChatTitle(chatNode.data.label || "Chat");
      setActiveChatNodeId(nodeId);
      setIsChatOpen(true);
    }
  }, []);

  const convertPersistedNodesToCanvas = useCallback(
    (persistedNodes: PersistedWorkflowNode[]) =>
      persistedNodes.map((node) => {
        const canvasNode = toCanvasNodeBase(node);
        if (canvasNode.type === "chatTrigger") {
          return {
            ...canvasNode,
            data: {
              ...canvasNode.data,
              onOpenChat: () => handleOpenChat(canvasNode.id),
            },
          };
        }
        return canvasNode;
      }),
    [handleOpenChat],
  );

  // Refs
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const reactFlowInstance = useRef<ReactFlowInstance<
    CanvasNode,
    CanvasEdge
  > | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const searchMatchSet = useMemo(() => new Set(searchMatches), [searchMatches]);

  const createSnapshot = useCallback(
    (): WorkflowSnapshot => ({
      nodes: nodesRef.current.map(cloneNode),
      edges: edgesRef.current.map(cloneEdge),
    }),
    [],
  );

  const recordSnapshot = useCallback(
    (options?: { force?: boolean }) => {
      if (isRestoringRef.current && !options?.force) {
        return;
      }
      const snapshot = createSnapshot();
      undoStackRef.current = [...undoStackRef.current, snapshot].slice(
        -HISTORY_LIMIT,
      );
      redoStackRef.current = [];
      setCanUndo(undoStackRef.current.length > 0);
      setCanRedo(false);
    },
    [createSnapshot],
  );

  const applySnapshot = useCallback(
    (snapshot: WorkflowSnapshot, { resetHistory = false } = {}) => {
      isRestoringRef.current = true;
      setNodesState(snapshot.nodes);
      setEdgesState(snapshot.edges);
      if (resetHistory) {
        undoStackRef.current = [];
        redoStackRef.current = [];
        setCanUndo(false);
        setCanRedo(false);
      }
    },
    [setCanRedo, setCanUndo, setEdgesState, setNodesState],
  );

  useLayoutEffect(() => {
    if (isRestoringRef.current) {
      isRestoringRef.current = false;
    }
  }, [edges, nodes]);

  useEffect(() => {
    nodesRef.current = nodes;
  }, [nodes]);

  useEffect(() => {
    edgesRef.current = edges;
  }, [edges]);
  useEffect(() => {
    if (hoveredEdgeId && !edges.some((edge) => edge.id === hoveredEdgeId)) {
      setHoveredEdgeId(null);
    }
  }, [edges, hoveredEdgeId, setHoveredEdgeId]);

  const setNodes = useCallback(
    (updater: React.SetStateAction<CanvasNode[]>) => {
      if (!isRestoringRef.current) {
        recordSnapshot();
      }
      setNodesState((current) =>
        typeof updater === "function"
          ? (updater as (value: CanvasNode[]) => CanvasNode[])(current)
          : updater,
      );
    },
    [recordSnapshot, setNodesState],
  );

  const setEdges = useCallback(
    (updater: React.SetStateAction<WorkflowEdge[]>) => {
      if (!isRestoringRef.current) {
        recordSnapshot();
      }
      setEdgesState((current) =>
        typeof updater === "function"
          ? (updater as (value: WorkflowEdge[]) => WorkflowEdge[])(current)
          : updater,
      );
    },
    [recordSnapshot, setEdgesState],
  );

  const handleInsertSubworkflow = useCallback(
    (subworkflow: SubworkflowTemplate) => {
      const libraryEntry = SUBWORKFLOW_LIBRARY[subworkflow.id];

      if (!libraryEntry) {
        toast({
          title: "Template unavailable",
          description:
            "This sub-workflow doesn't have a canvas definition yet. Please try another template.",
          variant: "destructive",
        });
        return;
      }

      const templateXs = libraryEntry.nodes.map(
        (node) => node.position?.x ?? 0,
      );
      const templateYs = libraryEntry.nodes.map(
        (node) => node.position?.y ?? 0,
      );
      const templateMinX = templateXs.length > 0 ? Math.min(...templateXs) : 0;
      const templateMinY = templateYs.length > 0 ? Math.min(...templateYs) : 0;

      const existingNodes = nodesRef.current;
      const existingMaxX = existingNodes.length
        ? Math.max(...existingNodes.map((node) => node.position?.x ?? 0))
        : 0;
      const existingMinY = existingNodes.length
        ? Math.min(...existingNodes.map((node) => node.position?.y ?? 0))
        : 0;

      const insertionX = existingNodes.length > 0 ? existingMaxX + 320 : 200;
      const insertionY = existingNodes.length > 0 ? existingMinY : 200;

      const idMap = new Map<string, string>();
      const allocateIdentity = createIdentityAllocator(nodesRef.current);

      const remappedNodes = libraryEntry.nodes.map((node) => {
        const baseLabel =
          typeof node.data?.label === "string" && node.data.label.length > 0
            ? node.data.label
            : typeof node.data?.type === "string" && node.data.type.length > 0
              ? `${node.data.type} Node`
              : DEFAULT_NODE_LABEL;
        const { id: newId, label } = allocateIdentity(baseLabel);
        idMap.set(node.id, newId);

        return {
          ...node,
          id: newId,
          position: {
            x: insertionX + ((node.position?.x ?? 0) - templateMinX),
            y: insertionY + ((node.position?.y ?? 0) - templateMinY),
          },
          data: {
            ...node.data,
            type: node.data?.type ?? node.type ?? "default",
            status: "idle",
            label,
          },
        };
      });

      const remappedEdges = libraryEntry.edges.map((edge) => ({
        ...edge,
        id: generateRandomId("edge"),
        source: idMap.get(edge.source) ?? edge.source,
        target: idMap.get(edge.target) ?? edge.target,
      }));

      const canvasNodes = convertPersistedNodesToCanvas(remappedNodes);
      const canvasEdges = convertPersistedEdgesToCanvas(remappedEdges);

      setNodes((current) => [...current, ...canvasNodes]);
      setEdges((current) => [...current, ...canvasEdges]);

      setSubworkflows((prev) =>
        prev.map((template) =>
          template.id === subworkflow.id
            ? {
                ...template,
                usageCount: template.usageCount + 1,
                lastUpdated: new Date().toISOString(),
              }
            : template,
        ),
      );

      if (canvasNodes.length > 0) {
        setSelectedNodeId(canvasNodes[0].id);
        setActiveTab("canvas");

        if (reactFlowInstance.current) {
          const insertedXs = canvasNodes.map((node) => node.position.x);
          const insertedYs = canvasNodes.map((node) => node.position.y);
          const minX = Math.min(...insertedXs);
          const maxX = Math.max(...insertedXs);
          const minY = Math.min(...insertedYs);
          const maxY = Math.max(...insertedYs);
          const centerX = minX + (maxX - minX) / 2;
          const centerY = minY + (maxY - minY) / 2;

          reactFlowInstance.current.setCenter(centerX, centerY, {
            zoom: 1.15,
            duration: 400,
          });
        }
      }

      toast({
        title: `${subworkflow.name} inserted`,
        description: `Added ${canvasNodes.length} nodes and ${canvasEdges.length} connections to the canvas.`,
      });
    },
    [
      convertPersistedNodesToCanvas,
      setNodes,
      setEdges,
      setSubworkflows,
      setSelectedNodeId,
      setActiveTab,
    ],
  );

  const handleNodesChange = useCallback(
    (changes: NodeChange<CanvasNode>[]) => {
      const shouldRecord = changes.some((change) => {
        if (change.type === "select") {
          return false;
        }
        if (change.type === "position" && change.dragging) {
          return false;
        }
        return true;
      });
      if (shouldRecord) {
        recordSnapshot();
      }
      onNodesChangeState(changes);
    },
    [onNodesChangeState, recordSnapshot],
  );

  const handleEdgesChange = useCallback(
    (changes: EdgeChange<WorkflowEdge>[]) => {
      if (changes.some((change) => change.type !== "select")) {
        recordSnapshot();
      }
      onEdgesChangeState(changes);
    },
    [onEdgesChangeState, recordSnapshot],
  );
  const handleEdgeMouseEnter = useCallback(
    (_event: React.MouseEvent<Element>, edge: CanvasEdge) => {
      setHoveredEdgeId(edge.id);
    },
    [setHoveredEdgeId],
  );
  const handleEdgeMouseLeave = useCallback(
    (event: React.MouseEvent<Element>, edge: CanvasEdge) => {
      const relatedTarget = event.relatedTarget as HTMLElement | null;
      if (
        relatedTarget &&
        typeof relatedTarget.closest === "function" &&
        relatedTarget.closest(`[data-edge-id="${edge.id}"]`)
      ) {
        return;
      }
      setHoveredEdgeId((current) => (current === edge.id ? null : current));
    },
    [setHoveredEdgeId],
  );

  const resolveNodeLabel = useCallback((canvasNodeId: string): string => {
    const node = latestNodesRef.current.find(
      (item) => item.id === canvasNodeId,
    );
    const label =
      typeof node?.data?.label === "string" && node.data.label.trim()
        ? node.data.label.trim()
        : null;
    return label ?? canvasNodeId;
  }, []);

  const deleteNodes = useCallback(
    (nodeIds: string[], options?: { suppressToast?: boolean }) => {
      const uniqueIds = Array.from(new Set(nodeIds)).filter(Boolean);
      if (uniqueIds.length === 0) {
        return;
      }

      const labels = uniqueIds.map((id) => resolveNodeLabel(id));

      setNodeRuntimeCache((current) => {
        if (Object.keys(current).length === 0) {
          return current;
        }

        let modified = false;
        const next = { ...current };
        for (const id of uniqueIds) {
          if (id in next) {
            delete next[id];
            modified = true;
          }
        }

        return modified ? next : current;
      });

      isRestoringRef.current = true;
      recordSnapshot({ force: true });
      try {
        setNodesState((current) =>
          current.filter((node) => !uniqueIds.includes(node.id)),
        );
        setEdgesState((current) =>
          current.filter(
            (edge) =>
              !uniqueIds.includes(edge.source) &&
              !uniqueIds.includes(edge.target),
          ),
        );
      } catch (error) {
        isRestoringRef.current = false;
        throw error;
      }

      setValidationErrors((errors) =>
        errors.filter((error) => {
          if (error.nodeId && uniqueIds.includes(error.nodeId)) {
            return false;
          }
          if (error.sourceId && uniqueIds.includes(error.sourceId)) {
            return false;
          }
          if (error.targetId && uniqueIds.includes(error.targetId)) {
            return false;
          }
          return true;
        }),
      );

      setSearchMatches((matches) =>
        matches.filter((match) => !uniqueIds.includes(match)),
      );

      setSelectedNodeId((current) =>
        current && uniqueIds.includes(current) ? null : current,
      );

      if (activeChatNodeId && uniqueIds.includes(activeChatNodeId)) {
        setActiveChatNodeId(null);
        setIsChatOpen(false);
      }

      if (!options?.suppressToast) {
        toast({
          title: uniqueIds.length === 1 ? "Node deleted" : "Nodes deleted",
          description:
            uniqueIds.length === 1
              ? `Removed ${labels[0]}.`
              : `Removed ${uniqueIds.length} nodes.`,
        });
      }
    },
    [
      activeChatNodeId,
      recordSnapshot,
      resolveNodeLabel,
      setNodeRuntimeCache,
      setActiveChatNodeId,
      setEdgesState,
      setIsChatOpen,
      setNodesState,
      setSearchMatches,
      setSelectedNodeId,
      setValidationErrors,
    ],
  );

  const handleDeleteNode = useCallback(
    (nodeId: string) => {
      deleteNodes([nodeId]);
    },
    [deleteNodes],
  );

  const handleUpdateStickyNoteNode = useCallback(
    (
      nodeId: string,
      updates: Partial<
        Pick<StickyNoteNodeData, "color" | "content" | "width" | "height">
      >,
    ) => {
      setNodes((nds) =>
        nds.map((node) => {
          if (node.id !== nodeId) {
            return node;
          }

          const sanitizedUpdates: Record<string, unknown> = {};

          if ("color" in updates) {
            sanitizedUpdates.color = isStickyNoteColor(updates.color)
              ? updates.color
              : DEFAULT_STICKY_NOTE_COLOR;
          }

          if ("content" in updates && typeof updates.content === "string") {
            sanitizedUpdates.content = updates.content;
          }

          if ("width" in updates && typeof updates.width === "number") {
            sanitizedUpdates.width = clampStickyDimension(
              updates.width,
              STICKY_NOTE_MIN_WIDTH,
            );
          }

          if ("height" in updates && typeof updates.height === "number") {
            sanitizedUpdates.height = clampStickyDimension(
              updates.height,
              STICKY_NOTE_MIN_HEIGHT,
            );
          }

          if (Object.keys(sanitizedUpdates).length === 0) {
            return node;
          }

          return {
            ...node,
            data: {
              ...node.data,
              ...sanitizedUpdates,
            },
          };
        }),
      );
    },
    [setNodes],
  );

  const decoratedNodes = useMemo(() => {
    return nodes.map((node) => {
      const isMatch = searchMatchSet.has(node.id);
      const isActive =
        isMatch &&
        isSearchOpen &&
        searchMatches[currentSearchIndex] === node.id;
      const isStickyNoteNode = node.type === "stickyNote";

      const baseData = {
        ...node.data,
        onDelete: handleDeleteNode,
        ...(isStickyNoteNode
          ? { onUpdateStickyNote: handleUpdateStickyNoteNode }
          : {}),
      } as NodeData & Record<string, unknown>;

      const augmentedData = isStickyNoteNode
        ? ({
            ...baseData,
            label:
              typeof baseData.label === "string" && baseData.label.length > 0
                ? baseData.label
                : "Sticky Note",
            color: isStickyNoteColor(baseData.color)
              ? (baseData.color as StickyNoteColor)
              : DEFAULT_STICKY_NOTE_COLOR,
            content: sanitizeStickyNoteContent(baseData.content),
            width: sanitizeStickyNoteDimension(
              baseData.width,
              DEFAULT_STICKY_NOTE_WIDTH,
              STICKY_NOTE_MIN_WIDTH,
            ),
            height: sanitizeStickyNoteDimension(
              baseData.height,
              DEFAULT_STICKY_NOTE_HEIGHT,
              STICKY_NOTE_MIN_HEIGHT,
            ),
            onUpdateStickyNote: handleUpdateStickyNoteNode,
          } as NodeData)
        : baseData;

      const decoratedData = !isSearchOpen
        ? {
            ...augmentedData,
            isSearchMatch: false,
            isSearchActive: false,
          }
        : {
            ...augmentedData,
            isSearchMatch: isMatch,
            isSearchActive: isActive,
          };

      return {
        ...node,
        data: decoratedData,
        ...(isStickyNoteNode ? { connectable: false } : {}),
      };
    });
  }, [
    currentSearchIndex,
    handleDeleteNode,
    handleUpdateStickyNoteNode,
    isSearchOpen,
    nodes,
    searchMatchSet,
    searchMatches,
  ]);

  const determineLogLevel = useCallback(
    (
      payload: Record<string, unknown>,
    ): "INFO" | "DEBUG" | "ERROR" | "WARNING" => {
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
        typeof payload.status === "string"
          ? payload.status.toLowerCase()
          : null;
      if (status === "error" || status === "failed") {
        return "ERROR";
      }
      if (
        status === "warning" ||
        status === "cancelled" ||
        status === "partial"
      ) {
        return "WARNING";
      }
      if (status === "debug") {
        return "DEBUG";
      }
      return "INFO";
    },
    [],
  );

  const describePayload = useCallback(
    (
      payload: Record<string, unknown>,
      graphToCanvas: Record<string, string>,
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
        const label = resolveNodeLabel(canvasNodeId);
        if (status) {
          return `Node ${label} ${status}`;
        }
        return `Node ${label} emitted an update`;
      }

      if (status) {
        return `Run status changed to ${status}`;
      }

      return JSON.stringify(payload);
    },
    [resolveNodeLabel],
  );

  const deriveNodeStatusUpdates = useCallback(
    (
      payload: Record<string, unknown>,
      graphToCanvas: Record<string, string>,
    ): Record<string, NodeStatus> => {
      const nodeKey = ["node", "step", "name"].find(
        (key) => typeof payload[key] === "string" && payload[key],
      );
      if (!nodeKey) {
        return {};
      }
      const statusValue =
        typeof payload.status === "string" ? payload.status : undefined;
      if (!statusValue) {
        return {};
      }
      const graphNode = String(payload[nodeKey]);
      const canvasNodeId = graphToCanvas[graphNode] ?? graphNode;
      const status = nodeStatusFromValue(statusValue);
      return { [canvasNodeId]: status };
    },
    [],
  );

  const applyExecutionUpdate = useCallback(
    (
      executionId: string,
      payload: Record<string, unknown>,
      graphToCanvas: Record<string, string>,
    ) => {
      if (!isMountedRef.current) {
        return;
      }

      const statusValue =
        typeof payload.status === "string" ? payload.status : undefined;
      const hasNodeReference = ["node", "step", "name"].some(
        (key) => typeof payload[key] === "string" && payload[key],
      );
      let executionStatus = executionStatusFromValue(statusValue);

      if (hasNodeReference) {
        executionStatus = null;
      }

      if (typeof payload.error === "string" && payload.error.trim()) {
        executionStatus = "failed";
      }

      const nodeUpdates = deriveNodeStatusUpdates(payload, graphToCanvas);
      const timestamp = new Date();
      const updatedAt = timestamp.toISOString();

      const runtimeUpdates: Record<string, NodeRuntimeData> = {};
      Object.entries(payload).forEach(([key, value]) => {
        if (typeof key !== "string") {
          return;
        }
        if (
          key === "status" ||
          key === "level" ||
          key === "error" ||
          key === "message" ||
          key === "type" ||
          key === "timestamp" ||
          key === "step"
        ) {
          return;
        }
        const canvasNodeId = graphToCanvas[key] ?? null;
        if (!canvasNodeId) {
          return;
        }
        if (!isRecord(value)) {
          return;
        }

        const resultsCandidate = value["results"];
        let candidatePayload: unknown;

        if (isRecord(resultsCandidate)) {
          candidatePayload =
            resultsCandidate[key] ??
            resultsCandidate[canvasNodeId] ??
            Object.values(resultsCandidate)[0];
        }

        if (candidatePayload === undefined) {
          const directValue =
            typeof value[key] !== "undefined" ? value[key] : undefined;
          if (directValue !== undefined) {
            candidatePayload = directValue;
          }
        }

        if (candidatePayload === undefined && value["value"] !== undefined) {
          candidatePayload = value["value"];
        }

        if (candidatePayload === undefined) {
          candidatePayload = value;
        }

        let inputs: unknown;
        let outputs: unknown;
        let messages: unknown;
        if (isRecord(candidatePayload)) {
          inputs =
            candidatePayload["inputs"] !== undefined
              ? candidatePayload["inputs"]
              : candidatePayload["input"];
          outputs =
            candidatePayload["outputs"] !== undefined
              ? candidatePayload["outputs"]
              : (candidatePayload["output"] ?? candidatePayload["result"]);
          messages = candidatePayload["messages"];
        }

        runtimeUpdates[canvasNodeId] = {
          ...(inputs !== undefined ? { inputs } : {}),
          ...(outputs !== undefined ? { outputs } : {}),
          ...(messages !== undefined ? { messages } : {}),
          raw: candidatePayload,
          updatedAt,
        };
      });

      const logLevel = determineLogLevel(payload);
      const message = describePayload(payload, graphToCanvas);

      setExecutions((prev) =>
        prev.map((execution) => {
          if (execution.id !== executionId) {
            return execution;
          }

          const updatedNodes = execution.nodes.map((node) => {
            const nextStatus = nodeUpdates[node.id];
            const runtime = runtimeUpdates[node.id];
            let updatedNode = node;
            if (nextStatus) {
              updatedNode = { ...updatedNode, status: nextStatus };
            } else if (
              executionStatus &&
              executionStatus !== "running" &&
              node.status === "running"
            ) {
              const fallback: NodeStatus =
                executionStatus === "failed"
                  ? "error"
                  : executionStatus === "partial"
                    ? "warning"
                    : "success";
              updatedNode = { ...updatedNode, status: fallback };
            }

            if (runtime) {
              const existingDetails =
                node.details && isRecord(node.details)
                  ? (node.details as Record<string, unknown>)
                  : {};
              const nextDetails: Record<string, unknown> = {
                ...existingDetails,
              };
              if (runtime.inputs !== undefined) {
                nextDetails.inputs = runtime.inputs;
              }
              if (runtime.outputs !== undefined) {
                nextDetails.outputs = runtime.outputs;
              }
              if (runtime.messages !== undefined) {
                nextDetails.messages = runtime.messages;
              }
              nextDetails.raw = runtime.raw;
              nextDetails.updatedAt = runtime.updatedAt;
              updatedNode = { ...updatedNode, details: nextDetails };
            }

            return updatedNode;
          });

          const logs = [
            ...execution.logs,
            {
              timestamp: timestamp.toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              }),
              level: logLevel,
              message,
            },
          ];

          const duration =
            timestamp.getTime() - new Date(execution.startTime).getTime();

          const issues =
            logLevel === "ERROR" ? execution.issues + 1 : execution.issues;

          const metadata = {
            ...(execution.metadata ?? {}),
            graphToCanvas: {
              ...(execution.metadata?.graphToCanvas ?? {}),
              ...graphToCanvas,
            },
          };

          const endTime =
            executionStatus && executionStatus !== "running"
              ? timestamp.toISOString()
              : execution.endTime;

          return {
            ...execution,
            status: executionStatus ?? execution.status,
            nodes: updatedNodes,
            logs,
            duration,
            issues,
            endTime,
            metadata,
          };
        }),
      );

      const hasRuntimeUpdates = Object.keys(runtimeUpdates).length > 0;

      if (
        Object.keys(nodeUpdates).length > 0 ||
        hasRuntimeUpdates ||
        (executionStatus && executionStatus !== "running")
      ) {
        setNodes((prev) =>
          prev.map((node) => {
            const nextStatus = nodeUpdates[node.id];
            const runtime = runtimeUpdates[node.id];
            let nextData = node.data;
            let changed = false;

            if (nextStatus) {
              nextData = { ...nextData, status: nextStatus };
              changed = true;
            } else if (
              executionStatus &&
              executionStatus !== "running" &&
              (node.data?.status === "running" ||
                node.data?.status === undefined)
            ) {
              const fallback: NodeStatus =
                executionStatus === "failed"
                  ? "error"
                  : executionStatus === "partial"
                    ? "warning"
                    : "success";
              nextData = { ...nextData, status: fallback };
              changed = true;
            }

            if (runtime) {
              const nextRuntime: NodeRuntimeData = {
                ...((nextData.runtime ?? {}) as NodeRuntimeData),
                ...(runtime.inputs !== undefined
                  ? { inputs: runtime.inputs }
                  : {}),
                ...(runtime.outputs !== undefined
                  ? { outputs: runtime.outputs }
                  : {}),
                ...(runtime.messages !== undefined
                  ? { messages: runtime.messages }
                  : {}),
                raw: runtime.raw,
                updatedAt: runtime.updatedAt,
              };
              nextData = { ...nextData, runtime: nextRuntime };
              changed = true;
            }

            if (changed) {
              return {
                ...node,
                data: nextData,
              };
            }

            return node;
          }),
        );
      }

      if (executionStatus && executionStatus !== "running") {
        setIsRunning(false);
        if (websocketRef.current) {
          websocketRef.current.close();
          websocketRef.current = null;
        }
      }
    },
    [
      setExecutions,
      setNodes,
      setIsRunning,
      deriveNodeStatusUpdates,
      determineLogLevel,
      describePayload,
    ],
  );

  const highlightMatch = useCallback(
    (index: number) => {
      const instance = reactFlowInstance.current;
      if (!instance) {
        return;
      }

      const nodeId = searchMatches[index];
      if (!nodeId) {
        return;
      }

      const node = instance.getNode(nodeId);
      if (!node) {
        return;
      }

      const position = node.positionAbsolute ?? node.position;
      const width = node.measured?.width ?? node.width ?? 180;
      const height = node.measured?.height ?? node.height ?? 120;

      const centerX = (position?.x ?? 0) + width / 2;
      const centerY = (position?.y ?? 0) + height / 2;

      const zoomLevel =
        typeof instance.getZoom === "function"
          ? Math.max(instance.getZoom(), 1.2)
          : 1.2;

      instance.setCenter(centerX, centerY, {
        zoom: zoomLevel,
        duration: 300,
      });
    },
    [searchMatches],
  );

  const handleSearchNodes = useCallback((query: string) => {
    const normalized = query.trim().toLowerCase();

    if (!normalized) {
      setSearchMatches([]);
      setCurrentSearchIndex(0);
      return;
    }

    const matches = nodesRef.current
      .filter((node) => {
        const label = String(node.data?.label ?? "").toLowerCase();
        const description = String(node.data?.description ?? "").toLowerCase();
        return (
          label.includes(normalized) ||
          description.includes(normalized) ||
          node.id.toLowerCase().includes(normalized)
        );
      })
      .map((node) => node.id);

    setSearchMatches(matches);
    setCurrentSearchIndex(matches.length > 0 ? 0 : 0);
  }, []);

  const handleHighlightNext = useCallback(() => {
    if (searchMatches.length === 0) {
      return;
    }
    setCurrentSearchIndex((index) => (index + 1) % searchMatches.length);
  }, [searchMatches]);

  const handleHighlightPrevious = useCallback(() => {
    if (searchMatches.length === 0) {
      return;
    }
    setCurrentSearchIndex(
      (index) => (index - 1 + searchMatches.length) % searchMatches.length,
    );
  }, [searchMatches]);

  const handleCloseSearch = useCallback(() => {
    setIsSearchOpen(false);
    setSearchMatches([]);
    setCurrentSearchIndex(0);
  }, []);

  const handleToggleSearch = useCallback(() => {
    setIsSearchOpen((previous) => {
      const next = !previous;
      setSearchMatches([]);
      setCurrentSearchIndex(0);
      return next;
    });
  }, []);

  useEffect(() => {
    if (!isSearchOpen) {
      return;
    }

    if (searchMatches.length === 0) {
      return;
    }

    const safeIndex = Math.min(
      currentSearchIndex,
      Math.max(searchMatches.length - 1, 0),
    );

    if (safeIndex !== currentSearchIndex) {
      setCurrentSearchIndex(safeIndex);
      return;
    }

    highlightMatch(safeIndex);
  }, [currentSearchIndex, highlightMatch, isSearchOpen, searchMatches]);

  const handleDuplicateSelectedNodes = useCallback(() => {
    const selectedNodes = nodes.filter((node) => node.selected);
    if (selectedNodes.length === 0) {
      toast({
        title: "No nodes selected",
        description: "Select at least one node to duplicate.",
        variant: "destructive",
      });
      return;
    }

    const idMap = new Map<string, string>();
    const allocateIdentity = createIdentityAllocator(nodesRef.current);
    const duplicatedNodes = selectedNodes.map((node) => {
      const clonedNode = cloneNode(node);
      const baseLabel =
        typeof clonedNode.data?.label === "string" &&
        clonedNode.data.label.trim().length > 0
          ? `${clonedNode.data.label} Copy`
          : `${clonedNode.id} Copy`;
      const { id: newId, label } = allocateIdentity(baseLabel);
      idMap.set(node.id, newId);
      const duplicatedData: NodeData = {
        ...(clonedNode.data as NodeData),
        label,
      };
      if (clonedNode.type === "chatTrigger") {
        duplicatedData.onOpenChat = () => handleOpenChat(newId);
      }
      return {
        ...clonedNode,
        id: newId,
        position: {
          x: (clonedNode.position?.x ?? 0) + 40,
          y: (clonedNode.position?.y ?? 0) + 40,
        },
        selected: false,
        data: duplicatedData,
      } as CanvasNode;
    });

    const selectedIds = new Set(selectedNodes.map((node) => node.id));
    const duplicatedEdges = edges
      .filter(
        (edge) => selectedIds.has(edge.source) && selectedIds.has(edge.target),
      )
      .map((edge) => {
        const sourceId = idMap.get(edge.source);
        const targetId = idMap.get(edge.target);
        if (!sourceId || !targetId) {
          return null;
        }
        const clonedEdge = cloneEdge(edge);
        return {
          ...clonedEdge,
          id: `edge-${sourceId}-${targetId}-${Math.random()
            .toString(36)
            .slice(2, 8)}`,
          source: sourceId,
          target: targetId,
          selected: false,
        } as WorkflowEdge;
      })
      .filter(Boolean) as WorkflowEdge[];

    isRestoringRef.current = true;
    recordSnapshot({ force: true });
    try {
      setNodesState((current) => [...current, ...duplicatedNodes]);
      if (duplicatedEdges.length > 0) {
        setEdgesState((current) => [...current, ...duplicatedEdges]);
      }
    } catch (error) {
      isRestoringRef.current = false;
      throw error;
    }
    toast({
      title: "Nodes duplicated",
      description: `${duplicatedNodes.length} node${
        duplicatedNodes.length === 1 ? "" : "s"
      } copied with their connections.`,
    });
  }, [
    edges,
    handleOpenChat,
    nodes,
    recordSnapshot,
    setEdgesState,
    setNodesState,
  ]);

  const copyNodesToClipboard = useCallback(
    async (
      nodesToCopy: CanvasNode[],
      options: CopyClipboardOptions = {},
    ): Promise<CopyClipboardResult> => {
      if (nodesToCopy.length === 0) {
        toast({
          title: "No nodes selected",
          description: "Select at least one node to copy.",
          variant: "destructive",
        });
        return {
          success: false,
          nodeCount: 0,
          edgeCount: 0,
          usedFallback: false,
        };
      }

      const selectedIds = new Set(nodesToCopy.map((node) => node.id));
      const persistedNodes = nodesToCopy.map(toPersistedNode);
      const persistedEdges = edgesRef.current
        .filter(
          (edge) =>
            selectedIds.has(edge.source) && selectedIds.has(edge.target),
        )
        .map(toPersistedEdge);

      const payload = buildClipboardPayload(persistedNodes, persistedEdges);
      clipboardRef.current = payload;
      pasteOffsetStepRef.current = 0;
      lastClipboardSignatureRef.current =
        signatureFromClipboardPayload(payload);

      let systemClipboardCopied = false;

      if (
        typeof navigator !== "undefined" &&
        navigator.clipboard &&
        typeof navigator.clipboard.writeText === "function"
      ) {
        try {
          await navigator.clipboard.writeText(encodeClipboardPayload(payload));
          systemClipboardCopied = true;
        } catch (error) {
          console.warn(
            "Failed to write workflow selection to clipboard",
            error,
          );
        }
      }

      if (!options.skipSuccessToast) {
        toast({
          title: nodesToCopy.length === 1 ? "Node copied" : "Nodes copied",
          description: `${nodesToCopy.length} node${
            nodesToCopy.length === 1 ? "" : "s"
          } copied${
            systemClipboardCopied ? "" : " (available for in-app paste)"
          }.`,
        });
      } else if (!systemClipboardCopied) {
        toast({
          title: "Nodes copied (in-app clipboard)",
          description:
            "System clipboard unavailable. Paste with Ctrl/Cmd+V in this tab.",
        });
      }

      return {
        success: true,
        nodeCount: nodesToCopy.length,
        edgeCount: persistedEdges.length,
        usedFallback: !systemClipboardCopied,
      };
    },
    [clipboardRef, edgesRef, lastClipboardSignatureRef, pasteOffsetStepRef],
  );

  const copySelectedNodes = useCallback(async () => {
    const selectedNodes = nodesRef.current.filter((node) => node.selected);
    return copyNodesToClipboard(selectedNodes);
  }, [copyNodesToClipboard]);

  const cutSelectedNodes = useCallback(async () => {
    const selectedNodes = nodesRef.current.filter((node) => node.selected);
    const nodeIds = selectedNodes.map((node) => node.id);
    const result = await copyNodesToClipboard(selectedNodes, {
      skipSuccessToast: true,
    });

    if (!result.success) {
      return;
    }

    deleteNodes(nodeIds, { suppressToast: true });

    const fallbackNote = result.usedFallback
      ? "System clipboard unavailable. Paste with Ctrl/Cmd+V in this tab."
      : "Paste with Ctrl/Cmd+V.";

    toast({
      title: nodeIds.length === 1 ? "Node cut" : "Nodes cut",
      description: `${nodeIds.length} node${
        nodeIds.length === 1 ? "" : "s"
      } ready to paste. ${fallbackNote}`,
    });
  }, [copyNodesToClipboard, deleteNodes]);

  const pasteNodes = useCallback(async () => {
    let payload: WorkflowClipboardPayload | null = null;

    if (
      typeof navigator !== "undefined" &&
      navigator.clipboard &&
      typeof navigator.clipboard.readText === "function"
    ) {
      try {
        const clipboardText = await navigator.clipboard.readText();
        const parsed = decodeClipboardPayloadString(clipboardText);
        if (parsed) {
          payload = parsed;
        }
      } catch (error) {
        console.warn("Failed to read workflow selection from clipboard", error);
      }
    }

    if (!payload) {
      payload = clipboardRef.current;
    }

    if (!payload || payload.nodes.length === 0) {
      toast({
        title: "Nothing to paste",
        description: "Copy nodes before pasting.",
        variant: "destructive",
      });
      return;
    }

    const signature = signatureFromClipboardPayload(payload);
    if (signature !== lastClipboardSignatureRef.current) {
      pasteOffsetStepRef.current = 0;
      lastClipboardSignatureRef.current = signature;
    }

    clipboardRef.current = payload;

    const step = pasteOffsetStepRef.current;
    const offset = PASTE_BASE_OFFSET + step * PASTE_OFFSET_INCREMENT;
    pasteOffsetStepRef.current = Math.min(
      pasteOffsetStepRef.current + 1,
      PASTE_OFFSET_MAX_STEPS,
    );

    const idMap = new Map<string, string>();
    const allocateIdentity = createIdentityAllocator(nodesRef.current);

    const remappedNodes = payload.nodes.map((node) => {
      const baseLabel =
        typeof node.data?.label === "string" &&
        node.data.label.trim().length > 0
          ? node.data.label
          : sanitizeLabel(node.id);
      const { id: newId, label } = allocateIdentity(baseLabel);
      idMap.set(node.id, newId);
      const position = node.position ?? { x: 0, y: 0 };
      return {
        ...node,
        id: newId,
        position: {
          x: position.x + offset,
          y: position.y + offset,
        },
        data: {
          ...node.data,
          label,
        },
      };
    });

    const remappedEdges = payload.edges
      .map((edge) => {
        const sourceId = idMap.get(edge.source);
        const targetId = idMap.get(edge.target);
        if (!sourceId || !targetId) {
          return null;
        }
        return {
          ...edge,
          id: generateRandomId("edge"),
          source: sourceId,
          target: targetId,
        };
      })
      .filter(Boolean) as PersistedWorkflowEdge[];

    const canvasNodes = convertPersistedNodesToCanvas(remappedNodes);
    const canvasEdges = convertPersistedEdgesToCanvas(remappedEdges);

    if (canvasNodes.length === 0) {
      toast({
        title: "Nothing to paste",
        description: "Copied selection has no nodes.",
        variant: "destructive",
      });
      return;
    }

    isRestoringRef.current = true;
    recordSnapshot({ force: true });
    try {
      setNodesState((current) => [...current, ...canvasNodes]);
      if (canvasEdges.length > 0) {
        setEdgesState((current) => [...current, ...canvasEdges]);
      }
    } catch (error) {
      isRestoringRef.current = false;
      throw error;
    }

    const connectionsNote =
      canvasEdges.length > 0
        ? ` with ${canvasEdges.length} connection${
            canvasEdges.length === 1 ? "" : "s"
          }`
        : "";

    toast({
      title: canvasNodes.length === 1 ? "Node pasted" : "Nodes pasted",
      description: `Added ${canvasNodes.length} node${
        canvasNodes.length === 1 ? "" : "s"
      }${connectionsNote}.`,
    });
  }, [
    clipboardRef,
    convertPersistedNodesToCanvas,
    lastClipboardSignatureRef,
    pasteOffsetStepRef,
    recordSnapshot,
    setEdgesState,
    setNodesState,
  ]);

  const handleExportWorkflow = useCallback(() => {
    try {
      const snapshot = createSnapshot();
      const workflowData = {
        name: workflowName,
        description: workflowDescription,
        nodes: snapshot.nodes.map(toPersistedNode),
        edges: snapshot.edges.map(toPersistedEdge),
      };
      const serialized = JSON.stringify(workflowData, null, 2);
      const blob = new Blob([serialized], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${
        workflowName.replace(/\s+/g, "-").toLowerCase() || "workflow"
      }.json`;
      anchor.click();
      URL.revokeObjectURL(url);
      toast({
        title: "Workflow exported",
        description: "A JSON export has been downloaded.",
      });
    } catch (error) {
      toast({
        title: "Export failed",
        description:
          error instanceof Error ? error.message : "Unable to export workflow.",
        variant: "destructive",
      });
    }
  }, [createSnapshot, workflowDescription, workflowName]);

  const handleImportWorkflow = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleWorkflowFileSelected = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (!file) {
        return;
      }

      const reader = new FileReader();
      reader.onload = () => {
        try {
          const content =
            typeof reader.result === "string" ? reader.result : "";
          const parsed = JSON.parse(content);
          validateWorkflowData(parsed);

          const rawNodes = (parsed.nodes as PersistedWorkflowNode[]).map(
            (node) => ({
              ...node,
              id: node.id ?? generateNodeId(),
            }),
          );
          const rawEdges = (parsed.edges as PersistedWorkflowEdge[]).map(
            (edge) => ({
              ...edge,
              id:
                edge.id ??
                `edge-${Math.random().toString(36).slice(2, 8)}-${Math.random()
                  .toString(36)
                  .slice(2, 8)}`,
            }),
          );

          const importedNodes = convertPersistedNodesToCanvas(rawNodes);
          const importedEdges = convertPersistedEdgesToCanvas(rawEdges);

          isRestoringRef.current = true;
          recordSnapshot({ force: true });
          try {
            setNodesState(importedNodes);
            setEdgesState(importedEdges);
            if (
              typeof parsed.name === "string" &&
              parsed.name.trim().length > 0
            ) {
              setWorkflowName(parsed.name);
            }
            if (typeof parsed.description === "string") {
              setWorkflowDescription(parsed.description);
            }
            setCurrentWorkflowId(null);
            setWorkflowVersions([]);
            setWorkflowTags(["draft"]);
          } catch (error) {
            isRestoringRef.current = false;
            throw error;
          }

          toast({
            title: "Workflow imported",
            description: `Loaded ${importedNodes.length} node${
              importedNodes.length === 1 ? "" : "s"
            } from file.`,
          });
        } catch (error) {
          toast({
            title: "Import failed",
            description:
              error instanceof Error ? error.message : "Invalid workflow file.",
            variant: "destructive",
          });
        } finally {
          event.target.value = "";
        }
      };
      reader.onerror = () => {
        toast({
          title: "Import failed",
          description: "Unable to read the selected file.",
          variant: "destructive",
        });
        event.target.value = "";
      };
      reader.readAsText(file);
    },
    [
      convertPersistedNodesToCanvas,
      recordSnapshot,
      setEdgesState,
      setNodesState,
      setWorkflowDescription,
      setWorkflowName,
    ],
  );

  const handleSaveWorkflow = useCallback(async () => {
    const snapshot = createSnapshot();
    const persistedNodes = snapshot.nodes.map(toPersistedNode);
    const persistedEdges = snapshot.edges.map(toPersistedEdge);
    const timestampLabel = new Date().toLocaleString();

    const tagsToPersist = workflowTags.length > 0 ? workflowTags : ["draft"];

    try {
      const saved = await persistWorkflow(
        {
          id: currentWorkflowId ?? undefined,
          name: workflowName.trim() || "Untitled Workflow",
          description: workflowDescription.trim(),
          tags: tagsToPersist,
          nodes: persistedNodes,
          edges: persistedEdges,
        },
        { versionMessage: `Manual save (${timestampLabel})` },
      );

      setCurrentWorkflowId(saved.id);
      setWorkflowName(saved.name);
      setWorkflowDescription(saved.description ?? "");
      setWorkflowTags(saved.tags ?? tagsToPersist);
      setWorkflowVersions(saved.versions ?? []);

      toast({
        title: "Workflow saved",
        description: `"${saved.name}" has been updated.`,
      });

      if (!workflowId || workflowId !== saved.id) {
        navigate(`/workflow-canvas/${saved.id}`, { replace: !!workflowId });
      }
    } catch (error) {
      toast({
        title: "Failed to save workflow",
        description:
          error instanceof Error ? error.message : "Unknown error occurred",
        variant: "destructive",
      });
    }
  }, [
    createSnapshot,
    currentWorkflowId,
    navigate,
    workflowDescription,
    workflowId,
    workflowName,
    workflowTags,
  ]);

  const handleTagsChange = useCallback((value: string) => {
    const tags = value
      .split(",")
      .map((tag) => tag.trim())
      .filter((tag) => tag.length > 0);
    setWorkflowTags(tags);
  }, []);

  const handleRestoreVersion = useCallback(
    async (versionId: string) => {
      if (!currentWorkflowId) {
        toast({
          title: "Save required",
          description: "Save this workflow before restoring versions.",
          variant: "destructive",
        });
        return;
      }

      try {
        const snapshot = await getVersionSnapshot(currentWorkflowId, versionId);
        if (!snapshot) {
          toast({
            title: "Version unavailable",
            description: "We couldn't load that version. Please try again.",
            variant: "destructive",
          });
          return;
        }

        const canvasNodes = convertPersistedNodesToCanvas(snapshot.nodes ?? []);
        const canvasEdges = convertPersistedEdgesToCanvas(snapshot.edges ?? []);
        applySnapshot(
          { nodes: canvasNodes, edges: canvasEdges },
          { resetHistory: true },
        );
        setWorkflowName(snapshot.name);
        setWorkflowDescription(snapshot.description ?? "");
        toast({
          title: "Version loaded",
          description: "Review the restored version and save to keep it.",
        });
      } catch (error) {
        toast({
          title: "Failed to restore version",
          description:
            error instanceof Error ? error.message : "Unknown error occurred",
          variant: "destructive",
        });
      }
    },
    [applySnapshot, convertPersistedNodesToCanvas, currentWorkflowId],
  );

  // Handle new connections between nodes
  const onConnect = useCallback(
    (params: Connection) => {
      const edgeId = `edge-${params.source}-${params.target}`;
      const connectionExists = edges.some(
        (edge) =>
          edge.source === params.source && edge.target === params.target,
      );

      if (!connectionExists) {
        setEdges((eds) =>
          addEdge(
            {
              ...params,
              id: edgeId,
              animated: false,
              type: "default",
              markerEnd: {
                type: MarkerType.ArrowClosed,
                width: 12,
                height: 12,
              },
              style: { stroke: "#99a1b3", strokeWidth: 2 },
            },
            eds,
          ),
        );
      }
    },
    [edges, setEdges],
  );

  // Handle node selection
  const onNodeClick = useCallback((event: React.MouseEvent) => {
    if (event.detail === 1) {
      // No-op for single clicks; double clicks handled separately
    }
  }, []);

  // Handle node double click for inspection
  const onNodeDoubleClick = useCallback(
    (_: React.MouseEvent, node: CanvasNode) => {
      // Ignore double-clicks on Start and End nodes
      if (node.type === "startEnd") {
        return;
      }
      setSelectedNodeId(node.id);
    },
    [],
  );

  // Handle drag over for dropping new nodes
  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  // Handle drop for creating new nodes
  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();

      if (!reactFlowWrapper.current || !reactFlowInstance.current) return;

      const reactFlowBounds = reactFlowWrapper.current.getBoundingClientRect();
      const nodeData = event.dataTransfer.getData("application/reactflow");

      if (!nodeData) return;

      try {
        const node = JSON.parse(nodeData) as SidebarNodeDefinition;

        // Get the position where the node was dropped
        const position = reactFlowInstance.current.project({
          x: event.clientX - reactFlowBounds.left,
          y: event.clientY - reactFlowBounds.top,
        });

        const nodeType = determineNodeType(node.id);

        const baseDataRest: Partial<NodeData> = isRecord(node.data)
          ? { ...(node.data as Partial<NodeData>) }
          : {};
        delete baseDataRest.icon;
        delete baseDataRest.onOpenChat;
        const semanticType =
          nodeType === "startEnd"
            ? node.id === "start-node"
              ? "start"
              : "end"
            : typeof node.type === "string" && node.type.length > 0
              ? node.type
              : typeof baseDataRest.type === "string" &&
                  baseDataRest.type.length > 0
                ? baseDataRest.type
                : "default";
        const baseLabel =
          typeof node.name === "string" && node.name.length > 0
            ? node.name
            : typeof baseDataRest.label === "string" &&
                baseDataRest.label.length > 0
              ? baseDataRest.label
              : DEFAULT_NODE_LABEL;
        const allocateIdentity = createIdentityAllocator(nodesRef.current);
        const { id: nodeId, label } = allocateIdentity(baseLabel);
        const description =
          typeof node.description === "string" && node.description.length > 0
            ? node.description
            : typeof baseDataRest.description === "string"
              ? baseDataRest.description
              : "";
        if (nodeType === "stickyNote") {
          const stickyNode: CanvasNode = {
            id: nodeId,
            type: "stickyNote",
            position,
            style: defaultNodeStyle,
            data: {
              ...baseDataRest,
              label,
              description,
              type: semanticType,
              status: "idle" as NodeStatus,
              color: isStickyNoteColor(baseDataRest.color)
                ? (baseDataRest.color as StickyNoteColor)
                : DEFAULT_STICKY_NOTE_COLOR,
              content: sanitizeStickyNoteContent(baseDataRest.content),
              width: sanitizeStickyNoteDimension(
                baseDataRest.width,
                DEFAULT_STICKY_NOTE_WIDTH,
                STICKY_NOTE_MIN_WIDTH,
              ),
              height: sanitizeStickyNoteDimension(
                baseDataRest.height,
                DEFAULT_STICKY_NOTE_HEIGHT,
                STICKY_NOTE_MIN_HEIGHT,
              ),
              onUpdateStickyNote: handleUpdateStickyNoteNode,
            },
            draggable: true,
            connectable: false,
          };

          setNodes((nds) => nds.concat(stickyNode));
          return;
        }

        const rawIconKey =
          typeof node.iconKey === "string"
            ? node.iconKey
            : typeof baseDataRest.iconKey === "string"
              ? baseDataRest.iconKey
              : undefined;
        const finalIconKey =
          inferNodeIconKey({
            iconKey: rawIconKey,
            label,
            type: semanticType,
          }) ?? rawIconKey;
        const iconNode = getNodeIcon(finalIconKey) ?? node.icon;

        const newNode: CanvasNode = {
          id: nodeId,
          type: nodeType,
          position,
          style: defaultNodeStyle,
          data: {
            ...baseDataRest,
            label,
            description,
            type: semanticType,
            status: "idle" as NodeStatus,
            iconKey: finalIconKey,
            icon: iconNode,
            onOpenChat:
              nodeType === "chatTrigger"
                ? () => handleOpenChat(nodeId)
                : undefined,
          },
          draggable: true,
        };

        // Add the new node to the canvas
        setNodes((nds) => nds.concat(newNode));
      } catch (error) {
        console.error("Error adding new node:", error);
      }
    },
    [handleOpenChat, handleUpdateStickyNoteNode, setNodes],
  );

  // Handle adding a node by clicking
  const handleAddNode = useCallback(
    (node: SidebarNodeDefinition) => {
      if (!reactFlowInstance.current) return;

      const nodeType = determineNodeType(node.id);
      const baseDataRest: Partial<NodeData> = isRecord(node.data)
        ? { ...(node.data as Partial<NodeData>) }
        : {};
      delete baseDataRest.icon;
      delete baseDataRest.onOpenChat;

      // Calculate a position for the new node
      const position = {
        x: Math.random() * 300 + 100,
        y: Math.random() * 300 + 100,
      };

      const semanticType =
        nodeType === "startEnd"
          ? node.id === "start-node"
            ? "start"
            : "end"
          : typeof node.type === "string" && node.type.length > 0
            ? node.type
            : typeof baseDataRest.type === "string" &&
                baseDataRest.type.length > 0
              ? baseDataRest.type
              : "default";
      const baseLabel =
        typeof node.name === "string" && node.name.length > 0
          ? node.name
          : typeof baseDataRest.label === "string" &&
              baseDataRest.label.length > 0
            ? baseDataRest.label
            : DEFAULT_NODE_LABEL;
      const allocateIdentity = createIdentityAllocator(nodesRef.current);
      const { id: nodeId, label: uniqueLabel } = allocateIdentity(baseLabel);
      const description =
        typeof node.description === "string" && node.description.length > 0
          ? node.description
          : typeof baseDataRest.description === "string"
            ? baseDataRest.description
            : "";
      if (nodeType === "stickyNote") {
        const stickyNode: CanvasNode = {
          id: nodeId,
          type: "stickyNote",
          position,
          style: defaultNodeStyle,
          data: {
            ...baseDataRest,
            type: semanticType,
            label: uniqueLabel,
            description,
            status: "idle" as NodeStatus,
            color: isStickyNoteColor(baseDataRest.color)
              ? (baseDataRest.color as StickyNoteColor)
              : DEFAULT_STICKY_NOTE_COLOR,
            content: sanitizeStickyNoteContent(baseDataRest.content),
            width: sanitizeStickyNoteDimension(
              baseDataRest.width,
              DEFAULT_STICKY_NOTE_WIDTH,
              STICKY_NOTE_MIN_WIDTH,
            ),
            height: sanitizeStickyNoteDimension(
              baseDataRest.height,
              DEFAULT_STICKY_NOTE_HEIGHT,
              STICKY_NOTE_MIN_HEIGHT,
            ),
            onUpdateStickyNote: handleUpdateStickyNoteNode,
          },
          draggable: true,
          connectable: false,
        };

        setNodes((nds) => [...nds, stickyNode]);
        return;
      }

      const rawIconKey =
        typeof node.iconKey === "string"
          ? node.iconKey
          : typeof baseDataRest.iconKey === "string"
            ? baseDataRest.iconKey
            : undefined;
      const finalIconKey =
        inferNodeIconKey({
          iconKey: rawIconKey,
          label: uniqueLabel,
          type: semanticType,
        }) ?? rawIconKey;
      const iconNode = getNodeIcon(finalIconKey) ?? node.icon;

      const newNode: Node<NodeData> = {
        id: nodeId,
        type: nodeType,
        position,
        style: defaultNodeStyle,
        data: {
          ...baseDataRest,
          type: semanticType,
          label: uniqueLabel,
          description,
          status: "idle" as NodeStatus,
          iconKey: finalIconKey,
          icon: iconNode,
          onOpenChat:
            nodeType === "chatTrigger"
              ? () => handleOpenChat(nodeId)
              : undefined,
        },
        draggable: true,
      };

      // Add the new node to the canvas
      setNodes((nds) => [...nds, newNode]);
    },
    [handleOpenChat, handleUpdateStickyNoteNode, setNodes],
  );

  // Handle chat message sending
  const handleChatResponseStart = useCallback(() => {
    if (!activeChatNodeId) {
      return;
    }

    setNodes((nds) =>
      nds.map((node) =>
        node.id === activeChatNodeId
          ? {
              ...node,
              data: {
                ...node.data,
                status: "running" as NodeStatus,
              },
            }
          : node,
      ),
    );
  }, [activeChatNodeId, setNodes]);

  const handleChatResponseEnd = useCallback(() => {
    if (!activeChatNodeId) {
      return;
    }

    setNodes((nds) =>
      nds.map((node) =>
        node.id === activeChatNodeId
          ? {
              ...node,
              data: {
                ...node.data,
                status: "success" as NodeStatus,
              },
            }
          : node,
      ),
    );
  }, [activeChatNodeId, setNodes]);

  const handleChatClientTool = useCallback(
    async (toolCall: { name: string; params: Record<string, unknown> }) => {
      if (!activeChatNodeId || toolCall.name !== "orcheo.run_workflow") {
        return {};
      }

      if (!workflowId) {
        throw new Error("Cannot trigger workflow without a workflow ID");
      }

      const params = toolCall.params ?? {};
      const rawMessage =
        typeof params.message === "string" ? params.message : "";
      const threadId =
        typeof params.threadId === "string"
          ? params.threadId
          : typeof params.thread_id === "string"
            ? params.thread_id
            : null;

      const metadata = { ...(params as Record<string, unknown>) };
      delete metadata.message;
      delete metadata.threadId;
      delete metadata.thread_id;

      const response = await fetch(
        buildBackendHttpUrl(
          `/api/chatkit/workflows/${workflowId}/trigger`,
          backendBaseUrl,
        ),
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            message: rawMessage,
            actor: user.name,
            client_thread_id: threadId,
            metadata,
          }),
        },
      );

      if (!response.ok) {
        throw new Error("Failed to trigger workflow via ChatKit client tool");
      }

      const result = await response.json();

      return result;
    },
    [activeChatNodeId, backendBaseUrl, user.name, workflowId],
  );

  // Handle workflow execution
  const handleRunWorkflow = useCallback(async () => {
    if (nodes.length === 0) {
      toast({
        title: "Add nodes before running",
        description: "Create at least one node to build a runnable workflow.",
        variant: "destructive",
      });
      return;
    }

    const { config, graphToCanvas, warnings } =
      await buildGraphConfigFromCanvas(nodes, edges);

    if (warnings.length > 0) {
      warnings.forEach((message) => {
        toast({
          title: "Workflow configuration warning",
          description: message,
        });
      });
    }
    const executionId = generateRandomId("run");
    const startTime = new Date();

    const executionNodes: WorkflowExecutionNode[] = nodes.map((node) => ({
      id: node.id,
      type:
        typeof node.data?.type === "string"
          ? node.data.type
          : (node.type ?? "custom"),
      name:
        typeof node.data?.label === "string" && node.data.label.trim()
          ? node.data.label
          : node.id,
      position: node.position,
      status: "running",
      iconKey:
        typeof node.data?.iconKey === "string" ? node.data.iconKey : undefined,
    }));

    const executionEdges: WorkflowEdge[] = edges.map((edge) => ({
      id: edge.id ?? generateRandomId("edge"),
      source: edge.source,
      target: edge.target,
    }));

    const initialLog = {
      timestamp: startTime.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      }),
      level: "INFO" as const,
      message: "Workflow execution started",
    };

    const executionRecord: WorkflowExecution = {
      id: executionId,
      runId: executionId,
      status: "running",
      startTime: startTime.toISOString(),
      duration: 0,
      issues: 0,
      nodes: executionNodes,
      edges: executionEdges,
      logs: [initialLog],
      metadata: { graphToCanvas },
    };

    setExecutions((prev) => [executionRecord, ...prev]);
    setActiveExecutionId(executionId);
    setIsRunning(true);
    setNodes((prev) =>
      prev.map((node) => ({
        ...node,
        data: { ...node.data, status: "running" as NodeStatus },
      })),
    );

    if (websocketRef.current) {
      websocketRef.current.close();
      websocketRef.current = null;
    }

    let websocketUrl: string;
    try {
      websocketUrl = buildWorkflowWebSocketUrl(
        currentWorkflowId ?? "canvas-preview",
        getBackendBaseUrl(),
      );
    } catch (error) {
      setIsRunning(false);
      toast({
        title: "Unable to start execution",
        description:
          error instanceof Error
            ? error.message
            : "Invalid workflow identifier",
        variant: "destructive",
      });
      return;
    }

    const ws = new WebSocket(websocketUrl);
    websocketRef.current = ws;

    ws.onopen = () => {
      const payload = {
        type: "run_workflow",
        graph_config: config,
        inputs: {
          canvas: {
            triggered_from: "canvas-app",
            workflow_id: currentWorkflowId ?? "canvas-preview",
            at: startTime.toISOString(),
          },
          metadata: {
            node_count: nodes.length,
            edge_count: edges.length,
          },
        },
        execution_id: executionId,
      };
      ws.send(JSON.stringify(payload));
    };

    ws.onmessage = (event) => {
      if (!isMountedRef.current) {
        return;
      }
      try {
        const data = JSON.parse(event.data) as Record<string, unknown>;
        applyExecutionUpdate(executionId, data, graphToCanvas);
      } catch (error) {
        console.error("Failed to parse workflow update", error);
        toast({
          title: "Workflow update error",
          description:
            error instanceof Error ? error.message : "Unknown parsing error",
          variant: "destructive",
        });
      }
    };

    ws.onerror = () => {
      if (!isMountedRef.current) {
        return;
      }
      const timestamp = new Date();
      setIsRunning(false);
      setExecutions((prev) =>
        prev.map((execution) => {
          if (execution.id !== executionId) {
            return execution;
          }
          const errorLog = {
            timestamp: timestamp.toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
            }),
            level: "ERROR" as const,
            message: "WebSocket connection reported an error.",
          };
          const updatedNodes = execution.nodes.map((node) =>
            node.status === "running"
              ? { ...node, status: "error" as NodeStatus }
              : node,
          );
          return {
            ...execution,
            status:
              execution.status === "success" ? execution.status : "failed",
            nodes: updatedNodes,
            logs: [...execution.logs, errorLog],
            endTime: execution.endTime ?? timestamp.toISOString(),
            duration:
              timestamp.getTime() - new Date(execution.startTime).getTime(),
            issues: execution.issues + 1,
          };
        }),
      );
      toast({
        title: "Workflow stream error",
        description: "The WebSocket connection reported an error.",
        variant: "destructive",
      });
      if (websocketRef.current === ws) {
        websocketRef.current.close();
        websocketRef.current = null;
      }
    };

    ws.onclose = () => {
      if (!isMountedRef.current) {
        return;
      }
      setIsRunning(false);
      if (websocketRef.current === ws) {
        websocketRef.current = null;
      }
    };
  }, [
    nodes,
    edges,
    setNodes,
    setExecutions,
    applyExecutionUpdate,
    currentWorkflowId,
  ]);

  // Handle workflow pause
  const handlePauseWorkflow = useCallback(() => {
    if (!isRunning) {
      return;
    }

    setIsRunning(false);
    if (websocketRef.current) {
      websocketRef.current.close();
      websocketRef.current = null;
    }

    const timestamp = new Date();

    setNodes((nds) =>
      nds.map((node) => {
        if (node.data.status === "running") {
          return {
            ...node,
            data: { ...node.data, status: "warning" as NodeStatus },
          };
        }
        return node;
      }),
    );

    if (activeExecutionId) {
      setExecutions((prev) =>
        prev.map((execution) => {
          if (execution.id !== activeExecutionId) {
            return execution;
          }
          return {
            ...execution,
            status: "partial",
            endTime: timestamp.toISOString(),
            duration:
              timestamp.getTime() - new Date(execution.startTime).getTime(),
            logs: [
              ...execution.logs,
              {
                timestamp: timestamp.toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                }),
                level: "WARNING" as const,
                message: "Execution paused from the canvas",
              },
            ],
          };
        }),
      );
    }

    toast({
      title: "Workflow paused",
      description: "Live updates disconnected. Resume to reconnect.",
    });
  }, [activeExecutionId, isRunning, setExecutions, setNodes]);

  const handleUndo = useCallback(() => {
    const previousSnapshot = undoStackRef.current.pop();
    if (!previousSnapshot) {
      return;
    }
    const currentSnapshot = createSnapshot();
    redoStackRef.current = [...redoStackRef.current, currentSnapshot].slice(
      -HISTORY_LIMIT,
    );
    applySnapshot(previousSnapshot);
    setCanUndo(undoStackRef.current.length > 0);
    setCanRedo(true);
  }, [applySnapshot, createSnapshot]);

  const handleRedo = useCallback(() => {
    const nextSnapshot = redoStackRef.current.pop();
    if (!nextSnapshot) {
      return;
    }
    const currentSnapshot = createSnapshot();
    undoStackRef.current = [...undoStackRef.current, currentSnapshot].slice(
      -HISTORY_LIMIT,
    );
    applySnapshot(nextSnapshot);
    setCanRedo(redoStackRef.current.length > 0);
    setCanUndo(true);
  }, [applySnapshot, createSnapshot]);

  useEffect(() => {
    const targetDocument =
      typeof document !== "undefined" ? document : undefined;
    if (!targetDocument) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const isEditable =
        !!target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable);

      if (
        (event.key === "Delete" || event.key === "Backspace") &&
        !isEditable
      ) {
        const selectedIds = nodesRef.current
          .filter((node) => node.selected)
          .map((node) => node.id);
        if (selectedIds.length > 0) {
          event.preventDefault();
          deleteNodes(selectedIds);
          return;
        }
      }

      if (!(event.ctrlKey || event.metaKey)) {
        return;
      }

      const key = event.key.toLowerCase();

      if ((key === "c" || key === "x" || key === "v") && isEditable) {
        return;
      }

      if (key === "c") {
        event.preventDefault();
        void copySelectedNodes();
        return;
      }

      if (key === "x") {
        event.preventDefault();
        void cutSelectedNodes();
        return;
      }

      if (key === "v") {
        event.preventDefault();
        void pasteNodes();
        return;
      }

      if (key === "f") {
        event.preventDefault();
        setIsSearchOpen(true);
        setSearchMatches([]);
        setCurrentSearchIndex(0);
        return;
      }

      if (key === "z") {
        event.preventDefault();
        if (event.shiftKey) {
          handleRedo();
        } else {
          handleUndo();
        }
        return;
      }

      if (key === "y") {
        event.preventDefault();
        handleRedo();
      }
    };

    targetDocument.addEventListener("keydown", handleKeyDown);
    return () => targetDocument.removeEventListener("keydown", handleKeyDown);
  }, [
    deleteNodes,
    handleRedo,
    handleUndo,
    copySelectedNodes,
    cutSelectedNodes,
    pasteNodes,
    setCurrentSearchIndex,
    setIsSearchOpen,
    setSearchMatches,
  ]);

  // Handle node inspector close
  const handleCloseNodeInspector = useCallback(() => {
    setSelectedNodeId(null);
  }, []);

  const handleCacheNodeRuntime = useCallback(
    (nodeId: string, runtime: NodeRuntimeCacheEntry) => {
      setNodeRuntimeCache((current) => ({ ...current, [nodeId]: runtime }));
    },
    [],
  );

  // Handle node update from inspector
  const handleNodeUpdate = useCallback(
    (nodeId: string, data: Partial<NodeData>) => {
      const currentNodes = nodesRef.current;
      const currentEdges = edgesRef.current;

      const targetNode = currentNodes.find((node) => node.id === nodeId);
      if (!targetNode) {
        return;
      }

      const desiredLabelInput =
        data.label !== undefined
          ? data.label
          : (targetNode.data?.label as string | undefined);
      const desiredLabel = sanitizeLabel(desiredLabelInput);
      const allocateIdentity = createIdentityAllocator(currentNodes, {
        excludeId: nodeId,
      });
      const { id: newId, label: uniqueLabel } = allocateIdentity(desiredLabel);

      const nextStatus =
        (data.status as NodeStatus | undefined) ||
        (targetNode.data?.status as NodeStatus | undefined) ||
        ("idle" as NodeStatus);

      const nextData: NodeData = {
        ...(targetNode.data as NodeData),
        ...data,
        label: uniqueLabel,
        status: nextStatus,
      };

      if (targetNode.type === "chatTrigger") {
        nextData.onOpenChat = () => handleOpenChat(newId);
      }

      const updatedNodes = currentNodes.map((node) =>
        node.id === nodeId
          ? ({
              ...node,
              id: newId,
              data: nextData,
            } as CanvasNode)
          : node,
      );

      const updatedEdges = currentEdges.map((edge) => {
        let modified = false;
        const nextEdge = { ...edge };
        if (edge.source === nodeId) {
          nextEdge.source = newId;
          modified = true;
        }
        if (edge.target === nodeId) {
          nextEdge.target = newId;
          modified = true;
        }
        return modified ? nextEdge : edge;
      });

      isRestoringRef.current = true;
      recordSnapshot({ force: true });
      try {
        setNodesState(updatedNodes);
        setEdgesState(updatedEdges);
      } catch (error) {
        isRestoringRef.current = false;
        throw error;
      }

      setValidationErrors((errors) =>
        errors.map((error) => {
          let modified = false;
          const nextError = { ...error };
          if (error.nodeId === nodeId) {
            nextError.nodeId = newId;
            modified = true;
          }
          if (error.sourceId === nodeId) {
            nextError.sourceId = newId;
            modified = true;
          }
          if (error.targetId === nodeId) {
            nextError.targetId = newId;
            modified = true;
          }
          return modified ? nextError : error;
        }),
      );

      setSearchMatches((matches) =>
        matches.map((match) => (match === nodeId ? newId : match)),
      );

      setActiveChatNodeId((current) => (current === nodeId ? newId : current));

      setChatTitle((title) =>
        activeChatNodeId === nodeId ? uniqueLabel : title,
      );

      if (desiredLabel !== uniqueLabel) {
        toast({
          title: "Adjusted node name",
          description: `Renamed to "${uniqueLabel}" to keep names unique.`,
        });
      }

      setSelectedNodeId(null);
    },
    [
      activeChatNodeId,
      handleOpenChat,
      recordSnapshot,
      setActiveChatNodeId,
      setChatTitle,
      setEdgesState,
      setSelectedNodeId,
      setValidationErrors,
      setNodesState,
      setSearchMatches,
    ],
  );

  // Handle execution selection
  const handleViewExecutionDetails = useCallback(
    (execution: HistoryWorkflowExecution) => {
      const mappedNodes = execution.nodes.map(
        (node) =>
          ({
            id: node.id,
            type: node.type || "default",
            position: node.position,
            data: {
              type: node.type || "default",
              label: node.name,
              status: node.status || ("idle" as const),
              details: node.details,
            } as NodeData,
            draggable: true,
          }) as Node<NodeData>,
      );
      setNodes(mappedNodes);
      setActiveExecutionId(execution.id);
    },
    [setNodes],
  );

  const handleCopyExecutionToEditor = useCallback(
    (execution: HistoryWorkflowExecution) => {
      handleViewExecutionDetails(execution);
      toast({
        title: "Execution copied to canvas",
        description: `Run ${execution.runId} was loaded into the editor.`,
      });
    },
    [handleViewExecutionDetails],
  );

  const handleDeleteExecution = useCallback(
    (execution: HistoryWorkflowExecution) => {
      setExecutions((prev) => prev.filter((item) => item.id !== execution.id));
      if (activeExecutionId === execution.id) {
        setActiveExecutionId(null);
      }
      toast({
        title: "Execution removed",
        description: `Run ${execution.runId} was removed from the history view.`,
      });
    },
    [activeExecutionId, setExecutions],
  );

  const handleRefreshExecutionHistory = useCallback(async () => {
    if (typeof fetch === "undefined") {
      toast({
        title: "Refresh unavailable",
        description: "The Fetch API is not available in this environment.",
        variant: "destructive",
      });
      return;
    }

    const targetExecution =
      (activeExecutionId &&
        executions.find((execution) => execution.id === activeExecutionId)) ||
      executions[0];

    if (!targetExecution) {
      toast({
        title: "No executions to refresh",
        description: "Run a workflow to create live execution history.",
      });
      return;
    }

    const url = buildBackendHttpUrl(
      `/api/executions/${targetExecution.id}/history`,
    );

    try {
      const response = await fetch(url);
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(
          detail || `Request failed with status ${response.status}`,
        );
      }

      const history = (await response.json()) as RunHistoryResponse;
      const mapping = targetExecution.metadata?.graphToCanvas ?? {};

      const logs = history.steps.map((step) => ({
        timestamp: new Date(step.at).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        }),
        level: determineLogLevel(step.payload),
        message: describePayload(step.payload, mapping),
      }));

      setExecutions((prev) =>
        prev.map((execution) => {
          if (execution.id !== history.execution_id) {
            return execution;
          }
          const status =
            executionStatusFromValue(history.status) ?? execution.status;
          const completedAt = history.completed_at ?? execution.endTime;
          return {
            ...execution,
            status,
            logs,
            endTime: completedAt ?? undefined,
            duration: completedAt
              ? new Date(completedAt).getTime() -
                new Date(history.started_at).getTime()
              : execution.duration,
          };
        }),
      );

      toast({
        title: "Execution history refreshed",
        description: `Loaded ${history.steps.length} streamed updates.`,
      });
    } catch (error) {
      toast({
        title: "Failed to refresh execution history",
        description:
          error instanceof Error ? error.message : "Unknown error occurred",
        variant: "destructive",
      });
    }
  }, [
    activeExecutionId,
    executions,
    determineLogLevel,
    describePayload,
    setExecutions,
  ]);

  // Load workflow data when workflowId changes
  useEffect(() => {
    let isMounted = true;

    const resetToBlankWorkflow = () => {
      setCurrentWorkflowId(null);
      setWorkflowName("New Workflow");
      setWorkflowDescription("");
      setWorkflowTags(["draft"]);
      setWorkflowVersions([]);
      setExecutions([]);
      if (nodesRef.current.length === 0 && edgesRef.current.length === 0) {
        applySnapshot({ nodes: [], edges: [] }, { resetHistory: true });
      } else {
        undoStackRef.current = [];
        redoStackRef.current = [];
        setCanUndo(false);
        setCanRedo(false);
      }
    };

    const loadWorkflow = async () => {
      if (!workflowId) {
        if (isMounted) {
          resetToBlankWorkflow();
        }
        return;
      }

      try {
        const persisted = await getWorkflowById(workflowId);
        if (persisted && isMounted) {
          setCurrentWorkflowId(persisted.id);
          setWorkflowName(persisted.name);
          setWorkflowDescription(persisted.description ?? "");
          setWorkflowTags(persisted.tags ?? ["draft"]);
          setWorkflowVersions(persisted.versions ?? []);
          const canvasNodes = convertPersistedNodesToCanvas(
            persisted.nodes ?? [],
          );
          const canvasEdges = convertPersistedEdgesToCanvas(
            persisted.edges ?? [],
          );
          applySnapshot(
            { nodes: canvasNodes, edges: canvasEdges },
            { resetHistory: true },
          );
          try {
            const history = await loadWorkflowExecutions(workflowId, {
              workflow: persisted,
            });
            if (isMounted) {
              setExecutions(history);
            }
          } catch (historyError) {
            if (isMounted) {
              setExecutions([]);
              toast({
                title: "Failed to load execution history",
                description:
                  historyError instanceof Error
                    ? historyError.message
                    : "Unable to retrieve workflow runs.",
                variant: "destructive",
              });
            }
            console.error("Failed to load workflow executions", historyError);
          }
          return;
        }
      } catch (error) {
        if (isMounted) {
          toast({
            title: "Failed to load workflow",
            description:
              error instanceof Error ? error.message : "Unknown error occurred",
            variant: "destructive",
          });
          setExecutions([]);
        }
      }

      if (!isMounted) {
        return;
      }

      const template = SAMPLE_WORKFLOWS.find((w) => w.id === workflowId);
      if (template) {
        setCurrentWorkflowId(null);
        setWorkflowName(template.name);
        setWorkflowDescription(template.description ?? "");
        setWorkflowTags(template.tags.filter((tag) => tag !== "template"));
        setWorkflowVersions([]);
        setExecutions([]);
        const canvasNodes = convertPersistedNodesToCanvas(template.nodes);
        const canvasEdges = convertPersistedEdgesToCanvas(template.edges);
        applySnapshot(
          { nodes: canvasNodes, edges: canvasEdges },
          { resetHistory: true },
        );
        toast({
          title: "Template loaded",
          description: "Save to add this workflow to your workspace.",
        });
        return;
      }

      toast({
        title: "Workflow not found",
        description: "Starting a new workflow instead.",
        variant: "destructive",
      });
      resetToBlankWorkflow();
    };

    void loadWorkflow();

    return () => {
      isMounted = false;
    };
  }, [applySnapshot, convertPersistedNodesToCanvas, workflowId]);

  useEffect(() => {
    if (!currentWorkflowId) {
      return;
    }

    const targetWindow = typeof window !== "undefined" ? window : undefined;
    if (!targetWindow) {
      return;
    }

    const handleStorageUpdate = async () => {
      try {
        const updated = await getWorkflowById(currentWorkflowId);
        if (updated) {
          setWorkflowVersions(updated.versions ?? []);
          setWorkflowTags(updated.tags ?? ["draft"]);
        }
      } catch (error) {
        console.error("Failed to reload workflow", error);
      }
    };

    targetWindow.addEventListener(WORKFLOW_STORAGE_EVENT, handleStorageUpdate);
    return () => {
      targetWindow.removeEventListener(
        WORKFLOW_STORAGE_EVENT,
        handleStorageUpdate,
      );
    };
  }, [currentWorkflowId]);

  // Fit view on initial render
  useEffect(() => {
    setTimeout(() => {
      if (reactFlowInstance.current) {
        reactFlowInstance.current.fitView({ padding: 0.2 });
      }
    }, 100);
  }, []);

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <TopNavigation
        currentWorkflow={{
          name: workflowName,
          path: ["Projects", "Workflows", workflowName],
        }}
        credentials={credentials}
        isCredentialsLoading={isCredentialsLoading}
        onAddCredential={handleAddCredential}
        onDeleteCredential={handleDeleteCredential}
      />

      <WorkflowTabs
        activeTab={activeTab}
        onTabChange={setActiveTab}
        readinessAlertCount={validationErrors.length}
      />

      <div className="flex-1 flex flex-col min-h-0">
        <Tabs
          value={activeTab}
          onValueChange={setActiveTab}
          className="w-full flex flex-col flex-1 min-h-0"
        >
          <TabsContent
            value="canvas"
            className="flex-1 m-0 p-0 overflow-hidden min-h-0"
          >
            <div className="flex h-full min-h-0">
              <SidebarPanel
                isCollapsed={sidebarCollapsed}
                onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
                onAddNode={handleAddNode}
              />

              <div
                ref={reactFlowWrapper}
                className="relative flex-1 h-full min-h-0"
                onDragOver={onDragOver}
                onDrop={onDrop}
              >
                <EdgeHoverContext.Provider value={edgeHoverContextValue}>
                  <WorkflowFlow
                    nodes={decoratedNodes}
                    edges={edges}
                    onNodesChange={handleNodesChange}
                    onEdgesChange={handleEdgesChange}
                    onConnect={onConnect}
                    onNodeClick={onNodeClick}
                    onNodeDoubleClick={onNodeDoubleClick}
                    onEdgeMouseEnter={handleEdgeMouseEnter}
                    onEdgeMouseLeave={handleEdgeMouseLeave}
                    onInit={(instance: ReactFlowInstance) => {
                      reactFlowInstance.current = instance;
                    }}
                    fitView
                    snapToGrid
                    snapGrid={[15, 15]}
                    editable={true}
                  >
                    <WorkflowSearch
                      isOpen={isSearchOpen}
                      onSearch={handleSearchNodes}
                      onHighlightNext={handleHighlightNext}
                      onHighlightPrevious={handleHighlightPrevious}
                      onClose={handleCloseSearch}
                      matchCount={searchMatches.length}
                      currentMatchIndex={currentSearchIndex}
                      className="backdrop-blur supports-[backdrop-filter]:bg-background/60"
                    />

                    <Panel position="top-left" className="m-4">
                      <WorkflowControls
                        isRunning={isRunning}
                        onRun={handleRunWorkflow}
                        onPause={handlePauseWorkflow}
                        onSave={handleSaveWorkflow}
                        onUndo={handleUndo}
                        onRedo={handleRedo}
                        canUndo={canUndo}
                        canRedo={canRedo}
                        onDuplicate={handleDuplicateSelectedNodes}
                        onExport={handleExportWorkflow}
                        onImport={handleImportWorkflow}
                        onToggleSearch={handleToggleSearch}
                        isSearchOpen={isSearchOpen}
                      />
                    </Panel>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="application/json"
                      className="hidden"
                      onChange={handleWorkflowFileSelected}
                    />
                  </WorkflowFlow>
                </EdgeHoverContext.Provider>
                <ConnectionValidator
                  errors={validationErrors}
                  onDismiss={handleDismissValidation}
                  onFix={handleFixValidation}
                />
              </div>
            </div>
          </TabsContent>

          <TabsContent
            value="execution"
            className="flex-1 m-0 p-0 overflow-hidden min-h-0"
          >
            <WorkflowExecutionHistory
              executions={executions}
              onViewDetails={handleViewExecutionDetails}
              onRefresh={handleRefreshExecutionHistory}
              onCopyToEditor={handleCopyExecutionToEditor}
              onDelete={handleDeleteExecution}
              defaultSelectedExecution={executions[0]}
            />
          </TabsContent>

          <TabsContent value="readiness" className="m-0 p-4 overflow-auto">
            <div className="mx-auto max-w-5xl pb-12">
              <WorkflowGovernancePanel
                subworkflows={subworkflows}
                onCreateSubworkflow={handleCreateSubworkflow}
                onInsertSubworkflow={handleInsertSubworkflow}
                onDeleteSubworkflow={handleDeleteSubworkflow}
                validationErrors={validationErrors}
                onRunValidation={runPublishValidation}
                onDismissValidation={handleDismissValidation}
                onFixValidation={handleFixValidation}
                isValidating={isValidating}
                lastValidationRun={lastValidationRun}
              />
            </div>
          </TabsContent>

          <TabsContent value="settings" className="m-0 p-4 overflow-auto">
            <div className="max-w-3xl mx-auto space-y-8">
              <div>
                <h2 className="text-xl font-bold mb-4">Workflow Settings</h2>
                <div className="space-y-4">
                  <div className="grid gap-2">
                    <label className="text-sm font-medium">Workflow Name</label>
                    <input
                      type="text"
                      className="border border-border rounded-md px-3 py-2 bg-background"
                      value={workflowName}
                      onChange={(e) => setWorkflowName(e.target.value)}
                    />
                  </div>
                  <div className="grid gap-2">
                    <label className="text-sm font-medium">Description</label>
                    <textarea
                      className="border border-border rounded-md px-3 py-2 bg-background"
                      rows={3}
                      value={workflowDescription}
                      onChange={(event) =>
                        setWorkflowDescription(event.target.value)
                      }
                    />
                  </div>
                  <div className="grid gap-2">
                    <label className="text-sm font-medium">Tags</label>
                    <input
                      type="text"
                      className="border border-border rounded-md px-3 py-2 bg-background"
                      value={workflowTags.join(", ")}
                      onChange={(event) => handleTagsChange(event.target.value)}
                    />

                    <p className="text-xs text-muted-foreground">
                      Separate tags with commas
                    </p>
                  </div>
                </div>
              </div>

              <Separator />

              <div>
                <h2 className="text-xl font-bold mb-4">Execution Settings</h2>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <label className="text-sm font-medium">
                        Timeout (seconds)
                      </label>
                      <p className="text-xs text-muted-foreground">
                        Maximum execution time for the workflow
                      </p>
                    </div>
                    <input
                      type="number"
                      className="border border-border rounded-md px-3 py-2 bg-background w-24"
                      defaultValue="300"
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <label className="text-sm font-medium">
                        Retry on Failure
                      </label>
                      <p className="text-xs text-muted-foreground">
                        Automatically retry the workflow if it fails
                      </p>
                    </div>
                    <div className="flex items-center h-6">
                      <input
                        type="checkbox"
                        className="h-4 w-4"
                        defaultChecked
                      />
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <label className="text-sm font-medium">
                        Maximum Retries
                      </label>
                      <p className="text-xs text-muted-foreground">
                        Number of retry attempts before giving up
                      </p>
                    </div>
                    <input
                      type="number"
                      className="border border-border rounded-md px-3 py-2 bg-background w-24"
                      defaultValue="3"
                    />
                  </div>
                </div>
              </div>

              <Separator />

              <div>
                <h2 className="text-xl font-bold mb-4">Notifications</h2>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <label className="text-sm font-medium">
                        Email Notifications
                      </label>
                      <p className="text-xs text-muted-foreground">
                        Send email when workflow fails
                      </p>
                    </div>
                    <div className="flex items-center h-6">
                      <input
                        type="checkbox"
                        className="h-4 w-4"
                        defaultChecked
                      />
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <label className="text-sm font-medium">
                        Slack Notifications
                      </label>
                      <p className="text-xs text-muted-foreground">
                        Send Slack message when workflow completes
                      </p>
                    </div>
                    <div className="flex items-center h-6">
                      <input type="checkbox" className="h-4 w-4" />
                    </div>
                  </div>
                </div>
              </div>

              <Separator />

              <WorkflowHistory
                versions={workflowVersions}
                currentVersion={workflowVersions.at(-1)?.version}
                onRestoreVersion={handleRestoreVersion}
              />

              <div className="flex justify-end gap-2">
                <Button variant="outline">Cancel</Button>
                <Button onClick={handleSaveWorkflow}>Save Settings</Button>
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </div>

      {selectedNode && (
        <NodeInspector
          node={{
            id: selectedNode.id,
            type: selectedNode.type || "default",
            data: selectedNode.data,
          }}
          nodes={nodes}
          edges={edges}
          onClose={handleCloseNodeInspector}
          onSave={handleNodeUpdate}
          runtimeCache={nodeRuntimeCache}
          onCacheRuntime={handleCacheNodeRuntime}
          className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 z-50"
        />
      )}

      {/* Chat Interface */}
      {isChatOpen && (
        <ChatInterface
          title={chatTitle}
          user={user}
          ai={ai}
          isClosable={true}
          position="bottom-right"
          initialMessages={[
            {
              id: "welcome-msg",
              content: `Welcome to the ${chatTitle} interface. How can I help you today?`,
              sender: {
                ...ai,
                isAI: true,
              },
              timestamp: new Date(),
            },
          ]}
          backendBaseUrl={getBackendBaseUrl()}
          sessionPayload={{
            workflowId: activeChatNodeId,
            workflowLabel: chatTitle,
          }}
          onResponseStart={handleChatResponseStart}
          onResponseEnd={handleChatResponseEnd}
          chatkitOptions={{
            composer: {
              placeholder: `Send a message to ${chatTitle}`,
            },
            onClientTool: handleChatClientTool,
          }}
        />
      )}
    </div>
  );
}
