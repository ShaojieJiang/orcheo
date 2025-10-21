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

import TopNavigation from "@features/shared/components/top-navigation";
import SidebarPanel from "@features/workflow/components/panels/sidebar-panel";
import WorkflowNode from "@features/workflow/components/nodes/workflow-node";
import WorkflowControls from "@features/workflow/components/canvas/workflow-controls";
import WorkflowSearch from "@features/workflow/components/canvas/workflow-search";
import NodeInspector from "@features/workflow/components/panels/node-inspector";
import ChatTriggerNode from "@features/workflow/components/nodes/chat-trigger-node";
import ChatInterface from "@features/shared/components/chat-interface";
import type { Attachment } from "@features/shared/components/chat-input";
import WorkflowExecutionHistory, {
  type WorkflowExecution as HistoryWorkflowExecution,
} from "@features/workflow/components/panels/workflow-execution-history";
import WorkflowTabs from "@features/workflow/components/panels/workflow-tabs";
import WorkflowHistory from "@features/workflow/components/panels/workflow-history";
import ConnectionValidator, {
  validateConnection,
  validateNodeCredentials,
  type ValidationError,
} from "@features/workflow/components/canvas/connection-validator";
import WorkflowGovernancePanel, {
  type SubworkflowTemplate,
} from "@features/workflow/components/panels/workflow-governance-panel";
import StartEndNode from "@features/workflow/components/nodes/start-end-node";
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
} from "@features/workflow/components/dialogs/credentials-vault";
import {
  useWorkflowRunner,
  type TokenMetrics,
  type WorkflowStreamMessage,
} from "@features/workflow/hooks/use-workflow-runner";
import {
  fetchExecutionHistory,
  replayExecution,
  type RunHistoryResponse,
} from "@features/workflow/api/executions";

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

const generateRandomId = (prefix: string) => {
  if (
    typeof globalThis.crypto !== "undefined" &&
    "randomUUID" in globalThis.crypto &&
    typeof globalThis.crypto.randomUUID === "function"
  ) {
    return `${prefix}-${globalThis.crypto.randomUUID()}`;
  }

  const timestamp = Date.now().toString(36);
  const randomSuffix = Math.random().toString(36).slice(2, 8);
  return `${prefix}-${timestamp}-${randomSuffix}`;
};

const generateNodeId = () => generateRandomId("node");

type SubworkflowStructure = {
  nodes: PersistedWorkflowNode[];
  edges: PersistedWorkflowEdge[];
};

