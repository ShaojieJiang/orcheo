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
  ReactFlow,
  Background,
  Controls,
  Panel,
  addEdge,
  useNodesState,
  useEdgesState,
  MarkerType,
  ConnectionLineType,
  MiniMap,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { Button } from "@/design-system/ui/button";
import { Tabs, TabsContent } from "@/design-system/ui/tabs";
import { Separator } from "@/design-system/ui/separator";
import { Badge } from "@/design-system/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/design-system/ui/alert";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/design-system/ui/select";

import TopNavigation from "@features/shared/components/top-navigation";
import SidebarPanel from "@features/workflow/components/panels/sidebar-panel";
import WorkflowNode from "@features/workflow/components/nodes/workflow-node";
import WorkflowControls from "@features/workflow/components/canvas/workflow-controls";
import WorkflowSearch from "@features/workflow/components/canvas/workflow-search";
import NodeInspector from "@features/workflow/components/panels/node-inspector";
import ChatTriggerNode from "@features/workflow/components/nodes/chat-trigger-node";
import ChatKitInterface from "@features/shared/components/chatkit/chatkit-interface";
import {
  type ChatEnvironment,
  type ChatKitMetrics,
  type ChatKitSession,
} from "@features/shared/components/chatkit/types";
import type { Attachment } from "@features/shared/components/chat-input";
import type { ChatMessageProps } from "@features/shared/components/chat-message";
import WorkflowExecutionHistory, {
  type WorkflowExecution as HistoryWorkflowExecution,
} from "@features/workflow/components/panels/workflow-execution-history";
import WorkflowTabs from "@features/workflow/components/panels/workflow-tabs";
import WorkflowHistory from "@features/workflow/components/panels/workflow-history";
import StartEndNode from "@features/workflow/components/nodes/start-end-node";
import {
  SAMPLE_CREDENTIALS,
  SAMPLE_SUBWORKFLOWS,
  SAMPLE_WORKFLOWS,
  type WorkflowCredential,
  type WorkflowEdge as PersistedWorkflowEdge,
  type WorkflowNode as PersistedWorkflowNode,
} from "@features/workflow/data/workflow-data";
import { SAMPLE_CHAT_SESSIONS } from "@features/workflow/data/chat-samples";
import {
  getVersionSnapshot,
  getWorkflowById,
  saveWorkflow as persistWorkflow,
  type StoredWorkflow,
  WORKFLOW_STORAGE_EVENT,
} from "@features/workflow/lib/workflow-storage";
import {
  DEFAULT_LANGGRAPH_GRAPH_CONFIG,
  fetchExecutionHistory,
  getBackendWorkflowId,
} from "@features/workflow/lib/execution-client";
import {
  useWorkflowExecution,
  type ExecutionLogEntry,
  type ExecutionStatus,
} from "@features/workflow/hooks/use-workflow-execution";
import { toast } from "@/hooks/use-toast";
import CredentialsVault from "@features/workflow/components/dialogs/credentials-vault";
import ReusableSubworkflowLibrary from "@features/workflow/components/panels/reusable-subworkflows";
import ConnectionValidator, {
  type ValidationError,
  type ValidatorNodeData,
  validateConnection,
  validateNodeCredentials,
} from "@features/workflow/components/canvas/connection-validator";

// Define custom node types
const nodeTypes = {
  default: WorkflowNode,
  chatTrigger: ChatTriggerNode,
  startEnd: StartEndNode,
};

// Add default style to remove ReactFlow node container
const defaultNodeStyle = {
  background: "none",
  border: "none",
  padding: 0,
  borderRadius: 0,
  width: "auto",
  boxShadow: "none",
};

const EXECUTION_STATUS_LABELS: Record<ExecutionStatus, string> = {
  idle: "Idle",
  connecting: "Connecting",
  running: "Running",
  completed: "Completed",
  error: "Error",
  cancelled: "Cancelled",
};

const isFinalExecutionStatus = (status: ExecutionStatus) =>
  status === "completed" || status === "error" || status === "cancelled";

const mapBackendStatusToHistory = (
  status: ExecutionStatus,
): HistoryWorkflowExecution["status"] => {
  switch (status) {
    case "completed":
      return "success";
    case "error":
      return "failed";
    case "cancelled":
      return "partial";
    case "running":
    case "connecting":
    case "idle":
    default:
      return "running";
  }
};

