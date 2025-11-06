import React, { useState, useCallback, useRef, useEffect, useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import type {
  Connection,
  Node,
  ReactFlowInstance,
} from "@xyflow/react";
import { Panel, addEdge } from "@xyflow/react";
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
  type ValidationError,
} from "@features/workflow/components/canvas/connection-validator";
import WorkflowGovernancePanel, {
  type SubworkflowTemplate,
} from "@features/workflow/components/panels/workflow-governance-panel";
import {
  createHandleCreateSubworkflow,
  createHandleDeleteSubworkflow,
  createHandleInsertSubworkflow,
} from "@features/workflow/pages/workflow-canvas/handlers/subworkflows";
import {
  createHandleDismissValidation,
  createHandleFixValidation,
  createRunPublishValidation,
} from "@features/workflow/pages/workflow-canvas/handlers/validation";
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
import { buildGraphConfigFromCanvas } from "@features/workflow/lib/graph-config";
import {
  getNodeIcon,
  inferNodeIconKey,
} from "@features/workflow/lib/node-icons";
import {
  clearRuntimeCacheFromSession,
  getRuntimeCacheStorageKey,
  persistRuntimeCacheToSession,
  readRuntimeCacheFromSession,
} from "@features/workflow/pages/workflow-canvas/helpers/runtime-cache";
import {
  DEFAULT_STICKY_NOTE_COLOR,
  DEFAULT_STICKY_NOTE_CONTENT,
  DEFAULT_STICKY_NOTE_HEIGHT,
  DEFAULT_STICKY_NOTE_WIDTH,
  STICKY_NOTE_MIN_HEIGHT,
  STICKY_NOTE_MIN_WIDTH,
  isStickyNoteColor,
  sanitizeStickyNoteContent,
  sanitizeStickyNoteDimension,
} from "@features/workflow/pages/workflow-canvas/helpers/sticky-notes";
import {
  type SubworkflowStructure,
} from "@features/workflow/pages/workflow-canvas/helpers/subworkflow-library";
import {
  generateNodeId,
  generateRandomId,
} from "@features/workflow/pages/workflow-canvas/helpers/id";
import {
  DEFAULT_NODE_LABEL,
  createIdentityAllocator,
  sanitizeLabel,
} from "@features/workflow/pages/workflow-canvas/helpers/node-identity";
import {
  convertPersistedEdgesToCanvas,
  defaultNodeStyle,
  toCanvasNodeBase,
  toPersistedEdge,
  toPersistedNode,
} from "@features/workflow/pages/workflow-canvas/helpers/transformers";
import {
  PASTE_BASE_OFFSET,
  PASTE_OFFSET_INCREMENT,
  PASTE_OFFSET_MAX_STEPS,
  buildClipboardPayload,
  cloneEdge,
  cloneNode,
  decodeClipboardPayloadString,
  encodeClipboardPayload,
  signatureFromClipboardPayload,
} from "@features/workflow/pages/workflow-canvas/helpers/clipboard";
import {
  executionStatusFromValue,
  nodeStatusFromValue,
} from "@features/workflow/pages/workflow-canvas/helpers/execution";
import {
  determineNodeType,
  isRecord,
  validateWorkflowData,
} from "@features/workflow/pages/workflow-canvas/helpers/validation";
import { useWorkflowCredentials } from "@features/workflow/pages/workflow-canvas/hooks/use-workflow-credentials";
import { useWorkflowCanvasHistory } from "@features/workflow/pages/workflow-canvas/hooks/use-workflow-canvas-history";
import { useWorkflowChat } from "@features/workflow/pages/workflow-canvas/hooks/use-workflow-chat";
import { useWorkflowSearch } from "@features/workflow/pages/workflow-canvas/hooks/use-workflow-search";
import { useWorkflowNodeState } from "@features/workflow/pages/workflow-canvas/hooks/use-workflow-node-state";
import type {
  CanvasEdge,
  CanvasNode,
  CopyClipboardOptions,
  CopyClipboardResult,
  NodeData,
  NodeStatus,
  RunHistoryResponse,
  RunHistoryStep,
  SidebarNodeDefinition,
  WorkflowClipboardPayload,
  WorkflowExecution,
  WorkflowExecutionNode,
  WorkflowExecutionStatus,
  WorkflowSnapshot,
} from "@features/workflow/pages/workflow-canvas/helpers/types";