const SUBWORKFLOW_LIBRARY: Record<string, SubworkflowStructure> = {
  "subflow-customer-onboarding": {
    nodes: [
      {
        id: "capture-intake",
        type: "trigger",
        position: { x: 0, y: 0 },
        data: {
          type: "trigger",
          label: "Capture intake request",
          description: "Webhook triggered when a signup is submitted.",
          status: "idle",
        },
      },
      {
        id: "enrich-profile",
        type: "function",
        position: { x: 260, y: 0 },
        data: {
          type: "function",
          label: "Enrich CRM profile",
          description: "Collect firmographic data for the new customer.",
          status: "idle",
        },
      },
      {
        id: "provision-access",
        type: "api",
        position: { x: 520, y: 0 },
        data: {
          type: "api",
          label: "Provision access",
          description: "Create accounts across internal and SaaS tools.",
          status: "idle",
        },
      },
      {
        id: "send-welcome",
        type: "api",
        position: { x: 780, y: 0 },
        data: {
          type: "api",
          label: "Send welcome sequence",
          description: "Kick off emails, docs, and success team handoff.",
          status: "idle",
        },
      },
    ],
    edges: [
      {
        id: "edge-capture-enrich",
        source: "capture-intake",
        target: "enrich-profile",
      },
      {
        id: "edge-enrich-provision",
        source: "enrich-profile",
        target: "provision-access",
      },
      {
        id: "edge-provision-welcome",
        source: "provision-access",
        target: "send-welcome",
      },
    ],
  },
  "subflow-incident-response": {
    nodes: [
      {
        id: "incident-raised",
        type: "trigger",
        position: { x: 0, y: 0 },
        data: {
          type: "trigger",
          label: "PagerDuty incident raised",
          description: "Triggered when a Sev1 alert fires.",
          status: "idle",
        },
      },
      {
        id: "triage-severity",
        type: "function",
        position: { x: 260, y: 0 },
        data: {
          type: "function",
          label: "Triage severity",
          description: "Evaluate runbooks and required responders.",
          status: "idle",
        },
      },
      {
        id: "notify-oncall",
        type: "api",
        position: { x: 520, y: -120 },
        data: {
          type: "api",
          label: "Notify on-call",
          description: "Post critical details into the on-call channel.",
          status: "idle",
        },
      },
      {
        id: "escalate-leads",
        type: "api",
        position: { x: 520, y: 120 },
        data: {
          type: "api",
          label: "Escalate to leads",
          description: "Escalate if no acknowledgement within SLA.",
          status: "idle",
        },
      },
      {
        id: "update-status",
        type: "function",
        position: { x: 780, y: 0 },
        data: {
          type: "function",
          label: "Update status page",
          description: "Publish current impact for stakeholders.",
          status: "idle",
        },
      },
    ],
    edges: [
      {
        id: "edge-raised-triage",
        source: "incident-raised",
        target: "triage-severity",
      },
      {
        id: "edge-triage-notify",
        source: "triage-severity",
        target: "notify-oncall",
      },
      {
        id: "edge-triage-escalate",
        source: "triage-severity",
        target: "escalate-leads",
      },
      {
        id: "edge-notify-update",
        source: "notify-oncall",
        target: "update-status",
      },
      {
        id: "edge-escalate-update",
        source: "escalate-leads",
        target: "update-status",
      },
    ],
  },
  "subflow-content-qa": {
    nodes: [
      {
        id: "draft-ready",
        type: "trigger",
        position: { x: 0, y: 0 },
        data: {
          type: "trigger",
          label: "Draft ready for review",
          description: "Start QA once an AI draft is submitted.",
          status: "idle",
        },
      },
      {
        id: "score-quality",
        type: "ai",
        position: { x: 260, y: 0 },
        data: {
          type: "ai",
          label: "Score quality",
          description: "Use AI rubric to score voice, tone, and accuracy.",
          status: "idle",
        },
      },
      {
        id: "collect-feedback",
        type: "function",
        position: { x: 520, y: -120 },
        data: {
          type: "function",
          label: "Collect revisions",
          description: "Request edits from stakeholders when needed.",
          status: "idle",
        },
      },
      {
        id: "schedule-publish",
        type: "api",
        position: { x: 520, y: 120 },
        data: {
          type: "api",
          label: "Schedule publish",
          description: "Queue approved content in the CMS calendar.",
          status: "idle",
        },
      },
      {
        id: "final-approval",
        type: "function",
        position: { x: 780, y: 0 },
        data: {
          type: "function",
          label: "Finalize and log",
          description: "Capture QA notes and mark the run complete.",
          status: "idle",
        },
      },
    ],
    edges: [
      {
        id: "edge-draft-score",
        source: "draft-ready",
        target: "score-quality",
      },
      {
        id: "edge-score-feedback",
        source: "score-quality",
        target: "collect-feedback",
      },
      {
        id: "edge-score-schedule",
        source: "score-quality",
        target: "schedule-publish",
      },
      {
        id: "edge-feedback-final",
        source: "collect-feedback",
        target: "final-approval",
      },
      {
        id: "edge-schedule-final",
        source: "schedule-publish",
        target: "final-approval",
      },
    ],
  },
};

interface NodeData {
  type: string;
  label: string;
  description?: string;
  status: "idle" | "running" | "success" | "error" | "warning";
  icon?: React.ReactNode;
  onOpenChat?: () => void;
  isDisabled?: boolean;
  [key: string]: unknown;
}

type CanvasNode = Node<NodeData>;
type CanvasEdge = Edge<Record<string, unknown>>;

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

// Update the WorkflowExecution interface to match the component's expectations
type WorkflowExecutionStatus = "running" | "success" | "failed" | "partial";
type NodeStatus = "idle" | "running" | "success" | "error" | "warning";

interface WorkflowExecutionNode {
  id: string;
  type: string;
  name: string;
  position: { x: number; y: number };
  status: NodeStatus;
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
  tokenMetrics?: TokenMetrics;
}

type WorkflowExecutionLogEntry = WorkflowExecution["logs"][number];

const LOG_TIME_FORMAT: Intl.DateTimeFormatOptions = {
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
};

const MAX_LOG_ENTRIES = 200;