const normaliseHistoryStatus = (status: string): ExecutionStatus => {
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

const computeDurationMs = (start?: string | null, end?: string | null) => {
  if (!start || !end) {
    return 0;
  }
  const startMs = new Date(start).getTime();
  const endMs = new Date(end).getTime();
  if (Number.isNaN(startMs) || Number.isNaN(endMs)) {
    return 0;
  }
  return Math.max(0, endMs - startMs);
};

const generateNodeId = () => {
  if (
    typeof globalThis.crypto !== "undefined" &&
    "randomUUID" in globalThis.crypto &&
    typeof globalThis.crypto.randomUUID === "function"
  ) {
    return `node-${globalThis.crypto.randomUUID()}`;
  }

  const timestamp = Date.now().toString(36);
  const randomSuffix = Math.random().toString(36).slice(2, 8);
  return `node-${timestamp}-${randomSuffix}`;
};

interface NodeData {
  type: string;
  label: string;
  description?: string;
  status: "idle" | "running" | "success" | "error" | "warning";
  icon?: React.ReactNode;
  onOpenChat?: () => void;
  isDisabled?: boolean;
  credentials?: {
    id?: string;
  } | null;
  [key: string]: unknown;
}

type CanvasNode = Node<NodeData>;
type CanvasEdge = Edge<Record<string, unknown>>;

type CredentialFormInput = Partial<
  Omit<WorkflowCredential, "id" | "createdAt" | "updatedAt">
> &
  Pick<WorkflowCredential, "name" | "type" | "access" | "secrets">;

const PERSISTED_NODE_FIELDS = new Set([
  "label",
  "description",
  "status",
  "type",
  "isDisabled",
]);

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

  if (
    data?.status &&
    ["idle", "running", "success", "error", "warning"].includes(data.status)
  ) {
    sanitized.status = data.status as PersistedWorkflowNode["data"]["status"];
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
      key === "icon"
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

const toCanvasNodeBase = (node: PersistedWorkflowNode): CanvasNode => {
  const extraEntries = Object.entries(node.data ?? {}).filter(
    ([key]) => !PERSISTED_NODE_FIELDS.has(key),
  );

  const extraData = Object.fromEntries(extraEntries);

  return {
    id: node.id,
    type: node.type ?? "default",
    position: node.position ?? { x: 0, y: 0 },
    style: defaultNodeStyle,
    data: {
      type: node.data?.type ?? node.type ?? "default",
      label: node.data?.label ?? "New Node",
      description: node.data?.description ?? "",
      status: (node.data?.status ?? "idle") as NodeStatus,
      isDisabled: node.data?.isDisabled,
      ...extraData,
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
  type: edge.type ?? "smoothstep",
  animated: edge.animated ?? false,
  markerEnd: {
    type: MarkerType.ArrowClosed,
    width: 20,
    height: 20,
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

const cloneNode = (node: CanvasNode): CanvasNode => ({
  ...node,
  position: node.position ? { ...node.position } : node.position,
  data: node.data ? { ...node.data } : node.data,
});

const cloneEdge = (edge: CanvasEdge): CanvasEdge => ({
  ...edge,
  data: edge.data ? { ...edge.data } : edge.data,
});

type NodeStatus = "idle" | "running" | "success" | "error" | "warning";

interface SidebarNodeDefinition {
  id?: string;
  type?: string;
  name?: string;
  description?: string;
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
  const [credentials, setCredentials] = useState<WorkflowCredential[]>(() =>
    SAMPLE_CREDENTIALS.map((credential) => ({
      ...credential,
      secrets: { ...credential.secrets },
    })),
  );
  const [linkedSubworkflows, setLinkedSubworkflows] = useState<string[]>([]);
  const [nodeCredentialAssignments, setNodeCredentialAssignments] = useState<
    Record<string, string>
  >({});
  const [validationErrors, setValidationErrors] = useState<ValidationError[]>(
    [],
  );

  // State for UI controls
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);
  const [selectedNode, setSelectedNode] = useState<CanvasNode | null>(null);
  const [activeTab, setActiveTab] = useState("canvas");
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [searchMatches, setSearchMatches] = useState<string[]>([]);
  const [currentSearchIndex, setCurrentSearchIndex] = useState(0);

  // Chat interface state
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [activeChatSessionId, setActiveChatSessionId] = useState<string | null>(
    SAMPLE_CHAT_SESSIONS[0]?.id ?? null,
  );
  const [chatEnvironment, setChatEnvironment] = useState<ChatEnvironment>(
    SAMPLE_CHAT_SESSIONS[0]?.environment ?? "draft",
  );
  const [chatSessions, setChatSessions] = useState<
    Record<string, ChatKitSession>
  >(() => {
    const initial: Record<string, ChatKitSession> = {};
    SAMPLE_CHAT_SESSIONS.forEach((session) => {
      initial[session.id] = session;
    });
    return initial;
  });
  const [chatView, setChatView] = useState<"assist" | "handoff">("assist");

  const backendWorkflowId = getBackendWorkflowId();
  const executionInputs = useMemo(
    () => ({ name: workflowName.trim() || "Canvas User" }),
    [workflowName],
  );
  const chatUserProfile = useMemo(
    () => ({
      id: "workflow-owner",
      name: "Workflow Owner",
      avatar: "https://avatar.vercel.sh/workflow-owner",
    }),
    [],
  );
  const chatAssistantProfile = useMemo(
    () => ({
      id: "assistant-default",
      name: "Workflow Copilot",
      avatar: "https://avatar.vercel.sh/workflow-copilot",
      isAI: true,
    }),
    [],
  );
  const {
    status: backendExecutionStatus,
    executionId: backendExecutionId,
    logs: backendExecutionLogs,
    tokenMetrics,
    lastError: backendExecutionError,
    startExecution,
    stopExecution,
  } = useWorkflowExecution({
    workflowId: backendWorkflowId,
    graphConfig: DEFAULT_LANGGRAPH_GRAPH_CONFIG,
    inputs: executionInputs,
  });
  const [liveExecution, setLiveExecution] =
    useState<HistoryWorkflowExecution | null>(null);
  const [liveExecutionLogs, setLiveExecutionLogs] = useState<
    ExecutionLogEntry[]
  >([]);
  const executionStartRef = useRef<string | null>(null);

  const undoStackRef = useRef<WorkflowSnapshot[]>([]);
  const redoStackRef = useRef<WorkflowSnapshot[]>([]);
  const isRestoringRef = useRef(false);
  const nodesRef = useRef<CanvasNode[]>(nodes);
  const edgesRef = useRef<CanvasEdge[]>(edges);

  const ensureCredentialsState = useCallback((items?: WorkflowCredential[]) => {
    const source = items && items.length > 0 ? items : SAMPLE_CREDENTIALS;
    setCredentials(
      source.map((credential) => ({
        ...credential,
        secrets: { ...credential.secrets },
      })),
    );
  }, []);

  const ensureLinkedSubworkflows = useCallback((ids?: string[]) => {
    setLinkedSubworkflows([...(ids ?? [])]);
  }, []);

  const rehydrateCredentialAssignments = useCallback(
    (canvasNodes: CanvasNode[]) => {
      const mapping: Record<string, string> = {};
      canvasNodes.forEach((node) => {
        const credentials =
          (node.data as NodeData & { credentials?: { id?: string } })
            .credentials ?? null;
        if (credentials?.id) {
          mapping[node.id] = credentials.id;
        }
      });
      setNodeCredentialAssignments(mapping);
    },
    [],
  );

  const handleOpenChat = useCallback(
    (nodeId: string) => {
      const chatNode = nodesRef.current.find((node) => node.id === nodeId);
      if (!chatNode) {
        return;
      }

      let resolvedEnvironment: ChatEnvironment | null = null;

      setChatSessions((prev) => {
        const existing = prev[nodeId];
        if (existing) {
          resolvedEnvironment = existing.environment;
          return {
            ...prev,
            [nodeId]: {
              ...existing,
              title: chatNode.data.label || existing.title,
              subtitle:
                typeof chatNode.data?.description === "string"
                  ? chatNode.data.description
                  : existing.subtitle,
              updatedAt: new Date().toISOString(),
            },
          };
        }

        const nowIso = new Date().toISOString();
        const session: ChatKitSession = {
          id: nodeId,
          nodeId,
          title: chatNode.data.label || "Chat trigger",
          subtitle:
            typeof chatNode.data?.description === "string"
              ? chatNode.data.description
              : "Chat-triggered workflow",
          environment: chatEnvironment,
          status: "idle",
          updatedAt: nowIso,
          participants: [
            { ...chatUserProfile, role: "user" },
            { ...chatAssistantProfile, role: "ai" },
          ],
          quickPrompts: [
            "Trigger this workflow",
            "Show me the last run summary",
            "List required credentials",
          ],
          handoffChecklist: [
            {
              id: `${nodeId}-qa`,
              label: "QA prompt output for chat trigger",
              completed: false,
              owner: "Workflow Owner",
            },
            {
              id: `${nodeId}-credentials`,
              label: "Verify credential scope for chat usage",
              completed: false,
              owner: "Security Reviewer",
            },
          ],
          messages: [
            {
              id: `welcome-${nodeId}`,
              content: `You're connected to ${
                chatNode.data.label || "this chat trigger"
              }. Ask me to run the workflow or inspect recent runs.`,
              sender: chatAssistantProfile,
              timestamp: nowIso,
            },
          ],
        };

        resolvedEnvironment = session.environment;

        return {
          ...prev,
          [nodeId]: session,
        };
      });

      setActiveChatSessionId(nodeId);
      if (resolvedEnvironment) {
        setChatEnvironment(resolvedEnvironment);
      }
      setIsChatOpen(true);
    },
    [chatAssistantProfile, chatEnvironment, chatUserProfile],
  );

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

  const decoratedNodes = useMemo(() => {
    if (!isSearchOpen && searchMatches.length === 0) {
      return nodes;
    }

    return nodes.map((node) => {
      const isMatch = searchMatchSet.has(node.id);
      const isActive =
        isMatch &&
        isSearchOpen &&
        searchMatches[currentSearchIndex] === node.id;

      if (!isSearchOpen) {
        return isMatch
          ? {
              ...node,
              data: {
                ...node.data,
                isSearchMatch: false,
                isSearchActive: false,
              },
            }
          : node;
      }

      return {
        ...node,
        data: {
          ...node.data,
          isSearchMatch: isMatch,
          isSearchActive: isActive,
        },
      };
    });
  }, [currentSearchIndex, isSearchOpen, nodes, searchMatchSet, searchMatches]);

  const credentialEligibleNodes = useMemo(
    () =>
      nodes.filter((node) => {
        const candidateType =
          typeof node.data?.type === "string"
            ? node.data.type
            : typeof node.type === "string"
              ? node.type
              : "";
        return ["api", "data", "database"].includes(candidateType);
      }),
    [nodes],
  );

  const credentialOptions = useMemo(
    () =>
      credentials.map((credential) => ({
        id: credential.id,
        label: credential.name,
      })),
    [credentials],
  );

  const credentialIssueCount = validationErrors.filter(
    (error) => error.type === "credential",
  ).length;
  const totalValidationIssues = validationErrors.length;

  const createSnapshot = useCallback(
    (): WorkflowSnapshot => ({
      nodes: nodesRef.current.map(cloneNode),
      edges: edgesRef.current.map(cloneEdge),
    }),
    [],
  );

  const appendValidationError = useCallback((error: ValidationError) => {
    setValidationErrors((previous) => {
      if (previous.some((item) => item.id === error.id)) {
        return previous;
      }
      return [...previous, error];
    });
  }, []);

  const mergeCredentialErrors = useCallback((errors: ValidationError[]) => {
    setValidationErrors((previous) => {
      const retained = previous.filter((item) => item.type !== "credential");
      const merged = new Map<string, ValidationError>();
      retained.forEach((item) => merged.set(item.id, item));
      errors.forEach((item) => merged.set(item.id, item));
      return Array.from(merged.values());
    });
  }, []);

  const runPublishValidation = useCallback(() => {
    const snapshot = createSnapshot();
    const credentialErrors = snapshot.nodes
      .map((node) =>
        validateNodeCredentials(node as unknown as Node<ValidatorNodeData>),
      )
      .filter((error): error is ValidationError => Boolean(error));

    mergeCredentialErrors(credentialErrors);
    return credentialErrors;
  }, [createSnapshot, mergeCredentialErrors]);

  const handleManualValidation = useCallback(() => {
    const newCredentialIssues = runPublishValidation();
    const existingConnectionIssues = validationErrors.filter(
      (error) => error.type === "connection",
    ).length;
    const totalIssues = newCredentialIssues.length + existingConnectionIssues;

    if (totalIssues === 0) {
      toast({
        title: "Workflow ready to publish",
        description: "No blocking credential or connection issues detected.",
      });
    } else {
      toast({
        title: "Resolve blocking issues",
        description: `${totalIssues} ${
          totalIssues === 1 ? "issue" : "issues"
        } must be fixed before publishing.`,
        variant: "destructive",
      });
    }
  }, [runPublishValidation, validationErrors]);

  const handleDismissValidationError = useCallback((id: string) => {
    setValidationErrors((previous) =>
      previous.filter((error) => error.id !== id),
    );
  }, []);

  const handleFixValidationError = useCallback(
    (error: ValidationError) => {
      if (error.type === "credential" && error.sourceId) {
        const targetNode = nodesRef.current.find(
          (node) => node.id === error.sourceId,
        );
        if (targetNode) {
          setActiveTab("settings");
          setSelectedNode(targetNode);
        }
        return;
      }

      if (error.type === "connection") {
        setActiveTab("canvas");
      }
    },
    [setActiveTab, setSelectedNode],
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
      rehydrateCredentialAssignments(snapshot.nodes);
      setNodesState(snapshot.nodes);
      setEdgesState(snapshot.edges);
      if (resetHistory) {
        undoStackRef.current = [];
        redoStackRef.current = [];
        setCanUndo(false);
        setCanRedo(false);
      }
    },
    [
      rehydrateCredentialAssignments,
      setCanRedo,
      setCanUndo,
      setEdgesState,
      setNodesState,
    ],
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
    if (nodesRef.current.length === 0) {
      return;
    }
    runPublishValidation();
  }, [nodeCredentialAssignments, runPublishValidation]);

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

  // Sample executions for the WorkflowExecutionHistory component
  const mockExecutions = useMemo<HistoryWorkflowExecution[]>(
    () => [
      {
        id: "1",
        runId: "842",
        status: "success",
        startTime: new Date().toISOString(),
        duration: 45200,
        issues: 0,
        nodes: [
          {
            id: "node-1",
            type: "webhook",
            name: "New Customer Webhook",
            position: { x: 100, y: 100 },
            status: "success",
          },
          {
            id: "node-2",
            type: "http",
            name: "Fetch Customer Details",
            position: { x: 400, y: 100 },
            status: "success",
            details: {
              method: "GET",
              url: "https://api.example.com/customers/123",
              items: 1,
            },
          },
          {
            id: "node-3",
            type: "function",
            name: "Format Customer Data",
            position: { x: 700, y: 100 },
            status: "success",
          },
          {
            id: "node-4",
            type: "api",
            name: "Create Account",
            position: { x: 400, y: 250 },
            status: "success",
          },
          {
            id: "node-5",
            type: "api",
            name: "Send Welcome Email",
            position: { x: 700, y: 250 },
            status: "success",
            details: {
              message: "Welcome to our platform!",
            },
          },
        ],
        edges: [
          { id: "edge-1", source: "node-1", target: "node-2", type: "default" },
          { id: "edge-2", source: "node-2", target: "node-3" },
          { id: "edge-3", source: "node-3", target: "node-4" },
          { id: "edge-4", source: "node-4", target: "node-5" },
        ],
        logs: [
          {
            timestamp: "10:23:15",
            level: "INFO",
            message: "Workflow execution started",
          },
          {
            timestamp: "10:23:16",
            level: "DEBUG",
            message: 'Executing node "New Customer Webhook"',
          },
          {
            timestamp: "10:23:17",
            level: "INFO",
            message: 'Node "New Customer Webhook" completed successfully',
          },
          {
            timestamp: "10:23:18",
            level: "DEBUG",
            message: 'Executing node "Fetch Customer Details"',
          },
          {
            timestamp: "10:23:20",
            level: "INFO",
            message: 'Node "Fetch Customer Details" completed successfully',
          },
          {
            timestamp: "10:23:21",
            level: "DEBUG",
            message: 'Executing node "Format Customer Data"',
          },
          {
            timestamp: "10:23:23",
            level: "INFO",
            message: 'Node "Format Customer Data" completed successfully',
          },
          {
            timestamp: "10:23:24",
            level: "DEBUG",
            message: 'Executing node "Create Account"',
          },
          {
            timestamp: "10:23:40",
            level: "INFO",
            message: 'Node "Create Account" completed successfully',
          },
          {
            timestamp: "10:23:41",
            level: "DEBUG",
            message: 'Executing node "Send Welcome Email"',
          },
          {
            timestamp: "10:23:45",
            level: "INFO",
            message: 'Node "Send Welcome Email" completed successfully',
          },
          {
            timestamp: "10:23:45",
            level: "INFO",
            message: "Workflow execution completed successfully",
          },
        ],
      },
      {
        id: "2",
        runId: "841",
        status: "failed",
        startTime: new Date(Date.now() - 86400000).toISOString(), // yesterday
        duration: 134700,
        issues: 3,
        nodes: [
          {
            id: "node-1",
            type: "webhook",
            name: "New Customer Webhook",
            position: { x: 100, y: 100 },
            status: "success",
          },
          {
            id: "node-2",
            type: "http",
            name: "Fetch Customer Details",
            position: { x: 400, y: 100 },
            status: "success",
            details: {
              method: "GET",
              url: "https://api.example.com/customers/456",
              items: 1,
            },
          },
          {
            id: "node-3",
            type: "function",
            name: "Format Customer Data",
            position: { x: 700, y: 100 },
            status: "success",
          },
          {
            id: "node-4",
            type: "api",
            name: "Create Account",
            position: { x: 400, y: 250 },
            status: "error",
            details: {
              message: "Email already exists",
            },
          },
          {
            id: "node-5",
            type: "api",
            name: "Send Welcome Email",
            position: { x: 700, y: 250 },
            status: "idle",
          },
        ],
        edges: [
          { id: "edge-1", source: "node-1", target: "node-2" },
          { id: "edge-2", source: "node-2", target: "node-3" },
          { id: "edge-3", source: "node-3", target: "node-4" },
          { id: "edge-4", source: "node-4", target: "node-5" },
        ],
        logs: [
          {
            timestamp: "15:45:10",
            level: "INFO",
            message: "Workflow execution started",
          },
          {
            timestamp: "15:45:11",
            level: "DEBUG",
            message: 'Executing node "New Customer Webhook"',
          },
          {
            timestamp: "15:45:12",
            level: "INFO",
            message: 'Node "New Customer Webhook" completed successfully',
          },
          {
            timestamp: "15:45:13",
            level: "DEBUG",
            message: 'Executing node "Fetch Customer Details"',
          },
          {
            timestamp: "15:45:15",
            level: "INFO",
            message: 'Node "Fetch Customer Details" completed successfully',
          },
          {
            timestamp: "15:45:16",
            level: "DEBUG",
            message: 'Executing node "Format Customer Data"',
          },
          {
            timestamp: "15:45:18",
            level: "INFO",
            message: 'Node "Format Customer Data" completed successfully',
          },
          {
            timestamp: "15:45:19",
            level: "DEBUG",
            message: 'Executing node "Create Account"',
          },
          {
            timestamp: "15:45:30",
            level: "ERROR",
            message: 'Error in node "Create Account": Email already exists',
          },
          {
            timestamp: "15:45:30",
            level: "INFO",
            message: "Workflow execution failed",
          },
        ],
      },
      {
        id: "3",
        runId: "840",
        status: "partial",
        startTime: new Date("2023-11-03T09:12:00").toISOString(),
        duration: 67300,
        issues: 1,
        nodes: [
          {
            id: "node-1",
            type: "webhook",
            name: "New Customer Webhook",
            position: { x: 100, y: 100 },
            status: "success",
          },
          {
            id: "node-2",
            type: "http",
            name: "Fetch Customer Details",
            position: { x: 400, y: 100 },
            status: "success",
          },
          {
            id: "node-3",
            type: "function",
            name: "Format Customer Data",
            position: { x: 700, y: 100 },
            status: "success",
          },
          {
            id: "node-4",
            type: "api",
            name: "Create Account",
            position: { x: 400, y: 250 },
            status: "success",
          },
          {
            id: "node-5",
            type: "api",
            name: "Send Welcome Email",
            position: { x: 700, y: 250 },
            status: "success",
          },
        ],
        edges: [
          { id: "edge-1", source: "node-1", target: "node-2" },
          { id: "edge-2", source: "node-2", target: "node-3" },
          { id: "edge-3", source: "node-3", target: "node-4" },
          { id: "edge-4", source: "node-4", target: "node-5" },
        ],
        logs: [
          {
            timestamp: "09:12:00",
            level: "INFO",
            message: "Workflow execution started",
          },
          {
            timestamp: "09:12:01",
            level: "DEBUG",
            message: 'Executing node "Daily Report Trigger"',
          },
          {
            timestamp: "09:12:02",
            level: "INFO",
            message: 'Node "Daily Report Trigger" completed successfully',
          },
          {
            timestamp: "09:12:03",
            level: "DEBUG",
            message: 'Executing node "Fetch Sales Data"',
          },
          {
            timestamp: "09:12:10",
            level: "INFO",
            message: 'Node "Fetch Sales Data" completed successfully',
          },
          {
            timestamp: "09:12:11",
            level: "DEBUG",
            message: 'Executing node "Generate Report"',
          },
          {
            timestamp: "09:12:30",
            level: "INFO",
            message: 'Node "Generate Report" completed successfully',
          },
          {
            timestamp: "09:12:31",
            level: "DEBUG",
            message: 'Executing node "Email Report"',
          },
          {
            timestamp: "09:12:40",
            level: "INFO",
            message: 'Node "Email Report" completed successfully',
          },
          {
            timestamp: "09:12:41",
            level: "DEBUG",
            message: 'Executing node "Slack Notification"',
          },
          {
            timestamp: "09:12:45",
            level: "WARNING",
            message:
              'Node "Slack Notification" completed with warnings: Channel not found',
          },
          {
            timestamp: "09:12:45",
            level: "INFO",
            message: "Workflow execution completed with warnings",
          },
        ],
      },
    ],
    [],
  );

  const buildExecutionFromSnapshot = useCallback(
    (snapshot: WorkflowSnapshot, executionId: string, startTime: string) => ({
      id: executionId,
      runId: executionId,
      status: "running" as HistoryWorkflowExecution["status"],
      startTime,
      duration: 0,
      issues: 0,
      nodes: snapshot.nodes.map((node) => ({
        id: node.id,
        type:
          typeof node.data?.type === "string"
            ? node.data.type
            : typeof node.type === "string"
              ? node.type
              : "default",
        name: typeof node.data?.label === "string" ? node.data.label : node.id,
        position: node.position ?? { x: 0, y: 0 },
        status: "running" as NodeStatus,
      })),
      edges: snapshot.edges.map((edge) => ({
        id: edge.id ?? `${edge.source}-${edge.target}`,
        source: edge.source,
        target: edge.target,
      })),
      logs: [],
    }),
    [],
  );

  const toHistoryLogs = useCallback(
    (entries: ExecutionLogEntry[]): HistoryWorkflowExecution["logs"] =>
      entries.map((entry) => ({
        timestamp: entry.timestamp,
        level: entry.level,
        message: entry.message,
      })),
    [],
  );

  const executionsForHistory = useMemo(() => {
    const normalise = (execution: HistoryWorkflowExecution) => ({
      ...execution,
      nodes: execution.nodes.map((node) => ({
        ...node,
        status: (node.status ?? "idle") as NodeStatus,
      })),
    });

    if (!liveExecution) {
      return mockExecutions.map(normalise);
    }
    const filtered = mockExecutions
      .filter((execution) => execution.id !== liveExecution.id)
      .map(normalise);
    return [normalise(liveExecution), ...filtered];
  }, [liveExecution, mockExecutions]);

  useEffect(() => {
    if (!backendWorkflowId) {
      return;
    }
    if (
      backendExecutionStatus === "running" ||
      backendExecutionStatus === "connecting"
    ) {
      setLiveExecutionLogs(backendExecutionLogs);
    }
  }, [backendExecutionLogs, backendExecutionStatus, backendWorkflowId]);

  useEffect(() => {
    setLiveExecution((current) =>
      current
        ? {
            ...current,
            logs: toHistoryLogs(liveExecutionLogs),
          }
        : current,
    );
  }, [liveExecutionLogs, toHistoryLogs]);

  const loadExecutionHistory = useCallback(async (executionId: string) => {
    try {
      const history = await fetchExecutionHistory(executionId);
      const normalisedStatus = normaliseHistoryStatus(history.status);
      const logs = history.steps.map((step) => {
        const payload = step.payload ?? {};
        const statusValue =
          typeof payload.status === "string"
            ? payload.status.toLowerCase()
            : "";
        let level: HistoryWorkflowExecution["logs"][number]["level"] = "INFO";
        if (statusValue === "error") {
          level = "ERROR";
        } else if (statusValue === "cancelled") {
          level = "WARNING";
        } else if (typeof payload.event === "string") {
          level = "DEBUG";
        }

        let message: string;
        if (typeof payload.message === "string" && payload.message.trim()) {
          message = payload.message;
        } else if (
          typeof payload.node === "string" &&
          typeof payload.event === "string"
        ) {
          message = `[${payload.event}] ${payload.node}`;
        } else if (typeof payload.status === "string") {
          message = `Status: ${payload.status}`;
        } else {
          message = JSON.stringify(payload);
        }

        return {
          timestamp: new Date(step.at).toISOString(),
          level,
          message,
        };
      });

      setLiveExecutionLogs(
        logs.map((entry) => ({
          timestamp: entry.timestamp,
          level: entry.level,
          message: entry.message,
        })),
      );

      const duration = computeDurationMs(
        history.started_at,
        history.completed_at ?? new Date().toISOString(),
      );

      setLiveExecution((current) =>
        current && current.id === executionId
          ? {
              ...current,
              status: mapBackendStatusToHistory(normalisedStatus),
              startTime: history.started_at,
              endTime: history.completed_at ?? current.endTime,
              duration,
              issues: normalisedStatus === "error" ? 1 : current.issues,
            }
          : current,
      );
    } catch (error) {
      console.error("Failed to fetch execution history", error);
      toast({
        title: "Execution history unavailable",
        description:
          error instanceof Error
            ? error.message
            : "Unable to retrieve execution history from the backend.",
        variant: "destructive",
      });
    }
  }, []);

  useEffect(() => {
    if (!backendWorkflowId) {
      return;
    }

    if (
      backendExecutionStatus === "running" ||
      backendExecutionStatus === "connecting"
    ) {
      executionStartRef.current ??= new Date().toISOString();
      setIsRunning(true);
      setLiveExecution((current) =>
        current
          ? {
              ...current,
              status: mapBackendStatusToHistory(backendExecutionStatus),
            }
          : current,
      );
      return;
    }

    if (backendExecutionStatus === "idle") {
      setIsRunning(false);
      return;
    }

    if (isFinalExecutionStatus(backendExecutionStatus)) {
      setIsRunning(false);
      if (!backendExecutionId) {
        return;
      }
      const finishedAt = new Date().toISOString();
      const startedAt = executionStartRef.current ?? finishedAt;
      const duration = computeDurationMs(startedAt, finishedAt);
      executionStartRef.current = null;
      setLiveExecution((current) =>
        current && current.id === backendExecutionId
          ? {
              ...current,
              status: mapBackendStatusToHistory(backendExecutionStatus),
              endTime: finishedAt,
              duration,
              issues:
                backendExecutionStatus === "error"
                  ? current.issues === 0
                    ? 1
                    : current.issues
                  : current.issues,
            }
          : current,
      );
      void loadExecutionHistory(backendExecutionId);
    }
  }, [
    backendExecutionId,
    backendExecutionStatus,
    backendWorkflowId,
    loadExecutionHistory,
  ]);

  const startBackendExecution = useCallback(async () => {
    try {
      const snapshot = createSnapshot();
      const startTime = new Date().toISOString();
      const executionIdentifier = await startExecution();
      if (!executionIdentifier) {
        return null;
      }
      executionStartRef.current = startTime;
      const executionRecord = buildExecutionFromSnapshot(
        snapshot,
        executionIdentifier,
        startTime,
      );
      setLiveExecution(executionRecord);
      setLiveExecutionLogs([]);
      return executionIdentifier;
    } catch (error) {
      console.error("Failed to start backend execution", error);
      toast({
        title: "Unable to start execution",
        description:
          error instanceof Error
            ? error.message
            : "Unexpected error while starting the backend execution.",
        variant: "destructive",
      });
      return null;
    }
  }, [buildExecutionFromSnapshot, createSnapshot, startExecution]);

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
    const duplicatedNodes = selectedNodes.map((node) => {
      const newId = generateNodeId();
      idMap.set(node.id, newId);
      const clonedNode = cloneNode(node);
      const baseLabel =
        typeof clonedNode.data?.label === "string"
          ? clonedNode.data.label
          : clonedNode.id;
      return {
        ...clonedNode,
        id: newId,
        position: {
          x: (clonedNode.position?.x ?? 0) + 40,
          y: (clonedNode.position?.y ?? 0) + 40,
        },
        selected: false,
        data: {
          ...clonedNode.data,
          label: `${baseLabel} Copy`,
        },
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
  }, [edges, nodes, recordSnapshot, setEdgesState, setNodesState]);

  const handleExportWorkflow = useCallback(() => {
    try {
      const snapshot = createSnapshot();
      const workflowData = {
        name: workflowName,
        description: workflowDescription,
        nodes: snapshot.nodes.map(toPersistedNode),
        edges: snapshot.edges.map(toPersistedEdge),
        credentials: credentials.map((credential) => ({
          ...credential,
          secrets: { ...credential.secrets },
        })),
        linkedSubworkflowIds: [...linkedSubworkflows],
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
  }, [
    createSnapshot,
    credentials,
    linkedSubworkflows,
    workflowDescription,
    workflowName,
  ]);

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
            ensureCredentialsState(
              Array.isArray(parsed.credentials)
                ? (parsed.credentials as WorkflowCredential[])
                : undefined,
            );
            ensureLinkedSubworkflows(
              Array.isArray(parsed.linkedSubworkflowIds)
                ? (parsed.linkedSubworkflowIds as string[])
                : undefined,
            );
            rehydrateCredentialAssignments(importedNodes);
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
      ensureCredentialsState,
      ensureLinkedSubworkflows,
      recordSnapshot,
      rehydrateCredentialAssignments,
      setEdgesState,
      setNodesState,
      setWorkflowDescription,
      setWorkflowName,
    ],
  );

  const handleAddCredential = useCallback((input: CredentialFormInput) => {
    const timestamp = new Date().toISOString();
    const randomId =
      typeof globalThis.crypto !== "undefined" &&
      typeof globalThis.crypto.randomUUID === "function"
        ? `cred-${globalThis.crypto.randomUUID()}`
        : `cred-${Date.now().toString(36)}-${Math.random()
            .toString(36)
            .slice(2, 8)}`;

    const credential: WorkflowCredential = {
      id: randomId,
      name: input.name,
      type: input.type,
      access: input.access,
      secrets: { ...input.secrets },
      owner: input.owner ?? "Workflow Owner",
      createdAt: timestamp,
      updatedAt: timestamp,
      description: input.description,
    };

    setCredentials((previous) => [...previous, credential]);
    toast({
      title: "Credential added",
      description: `${input.name} is now available for workflow nodes.`,
    });
  }, []);

  const handleDeleteCredential = useCallback(
    (credentialId: string) => {
      setCredentials((previous) =>
        previous.filter((credential) => credential.id !== credentialId),
      );

      setNodeCredentialAssignments((previous) => {
        const nextAssignments: Record<string, string> = { ...previous };
        let shouldUpdateNodes = false;
        Object.entries(previous).forEach(([nodeId, value]) => {
          if (value === credentialId) {
            delete nextAssignments[nodeId];
            shouldUpdateNodes = true;
          }
        });

        if (shouldUpdateNodes) {
          setNodes((current) =>
            current.map((node) => {
              const assigned = (
                node.data as NodeData & { credentials?: { id?: string } }
              ).credentials?.id;
              if (assigned === credentialId) {
                return {
                  ...node,
                  data: {
                    ...node.data,
                    credentials: null,
                  },
                };
              }
              return node;
            }),
          );
        }

        return nextAssignments;
      });

      toast({
        title: "Credential removed",
        description:
          "Nodes that referenced this credential will need a new assignment.",
        variant: "destructive",
      });
    },
    [setNodes],
  );

  const handleCredentialAssignmentChange = useCallback(
    (nodeId: string, credentialId: string | null) => {
      setNodeCredentialAssignments((previous) => {
        const next = { ...previous };
        if (!credentialId || credentialId === "__none__") {
          delete next[nodeId];
        } else {
          next[nodeId] = credentialId;
        }
        return next;
      });

      setNodes((current) =>
        current.map((node) => {
          if (node.id !== nodeId) {
            return node;
          }
          return {
            ...node,
            data: {
              ...node.data,
              credentials:
                credentialId && credentialId !== "__none__"
                  ? { id: credentialId }
                  : null,
            },
          };
        }),
      );

      setValidationErrors((previous) =>
        previous.filter(
          (error) =>
            !(
              error.type === "credential" &&
              error.sourceId === nodeId &&
              credentialId &&
              credentialId !== "__none__"
            ),
        ),
      );
    },
    [setNodes],
  );

  const handleToggleLinkedSubworkflow = useCallback(
    (subworkflowId: string, linked: boolean) => {
      setLinkedSubworkflows((previous) => {
        if (linked) {
          if (previous.includes(subworkflowId)) {
            return previous;
          }
          return [...previous, subworkflowId];
        }
        return previous.filter((item) => item !== subworkflowId);
      });
    },
    [],
  );

  const handleInsertSubworkflow = useCallback(
    (subworkflowId: string) => {
      const template = SAMPLE_SUBWORKFLOWS.find(
        (item) => item.id === subworkflowId,
      );
      if (!template) {
        toast({
          title: "Sub-workflow unavailable",
          description:
            "We couldn't locate that reusable sub-workflow template.",
          variant: "destructive",
        });
        return;
      }

      const baseOffsetX = Math.random() * 160 + 120;
      const baseOffsetY = Math.random() * 120 + 120;
      const timestamp = Date.now().toString(36);

      const convertedNodes = convertPersistedNodesToCanvas(template.nodes);
      const idMap = new Map<string, string>();

      const newNodes = convertedNodes.map((node, index) => {
        const newId = `${subworkflowId}-${timestamp}-node-${index}`;
        idMap.set(node.id, newId);
        const cloned = cloneNode(node);
        return {
          ...cloned,
          id: newId,
          position: {
            x: (cloned.position?.x ?? 0) + baseOffsetX,
            y: (cloned.position?.y ?? 0) + baseOffsetY,
          },
          data: {
            ...cloned.data,
            credentials:
              (cloned.data as NodeData & { credentials?: { id?: string } })
                .credentials ?? null,
          },
        } as CanvasNode;
      });

      const newEdges = template.edges.map((edge, index) => {
        const canvasEdge = toCanvasEdge(edge);
        return {
          ...canvasEdge,
          id: `${subworkflowId}-${timestamp}-edge-${index}`,
          source: idMap.get(canvasEdge.source) ?? canvasEdge.source,
          target: idMap.get(canvasEdge.target) ?? canvasEdge.target,
        } as CanvasEdge;
      });

      const credentialAssignments: Record<string, string> = {};
      newNodes.forEach((node) => {
        const credentialId = (
          node.data as NodeData & { credentials?: { id?: string } }
        ).credentials?.id;
        if (credentialId) {
          credentialAssignments[node.id] = credentialId;
        }
      });

      setNodes((current) => [...current, ...newNodes]);
      setEdges((current) => [...current, ...newEdges]);

      if (Object.keys(credentialAssignments).length > 0) {
        setNodeCredentialAssignments((previous) => ({
          ...previous,
          ...credentialAssignments,
        }));
      }

      setLinkedSubworkflows((previous) => {
        if (previous.includes(subworkflowId)) {
          return previous;
        }
        return [...previous, subworkflowId];
      });

      toast({
        title: "Sub-workflow inserted",
        description: `${template.name} was added to the canvas.`,
      });
    },
    [convertPersistedNodesToCanvas, setEdges, setNodes],
  );

  const handleSaveWorkflow = useCallback(() => {
    const credentialIssues = runPublishValidation();
    const connectionIssues = validationErrors.filter(
      (error) => error.type === "connection",
    );
    const totalIssues = credentialIssues.length + connectionIssues.length;

    if (totalIssues > 0) {
      toast({
        title: "Resolve validation issues",
        description:
          "Fix credential and connection problems before publishing this workflow.",
        variant: "destructive",
      });
      setActiveTab("settings");
      return;
    }

    const snapshot = createSnapshot();
    const persistedNodes = snapshot.nodes.map(toPersistedNode);
    const persistedEdges = snapshot.edges.map(toPersistedEdge);
    const timestampLabel = new Date().toLocaleString();

    const tagsToPersist = workflowTags.length > 0 ? workflowTags : ["draft"];

    const saved = persistWorkflow(
      {
        id: currentWorkflowId ?? undefined,
        name: workflowName.trim() || "Untitled Workflow",
        description: workflowDescription.trim(),
        tags: tagsToPersist,
        nodes: persistedNodes,
        edges: persistedEdges,
        credentials: credentials.map((credential) => ({
          ...credential,
          secrets: { ...credential.secrets },
        })),
        linkedSubworkflowIds: [...linkedSubworkflows],
      },
      { versionMessage: `Manual save (${timestampLabel})` },
    );

    setCurrentWorkflowId(saved.id);
    setWorkflowName(saved.name);
    setWorkflowDescription(saved.description ?? "");
    setWorkflowTags(saved.tags ?? tagsToPersist);
    setWorkflowVersions(saved.versions ?? []);
    ensureCredentialsState(saved.credentials);
    ensureLinkedSubworkflows(saved.linkedSubworkflowIds);

    toast({
      title: "Workflow saved",
      description: `"${saved.name}" has been updated.`,
    });

    if (!workflowId || workflowId !== saved.id) {
      navigate(`/workflow-canvas/${saved.id}`, { replace: !!workflowId });
    }
  }, [
    credentials,
    createSnapshot,
    currentWorkflowId,
    ensureCredentialsState,
    ensureLinkedSubworkflows,
    linkedSubworkflows,
    navigate,
    runPublishValidation,
    setActiveTab,
    workflowDescription,
    workflowId,
    workflowName,
    workflowTags,
    validationErrors,
  ]);

  const handleTagsChange = useCallback((value: string) => {
    const tags = value
      .split(",")
      .map((tag) => tag.trim())
      .filter((tag) => tag.length > 0);
    setWorkflowTags(tags);
  }, []);

  const handleRestoreVersion = useCallback(
    (versionId: string) => {
      if (!currentWorkflowId) {
        toast({
          title: "Save required",
          description: "Save this workflow before restoring versions.",
          variant: "destructive",
        });
        return;
      }

      const snapshot = getVersionSnapshot(currentWorkflowId, versionId);
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
    },
    [applySnapshot, convertPersistedNodesToCanvas, currentWorkflowId],
  );

  // Handle new connections between nodes
  const onConnect = useCallback(
    (params: Connection) => {
      const validationResult = validateConnection(
        params,
        nodesRef.current as unknown as Node<ValidatorNodeData>[],
        edgesRef.current,
      );
      if (validationResult) {
        appendValidationError(validationResult);
        toast({
          title: "Connection blocked",
          description: validationResult.message,
          variant: "destructive",
        });
        return;
      }

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
              type: "smoothstep",
              markerEnd: {
                type: MarkerType.ArrowClosed,
                width: 20,
                height: 20,
              },
              style: { stroke: "#99a1b3", strokeWidth: 2 },
            },
            eds,
          ),
        );
      }
    },
    [appendValidationError, edges, setEdges],
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
      setSelectedNode(node);
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

        // Create a new node
        const nodeId = generateNodeId();

        const newNode: CanvasNode = {
          id: nodeId,
          type: nodeType,
          position,
          style: defaultNodeStyle,
          data: {
            ...node,
            label: node.name || "New Node",
            description: node.description || "",
            type:
              nodeType === "startEnd"
                ? node.id === "start-node"
                  ? "start"
                  : "end"
                : node.id?.split("-")[0] || "default",
            status: "idle" as NodeStatus,
            icon: node.icon,
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
    [handleOpenChat, setNodes],
  );

  // Handle adding a node by clicking
  const handleAddNode = useCallback(
    (node: SidebarNodeDefinition) => {
      if (!reactFlowInstance.current) return;

      const nodeType = determineNodeType(node.id);

      // Calculate a position for the new node
      const position = {
        x: Math.random() * 300 + 100,
        y: Math.random() * 300 + 100,
      };

      // Create a new node with explicit NodeData type
      const nodeId = generateNodeId();

      const newNode: Node<NodeData> = {
        id: nodeId,
        type: nodeType,
        position,
        style: defaultNodeStyle,
        data: {
          type:
            nodeType === "startEnd"
              ? node.id === "start-node"
                ? "start"
                : "end"
              : node.type || "default",
          label: node.name || "New Node",
          description: node.description || "",
          status: "idle" as NodeStatus,
          icon: node.icon,
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
    [handleOpenChat, setNodes],
  );

  // Handle chat message sending
  const buildAssistantResponse = useCallback(
    (
      incoming: string,
      session: ChatKitSession,
      environment: ChatEnvironment,
    ) => {
      const text = incoming.toLowerCase();
      const outstanding =
        session.handoffChecklist?.filter((item) => !item.completed) ?? [];
      const latestRun = session.runSummaries?.[0];
      const tokenStats = session.tokenEstimate ?? latestRun?.tokens ?? null;

      if (text.includes("blocker") || text.includes("checklist")) {
        if (outstanding.length === 0) {
          return "No outstanding blockers. The handoff checklist is complete and we're ready for launch.";
        }
        const items = outstanding
          .map(
            (item) =>
              `• ${item.label}${item.owner ? ` (owner: ${item.owner})` : ""}`,
          )
          .join("\n");
        return `Here are the remaining items before handoff:\n${items}`;
      }

      if (text.includes("token")) {
        if (tokenStats) {
          return `Latest token profile — total: ${tokenStats.total.toLocaleString()}, prompt: ${tokenStats.prompt.toLocaleString()}, completion: ${tokenStats.completion.toLocaleString()}.`;
        }
        return "I'll capture token usage once the next run finishes.";
      }

      if (text.includes("credential")) {
        return "This chat trigger uses the credential assignments from the Settings tab. Make sure production-safe scopes are linked before publishing.";
      }

      if (text.includes("summary") || text.includes("run")) {
        if (latestRun) {
          const durationSeconds = latestRun.durationMs
            ? Math.round(latestRun.durationMs / 1000)
            : 0;
          return `Last ${environment} run (${latestRun.id}) ${latestRun.status === "completed" ? "completed" : latestRun.status} in ${durationSeconds}s. Triggered by ${latestRun.triggeredBy ?? "automation"}.`;
        }
        return `No recorded runs yet. Trigger a ${environment} execution and I'll summarise the results here.`;
      }

      if (text.includes("handoff")) {
        return `I'll package a production-ready summary once the outstanding checklist items are resolved. Let me know if you want a customer-facing recap.`;
      }

      return `Queued a ${environment} run for ${workflowName}. I'll post the telemetry as soon as it's ready.`;
    },
    [workflowName],
  );

  const handleSendChatMessage = useCallback(
    (sessionId: string, message: string, attachments: Attachment[]) => {
      if (!sessionId) {
        toast({
          title: "Select a chat-enabled node",
          description: "Open a node chat to send messages.",
        });
        return;
      }

      if (!message.trim() && attachments.length === 0) {
        return;
      }

      const formatFileSize = (bytes: number): string => {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        if (bytes < 1024 * 1024 * 1024)
          return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
        return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
      };

      const messageId = `msg-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
      const attachmentPayloads: NonNullable<ChatMessageProps["attachments"]> =
        attachments.map((item) => ({
          id: item.id,
          type: item.type,
          name: item.file.name,
          url:
            item.previewUrl ??
            (typeof window !== "undefined"
              ? URL.createObjectURL(item.file)
              : undefined),
          size: formatFileSize(item.file.size),
        }));

      let targetNodeId: string | null = null;
      let toastSessionTitle = "workflow";

      setChatSessions((prev) => {
        const session = prev[sessionId];
        if (!session) {
          return prev;
        }

        targetNodeId = session.nodeId ?? sessionId;
        toastSessionTitle = session.title;

        const nowIso = new Date().toISOString();
        const newMessage: ChatMessageProps = {
          id: messageId,
          content: message,
          sender: chatUserProfile,
          timestamp: nowIso,
          isUserMessage: true,
          status: "sending",
          attachments: attachmentPayloads,
        };

        return {
          ...prev,
          [sessionId]: {
            ...session,
            status: "running",
            messages: [...session.messages, newMessage],
            updatedAt: nowIso,
          },
        };
      });

      const attachmentSummary =
        attachments.length === 0
          ? ""
          : attachments.length === 1
            ? " with 1 attachment"
            : ` with ${attachments.length} attachments`;

      toast({
        title: `Message sent to ${toastSessionTitle}`,
        description: `"${message}"${attachmentSummary}`,
      });

      if (targetNodeId) {
        setNodes((nds) =>
          nds.map((node) => {
            if (node.id === targetNodeId) {
              return {
                ...node,
                data: {
                  ...node.data,
                  status: "running" as NodeStatus,
                },
              };
            }
            return node;
          }),
        );
      }

      setTimeout(() => {
        setChatSessions((prev) => {
          const session = prev[sessionId];
          if (!session) {
            return prev;
          }

          return {
            ...prev,
            [sessionId]: {
              ...session,
              messages: session.messages.map((chatMessage) =>
                chatMessage.id === messageId
                  ? { ...chatMessage, status: "sent" }
                  : chatMessage,
              ),
            },
          };
        });
      }, 400);

      setTimeout(() => {
        setChatSessions((prev) => {
          const session = prev[sessionId];
          if (!session) {
            return prev;
          }
          const environment = session.environment ?? chatEnvironment;
          const nowIso = new Date().toISOString();
          const response: ChatMessageProps = {
            id: `ai-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
            content: buildAssistantResponse(message, session, environment),
            sender: chatAssistantProfile,
            timestamp: nowIso,
          };

          const newSummary = {
            id: `session-${Math.random().toString(36).substring(2, 7)}`,
            status: "completed" as const,
            environment,
            startedAt: nowIso,
            durationMs: 4800,
            triggeredBy: chatUserProfile.name,
            tokens: session.tokenEstimate ??
              session.runSummaries?.[0]?.tokens ?? {
                prompt: 320,
                completion: 160,
                total: 480,
              },
            notes: `Simulated ${environment} execution for ${workflowName}.`,
          };

          return {
            ...prev,
            [sessionId]: {
              ...session,
              status: "completed",
              runSummaries: [
                newSummary,
                ...(session.runSummaries ?? []).slice(0, 4),
              ],
              messages: [...session.messages, response],
              updatedAt: nowIso,
            },
          };
        });

        if (targetNodeId) {
          setNodes((nds) =>
            nds.map((node) =>
              node.id === targetNodeId
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
        }
      }, 1200);
    },
    [
      buildAssistantResponse,
      chatAssistantProfile,
      chatEnvironment,
      chatUserProfile,
      setNodes,
      workflowName,
    ],
  );

  const handleChatEnvironmentChange = useCallback(
    (environment: ChatEnvironment) => {
      setChatEnvironment(environment);
      if (!activeChatSessionId) {
        return;
      }
      setChatSessions((prev) => {
        const session = prev[activeChatSessionId];
        if (!session) {
          return prev;
        }
        return {
          ...prev,
          [activeChatSessionId]: {
            ...session,
            environment,
            updatedAt: new Date().toISOString(),
          },
        };
      });
    },
    [activeChatSessionId],
  );

  const handleSelectChatSession = useCallback(
    (sessionId: string) => {
      setActiveChatSessionId(sessionId);
      setIsChatOpen(true);
      const session = chatSessions[sessionId];
      if (session?.environment) {
        setChatEnvironment(session.environment);
      }
    },
    [chatSessions],
  );

  const handleToggleChecklistItem = useCallback(
    (sessionId: string, itemId: string, completed: boolean) => {
      setChatSessions((prev) => {
        const session = prev[sessionId];
        if (!session?.handoffChecklist) {
          return prev;
        }
        return {
          ...prev,
          [sessionId]: {
            ...session,
            updatedAt: new Date().toISOString(),
            handoffChecklist: session.handoffChecklist.map((item) =>
              item.id === itemId ? { ...item, completed } : item,
            ),
          },
        };
      });
    },
    [],
  );

  const handleSendQuickPrompt = useCallback(
    (sessionId: string, prompt: string) => {
      handleSendChatMessage(sessionId, prompt, []);
    },
    [handleSendChatMessage],
  );

  const chatSessionsList = useMemo(
    () => Object.values(chatSessions),
    [chatSessions],
  );

  const chatMetrics = useMemo<ChatKitMetrics>(() => {
    const metrics: ChatKitMetrics = {
      lastExecutionStatus: backendExecutionStatus,
      lastExecutionStartedAt: liveExecution?.startedAt ?? null,
    };
    if (tokenMetrics) {
      metrics.tokens = {
        total: tokenMetrics.total,
        prompt: tokenMetrics.prompt,
        completion: tokenMetrics.completion,
      };
    }
    return metrics;
  }, [backendExecutionStatus, liveExecution, tokenMetrics]);

  // Handle workflow execution
  const handleRunWorkflow = useCallback(() => {
    if (backendWorkflowId) {
      setIsRunning(true);
      startBackendExecution()
        .then((executionIdentifier) => {
          if (!executionIdentifier) {
            setIsRunning(false);
            toast({
              title: "Unable to start execution",
              description:
                "The backend did not accept the execution request. Check server logs for more details.",
              variant: "destructive",
            });
            return;
          }
          toast({
            title: "Streaming workflow run",
            description:
              "Execution " +
              executionIdentifier +
              " is streaming from the backend.",
          });
        })
        .catch((error) => {
          console.error("Failed to initiate backend execution", error);
          setIsRunning(false);
          toast({
            title: "Backend execution failed",
            description:
              error instanceof Error
                ? error.message
                : "Unexpected error while starting the backend execution.",
            variant: "destructive",
          });
        });
      return;
    }

    setIsRunning(true);

    const nodeUpdates = [...nodes];
    let delay = 0;

    nodeUpdates.forEach((node) => {
      setTimeout(() => {
        setNodes((nds) =>
          nds.map((n) => {
            if (n.id === node.id) {
              return {
                ...n,
                data: {
                  ...n.data,
                  status: "running" as NodeStatus,
                },
              };
            }
            return n;
          }),
        );

        setTimeout(() => {
          setNodes((nds) =>
            nds.map((n) => {
              if (n.id === node.id) {
                return {
                  ...n,
                  data: {
                    ...n.data,
                    status:
                      Math.random() > 0.9
                        ? ("error" as NodeStatus)
                        : ("success" as NodeStatus),
                  },
                };
              }
              return n;
            }),
          );

          if (node.id === nodeUpdates[nodeUpdates.length - 1].id) {
            setIsRunning(false);
          }
        }, 1500);
      }, delay);

      delay += 1000;
    });
  }, [backendWorkflowId, nodes, setNodes, startBackendExecution]);

  // Handle workflow pause
  const handlePauseWorkflow = useCallback(() => {
    if (backendWorkflowId) {
      stopExecution();
      executionStartRef.current = null;
      setIsRunning(false);
      setLiveExecution((current) =>
        current
          ? {
              ...current,
              status: "partial",
            }
          : current,
      );
      toast({
        title: "Execution stream stopped",
        description: "Closed the live WebSocket connection to the backend.",
      });
      return;
    }

    setIsRunning(false);

    // Reset all running nodes to idle
    setNodes((nds) =>
      nds.map((n) => {
        if (n.data.status === "running") {
          return {
            ...n,
            data: {
              ...n.data,
              status: "idle" as NodeStatus,
            },
          };
        }
        return n;
      }),
    );
  }, [backendWorkflowId, setNodes, stopExecution]);

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
    const handleKeyDown = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey)) {
        return;
      }

      const key = event.key.toLowerCase();

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

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [
    handleRedo,
    handleUndo,
    setCurrentSearchIndex,
    setIsSearchOpen,
    setSearchMatches,
  ]);

  // Handle node inspector close
  const handleCloseNodeInspector = useCallback(() => {
    setSelectedNode(null);
  }, []);

  // Handle node update from inspector
  const handleNodeUpdate = useCallback(
    (nodeId: string, data: Partial<NodeData>) => {
      setNodes((nds) =>
        nds.map((n) => {
          if (n.id === nodeId) {
            const node = n as Node<NodeData>;
            return {
              ...node,
              data: {
                ...node.data,
                ...data,
                status:
                  data.status || node.data.status || ("idle" as NodeStatus),
              },
            };
          }
          return n;
        }),
      );
      setSelectedNode(null);
    },
    [setNodes],
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
    },
    [setNodes],
  );

  const handleRefreshExecutions = useCallback(() => {
    if (backendWorkflowId && backendExecutionId) {
      void loadExecutionHistory(backendExecutionId);
      return;
    }
    toast({
      title: "Execution history refresh",
      description: backendWorkflowId
        ? "No backend execution is currently active."
        : "Configure a backend workflow ID to enable live execution syncing.",
    });
  }, [backendExecutionId, backendWorkflowId, loadExecutionHistory]);

  // Load workflow data when workflowId changes
  useEffect(() => {
    const loadWorkflow = () => {
      if (!workflowId) {
        setCurrentWorkflowId(null);
        setWorkflowName("New Workflow");
        setWorkflowDescription("");
        setWorkflowTags(["draft"]);
        setWorkflowVersions([]);
        ensureCredentialsState();
        ensureLinkedSubworkflows([]);
        setNodeCredentialAssignments({});
        if (nodesRef.current.length === 0 && edgesRef.current.length === 0) {
          applySnapshot({ nodes: [], edges: [] }, { resetHistory: true });
        } else {
          undoStackRef.current = [];
          redoStackRef.current = [];
          setCanUndo(false);
          setCanRedo(false);
        }
        return;
      }

      const persisted = getWorkflowById(workflowId);
      if (persisted) {
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
        ensureCredentialsState(persisted.credentials);
        ensureLinkedSubworkflows(persisted.linkedSubworkflowIds);
        rehydrateCredentialAssignments(canvasNodes);
        return;
      }

      const template = SAMPLE_WORKFLOWS.find((w) => w.id === workflowId);
      if (template) {
        setCurrentWorkflowId(null);
        setWorkflowName(template.name);
        setWorkflowDescription(template.description ?? "");
        setWorkflowTags(template.tags.filter((tag) => tag !== "template"));
        setWorkflowVersions([]);
        const canvasNodes = convertPersistedNodesToCanvas(template.nodes);
        const canvasEdges = convertPersistedEdgesToCanvas(template.edges);
        applySnapshot(
          { nodes: canvasNodes, edges: canvasEdges },
          { resetHistory: true },
        );
        ensureCredentialsState(template.credentials);
        ensureLinkedSubworkflows(template.linkedSubworkflowIds);
        rehydrateCredentialAssignments(canvasNodes);
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
      setCurrentWorkflowId(null);
      setWorkflowName("New Workflow");
      setWorkflowDescription("");
      setWorkflowTags(["draft"]);
      setWorkflowVersions([]);
      ensureCredentialsState();
      ensureLinkedSubworkflows([]);
      setNodeCredentialAssignments({});
      applySnapshot({ nodes: [], edges: [] }, { resetHistory: true });
    };

    loadWorkflow();
  }, [
    applySnapshot,
    convertPersistedNodesToCanvas,
    ensureCredentialsState,
    ensureLinkedSubworkflows,
    rehydrateCredentialAssignments,
    workflowId,
  ]);

  useEffect(() => {
    if (!currentWorkflowId || typeof window === "undefined") {
      return;
    }

    const handleStorageUpdate = () => {
      const updated = getWorkflowById(currentWorkflowId);
      if (updated) {
        setWorkflowVersions(updated.versions ?? []);
        setWorkflowTags(updated.tags ?? ["draft"]);
      }
    };

    window.addEventListener(WORKFLOW_STORAGE_EVENT, handleStorageUpdate);
    return () => {
      window.removeEventListener(WORKFLOW_STORAGE_EVENT, handleStorageUpdate);
    };
  }, [currentWorkflowId]);

  // Fit view on initial render
  useEffect(() => {
    setTimeout(() => {
      if (reactFlowInstance.current) {
        reactFlowInstance.current.fitView({ padding: 0.2 });
      }
    }, 100);
  }, [nodes]);

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <TopNavigation
        currentWorkflow={{
          name: workflowName,
          path: ["Projects", "Workflows", workflowName],
        }}
      />

      <WorkflowTabs
        activeTab={activeTab}
        onTabChange={setActiveTab}
        executionCount={3}
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
                className="flex-1 h-full min-h-0"
                onDragOver={onDragOver}
                onDrop={onDrop}
              >
                <ReactFlow
                  nodes={decoratedNodes}
                  edges={edges}
                  onNodesChange={handleNodesChange}
                  onEdgesChange={handleEdgesChange}
                  onConnect={onConnect}
                  onNodeClick={onNodeClick}
                  onNodeDoubleClick={onNodeDoubleClick}
                  onInit={(instance) => {
                    reactFlowInstance.current = instance;
                  }}
                  nodeTypes={nodeTypes}
                  fitView
                  snapToGrid
                  snapGrid={[15, 15]}
                  defaultEdgeOptions={{
                    style: { stroke: "#99a1b3", strokeWidth: 2 },
                    type: "smoothstep",
                    markerEnd: {
                      type: MarkerType.ArrowClosed,
                    },
                  }}
                  connectionLineType={ConnectionLineType.SmoothStep}
                  connectionLineStyle={{ stroke: "#99a1b3", strokeWidth: 2 }}
                  proOptions={{ hideAttribution: true }}
                  className="h-full"
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
                  <Background />

                  <Controls />

                  <MiniMap
                    nodeStrokeWidth={3}
                    zoomable
                    pannable
                    nodeColor={(node) => {
                      switch (node.data?.type) {
                        case "api":
                          return "#93c5fd";
                        case "function":
                          return "#d8b4fe";
                        case "trigger":
                          return "#fcd34d";
                        case "data":
                          return "#86efac";
                        case "ai":
                          return "#a5b4fc";
                        case "chatTrigger":
                          return "#fdba74";
                        default:
                          return "#e2e8f0";
                      }
                    }}
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
                </ReactFlow>
              </div>
            </div>
          </TabsContent>

          <TabsContent
            value="execution"
            className="flex-1 m-0 p-0 overflow-hidden min-h-0"
          >
            <div className="flex flex-col h-full">
              <div className="border-b border-border p-4 space-y-2">
                {backendWorkflowId ? (
                  <div className="space-y-3">
                    <div className="flex flex-wrap items-center justify-between gap-4">
                      <div>
                        <h3 className="text-lg font-semibold">
                          Live execution
                        </h3>
                        <p className="text-sm text-muted-foreground">
                          Streaming updates from workflow
                          <span className="ml-1 font-mono text-xs bg-muted px-1.5 py-0.5 rounded">
                            {backendWorkflowId}
                          </span>
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-6 text-sm">
                        <div>
                          <span className="block text-xs uppercase text-muted-foreground tracking-wide">
                            Status
                          </span>
                          <span className="font-medium">
                            {EXECUTION_STATUS_LABELS[backendExecutionStatus]}
                          </span>
                        </div>
                        <div>
                          <span className="block text-xs uppercase text-muted-foreground tracking-wide">
                            Tokens
                          </span>
                          <span className="font-medium">
                            {tokenMetrics.total.toLocaleString()} total
                          </span>
                          <span className="block text-xs text-muted-foreground">
                            prompt {tokenMetrics.prompt.toLocaleString()} ·
                            completion{" "}
                            {tokenMetrics.completion.toLocaleString()}
                          </span>
                        </div>
                        {backendExecutionId ? (
                          <div>
                            <span className="block text-xs uppercase text-muted-foreground tracking-wide">
                              Execution ID
                            </span>
                            <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                              {backendExecutionId}
                            </code>
                          </div>
                        ) : null}
                      </div>
                    </div>
                    {backendExecutionError ? (
                      <Alert variant="destructive">
                        <AlertTitle>Streaming error</AlertTitle>
                        <AlertDescription>
                          {backendExecutionError}
                        </AlertDescription>
                      </Alert>
                    ) : null}
                  </div>
                ) : (
                  <Alert>
                    <AlertTitle>Backend streaming disabled</AlertTitle>
                    <AlertDescription>
                      Configure <code>VITE_ORCHEO_BACKEND_WORKFLOW_ID</code> to
                      stream live executions from the Orcheo backend. Runs are
                      currently simulated locally.
                    </AlertDescription>
                  </Alert>
                )}
              </div>
              <div className="flex-1 overflow-hidden">
                <WorkflowExecutionHistory
                  executions={executionsForHistory}
                  onViewDetails={handleViewExecutionDetails}
                  onRefresh={handleRefreshExecutions}
                  onCopyToEditor={(execution) =>
                    toast({
                      title: "Copied execution context",
                      description: `Run ${execution.runId} will be available in the editor soon.`,
                    })
                  }
                  onDelete={(execution) =>
                    toast({
                      title: "Execution deletion coming soon",
                      description: `Run ${execution.runId} can be removed once persistence is implemented.`,
                    })
                  }
                  defaultSelectedExecution={
                    liveExecution ?? executionsForHistory[0] ?? undefined
                  }
                />
              </div>
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

              <div className="space-y-4">
                <div>
                  <h2 className="text-xl font-bold mb-2">
                    Credential management
                  </h2>
                  <p className="text-sm text-muted-foreground">
                    Store encrypted credentials and reuse them across workflow
                    nodes.
                  </p>
                </div>
                <CredentialsVault
                  credentials={credentials}
                  onAddCredential={(credential) =>
                    handleAddCredential(credential)
                  }
                  onDeleteCredential={handleDeleteCredential}
                  className="mt-2"
                />
              </div>

              <div className="space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h3 className="text-lg font-semibold">
                      Node credential assignments
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      Map each external call to a credential before you publish.
                    </p>
                  </div>
                  <Badge
                    variant={
                      credentialIssueCount > 0 ? "destructive" : "secondary"
                    }
                  >
                    {credentialIssueCount > 0
                      ? `${credentialIssueCount} unassigned`
                      : "All nodes covered"}
                  </Badge>
                </div>

                {credentialEligibleNodes.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    No nodes require credentials in this workflow yet.
                  </p>
                ) : (
                  <div className="space-y-3">
                    {credentialEligibleNodes.map((node) => {
                      const assigned =
                        nodeCredentialAssignments[node.id] ?? "__none__";
                      const nodeType =
                        typeof node.data?.type === "string"
                          ? node.data.type
                          : (node.type ?? "");
                      return (
                        <div
                          key={node.id}
                          className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border/60 bg-muted/30 p-3"
                        >
                          <div>
                            <p className="text-sm font-medium">
                              {node.data?.label ?? node.id}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {node.id} • {nodeType}
                            </p>
                          </div>

                          <Select
                            value={assigned}
                            onValueChange={(value) =>
                              handleCredentialAssignmentChange(
                                node.id,
                                value === "__none__" ? null : value,
                              )
                            }
                          >
                            <SelectTrigger className="w-64">
                              <SelectValue placeholder="Select credential" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="__none__">
                                Unassigned
                              </SelectItem>
                              {credentialOptions.map((option) => (
                                <SelectItem key={option.id} value={option.id}>
                                  {option.label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              <Separator />

              <div className="space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h2 className="text-xl font-bold mb-1">
                      Reusable sub-workflows
                    </h2>
                    <p className="text-sm text-muted-foreground">
                      Insert curated workflow segments and control which ones
                      publish with this automation.
                    </p>
                  </div>
                </div>
                <ReusableSubworkflowLibrary
                  subworkflows={SAMPLE_SUBWORKFLOWS}
                  linkedSubworkflows={linkedSubworkflows}
                  onInsert={handleInsertSubworkflow}
                  onToggleLinked={handleToggleLinkedSubworkflow}
                />
              </div>

              <Separator />

              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-xl font-bold mb-1">Publish validation</h2>
                  <p className="text-sm text-muted-foreground">
                    Validation runs on save and highlights credential or
                    connection issues.
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <Badge
                    variant={
                      totalValidationIssues > 0 ? "destructive" : "secondary"
                    }
                  >
                    {totalValidationIssues > 0
                      ? `${totalValidationIssues} issues`
                      : "No blocking issues"}
                  </Badge>
                  <Button variant="outline" onClick={handleManualValidation}>
                    Run validation
                  </Button>
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
          onClose={handleCloseNodeInspector}
          onSave={handleNodeUpdate}
          className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 z-50"
        />
      )}

      <ChatKitInterface
        open={isChatOpen}
        onClose={() => setIsChatOpen(false)}
        workflowName={workflowName}
        environment={chatEnvironment}
        onEnvironmentChange={handleChatEnvironmentChange}
        sessions={chatSessionsList}
        activeSessionId={activeChatSessionId}
        onSelectSession={handleSelectChatSession}
        onSendMessage={handleSendChatMessage}
        onQuickPrompt={handleSendQuickPrompt}
        onToggleChecklistItem={handleToggleChecklistItem}
        metrics={chatMetrics}
        executionStatus={backendExecutionStatus}
        view={chatView}
        onViewChange={setChatView}
      />

      <ConnectionValidator
        errors={validationErrors}
        onDismiss={handleDismissValidationError}
        onFix={handleFixValidationError}
      />
    </div>
  );
}