interface WorkflowCanvasProps {
  initialNodes?: CanvasNode[];
  initialEdges?: CanvasEdge[];
}

export default function WorkflowCanvas({
  initialNodes = [],
  initialEdges = [],
}: WorkflowCanvasProps) {
  const { workflowId } = useParams<{ workflowId?: string }>();
  const navigate = useNavigate();

  const {
    nodes,
    edges,
    nodesRef,
    edgesRef,
    latestNodesRef,
    isRestoringRef,
    onNodesChange: handleNodesChange,
    onEdgesChange: handleEdgesChange,
    setNodes,
    setEdges,
    setNodesState,
    setEdgesState,
    createSnapshot,
    recordSnapshot,
    applySnapshot,
    handleUndo,
    handleRedo,
    canUndo,
    canRedo,
  } = useWorkflowCanvasHistory({ initialNodes, initialEdges });

  const [workflowName, setWorkflowName] = useState("New Workflow");
  const [workflowDescription, setWorkflowDescription] = useState("");
  const [currentWorkflowId, setCurrentWorkflowId] = useState<string | null>(
    workflowId ?? null,
  );
  const [workflowVersions, setWorkflowVersions] = useState<
    StoredWorkflow["versions"]
  >([]);
  const [workflowTags, setWorkflowTags] = useState<string[]>(["draft"]);
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
  const runtimeCacheKey = getRuntimeCacheStorageKey(workflowId ?? null);
  const [nodeRuntimeCache, setNodeRuntimeCache] = useState<
    Record<string, NodeRuntimeCacheEntry>
  >(() => readRuntimeCacheFromSession(runtimeCacheKey));
  const previousRuntimeCacheKeyRef = useRef(runtimeCacheKey);
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const reactFlowInstance = useRef<ReactFlowInstance<
    CanvasNode,
    CanvasEdge
  > | null>(null);

  // State for UI controls
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("canvas");
  const {
    isSearchOpen,
    setIsSearchOpen,
    searchMatches,
    setSearchMatches,
    currentSearchIndex,
    setCurrentSearchIndex,
    searchMatchSet,
    handleSearchNodes,
    handleHighlightNext,
    handleHighlightPrevious,
    handleCloseSearch,
    handleToggleSearch,
  } = useWorkflowSearch({
    nodesRef,
    reactFlowInstance,
  });
  const {
    decoratedNodes,
    resolveNodeLabel,
    deleteNodes,
    handleDeleteNode,
    handleUpdateStickyNoteNode,
  } = useWorkflowNodeState({
    nodes,
    searchMatches,
    searchMatchSet,
    isSearchOpen,
    currentSearchIndex,
    nodesRef,
    edgesRef,
    latestNodesRef,
    isRestoringRef,
    setNodes,
    setNodesState,
    setEdgesState,
    recordSnapshot,
    setNodeRuntimeCache,
    setValidationErrors,
    setSearchMatches,
    setSelectedNodeId,
    setActiveChatNodeId,
    setIsChatOpen,
    activeChatNodeId,
  });
  const [hoveredEdgeId, setHoveredEdgeId] = useState<string | null>(null);
  const selectedNode = useMemo(() => {
    if (!selectedNodeId) {
      return null;
    }
    return nodes.find((node) => node.id === selectedNodeId) ?? null;
  }, [nodes, selectedNodeId]);

  const backendBaseUrl = getBackendBaseUrl();
  const user = useMemo(
    () => ({
      id: "user-1",
      name: "Avery Chen",
      avatar: "https://avatar.vercel.sh/avery",
    }),
    [],
  );
  const {
    isChatOpen,
    setIsChatOpen,
    activeChatNodeId,
    setActiveChatNodeId,
    chatTitle,
    setChatTitle,
    handleOpenChat,
    handleChatResponseStart,
    handleChatResponseEnd,
    handleChatClientTool,
    attachChatHandlerToNode,
  } = useWorkflowChat({
    nodesRef,
    setNodes,
    workflowId,
    backendBaseUrl,
    userName: user.name,
  });
  const ai = useMemo(
    () => ({
      id: "ai-1",
      name: "Orcheo Canvas Assistant",
      avatar: "https://avatar.vercel.sh/orcheo-canvas",
    }),
    [],
  );
  const {
    credentials,
    isCredentialsLoading,
    handleAddCredential,
    handleDeleteCredential,
  } = useWorkflowCredentials({
    routeWorkflowId: workflowId,
    currentWorkflowId,
    backendBaseUrl,
    userName: user.name,
  });
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

  const clipboardRef = useRef<WorkflowClipboardPayload | null>(null);
  const pasteOffsetStepRef = useRef(0);
  const lastClipboardSignatureRef = useRef<string | null>(null);

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

  const handleCreateSubworkflow = useMemo(
    () =>
      createHandleCreateSubworkflow({
        getSelectedNodes: () =>
          nodesRef.current.filter((node) => node.selected),
        setSubworkflows,
      }),
    [nodesRef, setSubworkflows],
  );

  const handleDeleteSubworkflow = useMemo(
    () =>
      createHandleDeleteSubworkflow({
        setSubworkflows,
      }),
    [setSubworkflows],
  );

  const runPublishValidation = useMemo(
    () =>
      createRunPublishValidation({
        getNodes: () => nodesRef.current,
        getEdges: () => edgesRef.current,
        setValidationErrors,
        setIsValidating,
        setLastValidationRun,
      }),
    [
      nodesRef,
      edgesRef,
      setValidationErrors,
      setIsValidating,
      setLastValidationRun,
    ],
  );

  const handleDismissValidation = useMemo(
    () =>
      createHandleDismissValidation({
        setValidationErrors,
      }),
    [setValidationErrors],
  );

  const handleFixValidation = useMemo(
    () =>
      createHandleFixValidation({
        getNodes: () => nodesRef.current,
        setActiveTab,
        setSelectedNodeId,
        reactFlowInstance,
      }),
    [nodesRef, setActiveTab, setSelectedNodeId, reactFlowInstance],
  );

  const convertPersistedNodesToCanvas = useCallback(
    (persistedNodes: PersistedWorkflowNode[]) =>
      persistedNodes
        .map((node) => toCanvasNodeBase(node))
        .map(attachChatHandlerToNode),
    [attachChatHandlerToNode],
  );

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (hoveredEdgeId && !edges.some((edge) => edge.id === hoveredEdgeId)) {
      setHoveredEdgeId(null);
    }
  }, [edges, hoveredEdgeId, setHoveredEdgeId]);


  const handleInsertSubworkflow = useMemo(
    () =>
      createHandleInsertSubworkflow({
        nodesRef,
        setNodes,
        setEdges,
        setSubworkflows,
        convertPersistedNodesToCanvas,
        convertPersistedEdgesToCanvas,
        setSelectedNodeId,
        setActiveTab,
        reactFlowInstance,
      }),
    [
      nodesRef,
      setNodes,
      setEdges,
      setSubworkflows,
      convertPersistedNodesToCanvas,
      convertPersistedEdgesToCanvas,
      setSelectedNodeId,
      setActiveTab,
      reactFlowInstance,
    ],
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
        } as CanvasEdge;
      })
      .filter(Boolean) as CanvasEdge[];

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

    const executionEdges: CanvasEdge[] = edges.map((edge) => ({
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
      applySnapshot({ nodes: [], edges: [] }, { resetHistory: true });
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