const escapePythonString = (value: string): string =>
  value.replace(/\\/g, "\\\\").replace(/"/g, '\\"');

const normaliseStatus = (status: string | undefined): string | undefined =>
  typeof status === "string" ? status.toLowerCase() : undefined;

const summariseStreamMessage = (message: WorkflowStreamMessage): string => {
  if (
    typeof message.message === "string" &&
    message.message.trim().length > 0
  ) {
    return message.message;
  }
  if (typeof message.event === "string" && typeof message.node === "string") {
    return `${message.event} (${message.node})`;
  }
  if (typeof message.status === "string" && typeof message.node === "string") {
    return `${message.node} -> ${message.status}`;
  }
  try {
    const serialised = JSON.stringify(message);
    return serialised?.length ? serialised : "Workflow update received";
  } catch (error) {
    console.warn("Failed to serialise workflow message", error);
    return "Workflow update received";
  }
};

const determineLogLevel = (
  message: WorkflowStreamMessage,
): WorkflowExecutionLogEntry["level"] => {
  const status = normaliseStatus(message.status);
  if (status && ["error", "failed"].includes(status)) {
    return "ERROR";
  }
  if (status === "running") {
    return "DEBUG";
  }
  if (status === "partial" || status === "cancelled") {
    return "WARNING";
  }
  return "INFO";
};

const determineNodeStatus = (
  message: WorkflowStreamMessage,
): NodeStatus | null => {
  const status = normaliseStatus(message.status);
  if (!status) {
    const event =
      typeof message.event === "string"
        ? message.event.toLowerCase()
        : undefined;
    if (!event) {
      return null;
    }
    if (event.includes("start")) {
      return "running";
    }
    if (event.includes("complete") || event.includes("finish")) {
      return "success";
    }
    if (event.includes("error") || event.includes("fail")) {
      return "error";
    }
    return null;
  }

  if (["running", "in_progress"].includes(status)) {
    return "running";
  }
  if (["completed", "success"].includes(status)) {
    return "success";
  }
  if (["error", "failed"].includes(status)) {
    return "error";
  }
  if (["partial", "cancelled"].includes(status)) {
    return "warning";
  }
  return null;
};

const buildExecutionGraphConfig = (
  nodes: CanvasNode[],
  edges: CanvasEdge[],
) => {
  const graphNodes: Array<Record<string, unknown>> = [
    { name: "START", type: "START" },
    { name: "END", type: "END" },
  ];

  nodes.forEach((node) => {
    const label = String(node.data?.label ?? node.id);
    const safeLabel = escapePythonString(label);
    graphNodes.push({
      name: node.id,
      type: "PythonCode",
      code: `return {"node": "${safeLabel}", "label": "${safeLabel}"}`,
    });
  });

  const graphEdges: Array<[string, string]> = [];
  edges.forEach((edge) => {
    if (edge.source && edge.target) {
      graphEdges.push([edge.source, edge.target]);
    }
  });

  const nodeIds = new Set(nodes.map((node) => node.id));
  const sources = new Set(edges.map((edge) => edge.source));
  const targets = new Set(edges.map((edge) => edge.target));

  nodeIds.forEach((nodeId) => {
    if (!targets.has(nodeId)) {
      graphEdges.push(["START", nodeId]);
    }
    if (!sources.has(nodeId)) {
      graphEdges.push([nodeId, "END"]);
    }
  });

  const dedupedEdges = Array.from(
    new Set(graphEdges.map((edge) => edge.join("->"))),
  ).map((entry) => {
    const [source, target] = entry.split("->");
    return [source, target] as [string, string];
  });

  return {
    nodes: graphNodes,
    edges: dedupedEdges,
  };
};

const createExecutionFromCanvas = (
  executionId: string,
  nodes: CanvasNode[],
  edges: CanvasEdge[],
): WorkflowExecution => {
  const now = new Date().toISOString();
  const workflowNodes: WorkflowExecutionNode[] = nodes.map((node) => ({
    id: node.id,
    type: node.data?.type ?? node.type ?? "default",
    name: String(node.data?.label ?? node.id),
    position: {
      x: node.position?.x ?? 0,
      y: node.position?.y ?? 0,
    },
    status: (node.data?.status ?? "idle") as NodeStatus,
    details: node.data?.details as Record<string, unknown> | undefined,
  }));

  const workflowEdges: WorkflowEdge[] = edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
  }));

  return {
    id: executionId,
    runId: executionId,
    status: "running",
    startTime: now,
    duration: 0,
    issues: 0,
    nodes: workflowNodes,
    edges: workflowEdges,
    logs: [],
    tokenMetrics: {
      inputTokens: 0,
      outputTokens: 0,
      totalTokens: 0,
    },
  };
};

const updateExecutionFromMessage = (
  execution: WorkflowExecution,
  message: WorkflowStreamMessage,
): WorkflowExecution => {
  const now = new Date();
  const timestamp = now.toLocaleTimeString([], LOG_TIME_FORMAT);
  const logEntry: WorkflowExecutionLogEntry = {
    timestamp,
    level: determineLogLevel(message),
    message: summariseStreamMessage(message),
  };

  const status = normaliseStatus(message.status);
  let nextStatus = execution.status;
  let endTime = execution.endTime;
  let issues = execution.issues;

  if (logEntry.level === "ERROR") {
    issues += 1;
  }

  if (status) {
    if (["completed", "success"].includes(status)) {
      nextStatus = "success";
      endTime = now.toISOString();
    } else if (["error", "failed"].includes(status)) {
      nextStatus = "failed";
      endTime = now.toISOString();
      issues = Math.max(issues, 1);
    } else if (["partial", "cancelled"].includes(status)) {
      nextStatus = "partial";
      endTime = now.toISOString();
    } else if (["running", "in_progress"].includes(status)) {
      nextStatus = "running";
    }
  }

  const nodeId = typeof message.node === "string" ? message.node : null;
  const nodeStatus = determineNodeStatus(message);
  const updatedNodes = nodeId
    ? execution.nodes.map((node) => {
        if (node.id !== nodeId) {
          return node;
        }
        return {
          ...node,
          status: nodeStatus ?? node.status,
        };
      })
    : execution.nodes;

  const duration = endTime
    ? Math.max(
        new Date(endTime).getTime() - new Date(execution.startTime).getTime(),
        0,
      )
    : Math.max(now.getTime() - new Date(execution.startTime).getTime(), 0);

  const logs = [...execution.logs, logEntry].slice(-MAX_LOG_ENTRIES);

  return {
    ...execution,
    status: nextStatus,
    endTime,
    duration,
    issues,
    logs,
    nodes: updatedNodes,
  };
};

const updateExecutionFromHistory = (
  execution: WorkflowExecution,
  history: RunHistoryResponse,
): WorkflowExecution => {
  const logs: WorkflowExecutionLogEntry[] = history.steps.map((step) => ({
    timestamp: new Date(step.at).toLocaleTimeString([], LOG_TIME_FORMAT),
    level: determineLogLevel(step.payload as WorkflowStreamMessage),
    message: summariseStreamMessage(step.payload as WorkflowStreamMessage),
  }));

  const status = normaliseStatus(history.status);
  let executionStatus: WorkflowExecutionStatus = execution.status;
  if (status) {
    if (["completed", "success"].includes(status)) {
      executionStatus = "success";
    } else if (["error", "failed"].includes(status)) {
      executionStatus = "failed";
    } else if (["partial", "cancelled"].includes(status)) {
      executionStatus = "partial";
    } else if (["running", "pending"].includes(status)) {
      executionStatus = "running";
    }
  }

  const endTime = history.completed_at ?? execution.endTime;
  const startTime = history.started_at ?? execution.startTime;
  const duration = endTime
    ? Math.max(new Date(endTime).getTime() - new Date(startTime).getTime(), 0)
    : execution.duration;

  const issues = history.error
    ? Math.max(execution.issues, 1)
    : logs.filter((entry) => entry.level === "ERROR").length ||
      execution.issues;

  return {
    ...execution,
    status: executionStatus,
    startTime,
    endTime: endTime ?? execution.endTime,
    duration,
    issues,
    logs,
  };
};

const INITIAL_EXECUTIONS: WorkflowExecution[] = [
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
    tokenMetrics: {
      inputTokens: 128,
      outputTokens: 64,
      totalTokens: 192,
      lastUpdatedAt: new Date().toISOString(),
    },
  },
  {
    id: "2",
    runId: "843",
    status: "failed",
    startTime: new Date("2023-11-04T15:45:10").toISOString(),
    duration: 58200,
    issues: 2,
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
    tokenMetrics: {
      inputTokens: 256,
      outputTokens: 128,
      totalTokens: 384,
      lastUpdatedAt: new Date().toISOString(),
    },
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
    tokenMetrics: {
      inputTokens: 96,
      outputTokens: 48,
      totalTokens: 144,
      lastUpdatedAt: new Date().toISOString(),
    },
  },
];

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
  const [credentials, setCredentials] = useState<Credential[]>([
    {
      id: "cred-openai-prod",
      name: "OpenAI Production",
      type: "api",
      createdAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 12).toISOString(),
      updatedAt: new Date(Date.now() - 1000 * 60 * 45).toISOString(),
      owner: "Avery Chen",
      access: "shared",
      secrets: { apiKey: "sk-orcheo-prod-***" },
    },
    {
      id: "cred-slack-staging",
      name: "Slack Staging Bot",
      type: "api",
      createdAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 35).toISOString(),
      updatedAt: new Date(Date.now() - 1000 * 60 * 60 * 5).toISOString(),
      owner: "Jordan Patel",
      access: "private",
      secrets: { apiKey: "xoxb-staging-***" },
    },
  ]);
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
  const [executions, setExecutions] =
    useState<WorkflowExecution[]>(INITIAL_EXECUTIONS);
  const [activeExecutionId, setActiveExecutionId] = useState<string | null>(
    INITIAL_EXECUTIONS[0]?.id ?? null,
  );
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);

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
  const [activeChatNodeId, setActiveChatNodeId] = useState<string | null>(null);
  const [chatTitle, setChatTitle] = useState("Chat");

  const undoStackRef = useRef<WorkflowSnapshot[]>([]);
  const redoStackRef = useRef<WorkflowSnapshot[]>([]);
  const isRestoringRef = useRef(false);
  const nodesRef = useRef<CanvasNode[]>(nodes);
  const edgesRef = useRef<CanvasEdge[]>(edges);

  const handleAddCredential = useCallback((credential: CredentialInput) => {
    const timestamp = new Date().toISOString();
    const owner = credential.owner ?? "Avery Chen";

    const credentialRecord: Credential = {
      ...credential,
      owner,
      id: generateRandomId("cred"),
      createdAt: timestamp,
      updatedAt: timestamp,
    };

    setCredentials((prev) => [...prev, credentialRecord]);
    toast({
      title: "Credential added to vault",
      description: `${credentialRecord.name} is now available for nodes that require secure access.`,
    });
  }, []);

  const handleDeleteCredential = useCallback((id: string) => {
    setCredentials((prev) => prev.filter((credential) => credential.id !== id));
    toast({
      title: "Credential removed",
      description:
        "Nodes referencing this credential will require reconfiguration before publish.",
    });
  }, []);

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
          setSelectedNode(nodeToFocus);
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
    [nodes, setActiveTab, setSelectedNode],
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

  const handleStreamMessage = useCallback(
    (
      message: WorkflowStreamMessage,
      { executionId }: { executionId: string },
    ) => {
      setExecutions((previous) =>
        previous.map((execution) =>
          execution.id === executionId
            ? updateExecutionFromMessage(execution, message)
            : execution,
        ),
      );

      if (typeof message.node === "string") {
        const nodeStatus = determineNodeStatus(message);
        if (nodeStatus) {
          setNodes((current) =>
            current.map((node) =>
              node.id === message.node
                ? {
                    ...node,
                    data: {
                      ...node.data,
                      status: nodeStatus,
                    },
                  }
                : node,
            ),
          );
        }
      }
    },
    [setExecutions, setNodes],
  );

  const handleRunnerComplete = useCallback(
    ({ executionId }: { executionId: string }) => {
      setIsRunning(false);
      setActiveExecutionId(executionId);
    },
    [],
  );

  const handleRunnerError = useCallback(
    (error: Error, context: { executionId: string } | null) => {
      if (context?.executionId) {
        setExecutions((previous) =>
          previous.map((execution) =>
            execution.id === context.executionId
              ? updateExecutionFromMessage(execution, {
                  status: "error",
                  error: error.message,
                })
              : execution,
          ),
        );
      }

      toast({
        title: "Workflow execution error",
        description: error.message,
        variant: "destructive",
      });
      setIsRunning(false);
    },
    [setExecutions],
  );

  const {
    status: runnerStatus,
    executionId: runnerExecutionId,
    runWorkflow: triggerWorkflowRun,
    cancel: cancelWorkflowRun,
    metrics: runnerMetrics,
  } = useWorkflowRunner(workflowId ?? null, {
    onMessage: handleStreamMessage,
    onError: (error, context) => handleRunnerError(error, context),
    onComplete: handleRunnerComplete,
  });

  useEffect(() => {
    if (!runnerExecutionId) {
      return;
    }
    setActiveExecutionId(runnerExecutionId);
  }, [runnerExecutionId]);

  useEffect(() => {
    if (!runnerExecutionId) {
      return;
    }
    setExecutions((previous) =>
      previous.map((execution) =>
        execution.id === runnerExecutionId
          ? {
              ...execution,
              tokenMetrics: {
                inputTokens: runnerMetrics.inputTokens,
                outputTokens: runnerMetrics.outputTokens,
                totalTokens: runnerMetrics.totalTokens,
                lastUpdatedAt: runnerMetrics.lastUpdatedAt,
              },
            }
          : execution,
      ),
    );
  }, [runnerExecutionId, runnerMetrics, setExecutions]);

  useEffect(() => {
    if (runnerStatus === "streaming" || runnerStatus === "connecting") {
      setIsRunning(true);
      return;
    }
    if (runnerStatus === "completed" || runnerStatus === "error") {
      setIsRunning(false);
    }
  }, [runnerStatus]);

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

      const remappedNodes = libraryEntry.nodes.map((node) => {
        const newId = generateNodeId();
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
        setSelectedNode(canvasNodes[0]);
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
      setSelectedNode,
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

  const handleSaveWorkflow = useCallback(() => {
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
  const handleSendChatMessage = (
    message: string,
    attachments: Attachment[],
  ) => {
    if (!activeChatNodeId) {
      toast({
        title: "Select a chat-enabled node",
        description: "Open a node chat to send messages.",
      });
      return;
    }

    const activeNode = nodes.find((node) => node.id === activeChatNodeId);
    const attachmentSummary =
      attachments.length === 0
        ? ""
        : attachments.length === 1
          ? " with 1 attachment"
          : ` with ${attachments.length} attachments`;

    toast({
      title: `Message sent to ${activeNode?.data?.label ?? "workflow"}`,
      description: `"${message}"${attachmentSummary}`,
    });

    // Here you would typically process the message and trigger the workflow
    // For now, we'll just update the node status to simulate activity
    setNodes((nds) =>
      nds.map((n) => {
        if (n.id === activeChatNodeId) {
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

    // Simulate workflow execution
    setTimeout(() => {
      setNodes((nds) =>
        nds.map((n) => {
          if (n.id === activeChatNodeId) {
            return {
              ...n,
              data: {
                ...n.data,
                status: "success" as NodeStatus,
              },
            };
          }
          return n;
        }),
      );
    }, 2000);
  };

  // Handle workflow execution
  const handleRunWorkflow = useCallback(async () => {
    if (!workflowId) {
      toast({
        title: "Workflow identifier required",
        description:
          "Save this workflow or open an existing workflow before running it.",
        variant: "destructive",
      });
      return;
    }

    const graphConfig = buildExecutionGraphConfig(
      nodesRef.current,
      edgesRef.current,
    );
    const inputs = {
      workflow_id: workflowId,
      triggered_at: new Date().toISOString(),
      selected_node: selectedNode?.id ?? null,
    };

    try {
      const executionId = await triggerWorkflowRun({
        graphConfig,
        inputs,
      });

      setExecutions((previous) => [
        createExecutionFromCanvas(
          executionId,
          nodesRef.current,
          edgesRef.current,
        ),
        ...previous.filter((execution) => execution.id !== executionId),
      ]);
      setActiveExecutionId(executionId);

      toast({
        title: "Workflow execution started",
        description: `Run ${executionId} is streaming live updates.`,
      });
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Failed to start the workflow execution.";
      toast({
        title: "Unable to start execution",
        description: message,
        variant: "destructive",
      });
      setIsRunning(false);
    }
  }, [selectedNode?.id, triggerWorkflowRun, workflowId]);

  // Handle workflow pause
  const handlePauseWorkflow = useCallback(() => {
    cancelWorkflowRun();
    setIsRunning(false);

    if (runnerExecutionId) {
      const timestamp = new Date().toLocaleTimeString([], LOG_TIME_FORMAT);
      setExecutions((previous) =>
        previous.map((execution) =>
          execution.id === runnerExecutionId
            ? {
                ...execution,
                status: "partial",
                endTime: new Date().toISOString(),
                logs: [
                  ...execution.logs,
                  {
                    timestamp,
                    level: "WARNING",
                    message: "Execution paused from the canvas",
                  },
                ].slice(-MAX_LOG_ENTRIES),
              }
            : execution,
        ),
      );
    }

    setNodes((nds) =>
      nds.map((n) =>
        n.data.status === "running"
          ? {
              ...n,
              data: {
                ...n.data,
                status: "idle" as NodeStatus,
              },
            }
          : n,
      ),
    );
  }, [cancelWorkflowRun, runnerExecutionId, setExecutions, setNodes]);

  const handleRefreshExecutionHistory = useCallback(async () => {
    if (isHistoryLoading) {
      return;
    }
    const executionId = activeExecutionId ?? executions[0]?.id ?? null;
    if (!executionId) {
      toast({
        title: "No executions to refresh",
        description: "Run a workflow to view live execution history.",
      });
      return;
    }

    setIsHistoryLoading(true);
    try {
      const history = await fetchExecutionHistory(executionId);
      setExecutions((previous) =>
        previous.map((execution) =>
          execution.id === executionId
            ? updateExecutionFromHistory(execution, history)
            : execution,
        ),
      );
      toast({
        title: "Execution history updated",
        description: "Refreshed run " + executionId + ".",
      });
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Failed to refresh execution history.";
      toast({
        title: "History refresh failed",
        description: message,
        variant: "destructive",
      });
    } finally {
      setIsHistoryLoading(false);
    }
  }, [activeExecutionId, executions, isHistoryLoading]);

  const handleReplayExecution = useCallback(
    async (execution: WorkflowExecution) => {
      if (isHistoryLoading) {
        return;
      }
      setIsHistoryLoading(true);
      try {
        const history = await replayExecution(execution.id, 0);
        setExecutions((previous) =>
          previous.map((item) =>
            item.id === execution.id
              ? updateExecutionFromHistory(item, history)
              : item,
          ),
        );
        toast({
          title: "Replay data loaded",
          description:
            "Loaded " +
            history.steps.length +
            " steps from run " +
            execution.runId +
            ".",
        });
      } catch (error) {
        const message =
          error instanceof Error
            ? error.message
            : "Failed to load execution replay.";
        toast({
          title: "Replay failed",
          description: message,
          variant: "destructive",
        });
      } finally {
        setIsHistoryLoading(false);
      }
    },
    [isHistoryLoading],
  );

  const handleDeleteExecution = useCallback(
    (execution: WorkflowExecution) => {
      setExecutions((previous) =>
        previous.filter((item) => item.id !== execution.id),
      );
      if (activeExecutionId === execution.id) {
        setActiveExecutionId(null);
      }
      toast({
        title: "Execution removed",
        description: "Run " + execution.runId + " removed from the timeline.",
      });
    },
    [activeExecutionId],
  );

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
      setActiveExecutionId(execution.id);
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

  // Load workflow data when workflowId changes
  useEffect(() => {
    const loadWorkflow = () => {
      if (!workflowId) {
        setCurrentWorkflowId(null);
        setWorkflowName("New Workflow");
        setWorkflowDescription("");
        setWorkflowTags(["draft"]);
        setWorkflowVersions([]);
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
      applySnapshot({ nodes: [], edges: [] }, { resetHistory: true });
    };

    loadWorkflow();
  }, [applySnapshot, convertPersistedNodesToCanvas, workflowId]);

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

  // User and AI info for chat
  const user = {
    id: "user-1",
    name: "Avery Chen",
    avatar: "https://avatar.vercel.sh/avery",
  };

  const ai = {
    id: "ai-1",
    name: "Orcheo Canvas Assistant",
    avatar: "https://avatar.vercel.sh/orcheo-canvas",
  };

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
              onCopyToEditor={handleReplayExecution}
              onDelete={handleDeleteExecution}
              defaultSelectedExecution={
                activeExecutionId
                  ? executions.find(
                      (execution) => execution.id === activeExecutionId,
                    )
                  : executions[0]
              }
            />
          </TabsContent>

          <TabsContent value="readiness" className="m-0 p-4 overflow-auto">
            <div className="mx-auto max-w-5xl pb-12">
              <WorkflowGovernancePanel
                credentials={credentials}
                onAddCredential={handleAddCredential}
                onDeleteCredential={handleDeleteCredential}
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
          onClose={handleCloseNodeInspector}
          onSave={handleNodeUpdate}
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
          onSendMessage={handleSendChatMessage}
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
        />
      )}
    </div>
  );
}
