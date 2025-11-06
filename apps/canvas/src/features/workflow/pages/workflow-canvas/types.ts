import type React from "react";
import type { Edge, Node } from "@xyflow/react";

import type { WorkflowEdge, WorkflowNode } from "@features/workflow/data/workflow-data";
import type { StoredWorkflow } from "@features/workflow/lib/workflow-storage";
import type { Credential } from "@features/workflow/types/credential-vault";

export interface NodeRuntimeData {
  inputs?: unknown;
  outputs?: unknown;
  messages?: unknown;
  raw?: unknown;
  updatedAt: string;
}

export interface NodeData {
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

export type CanvasNode = Node<NodeData>;
export type CanvasEdge = Edge<Record<string, unknown>>;

export interface WorkflowSnapshot {
  nodes: CanvasNode[];
  edges: CanvasEdge[];
}

export interface WorkflowCanvasProps {
  initialNodes?: CanvasNode[];
  initialEdges?: CanvasEdge[];
}

export type WorkflowClipboardPayload = {
  version: 1;
  type: "workflow-selection";
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  copiedAt?: number;
};

export type CopyClipboardOptions = {
  skipSuccessToast?: boolean;
};

export type CopyClipboardResult = {
  success: boolean;
  nodeCount: number;
  edgeCount: number;
  usedFallback: boolean;
};

export type WorkflowExecutionStatus =
  | "running"
  | "success"
  | "failed"
  | "partial";

export type NodeStatus = "idle" | "running" | "success" | "error" | "warning";

export interface WorkflowExecutionNode {
  id: string;
  type: string;
  name: string;
  position: { x: number; y: number };
  status: NodeStatus;
  iconKey?: string;
  details?: Record<string, unknown>;
}

export interface WorkflowExecution {
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

export interface RunHistoryStep {
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
  inputs?: Record<string, unknown>;
  steps: RunHistoryStep[];
}

export interface SidebarNodeDefinition {
  id?: string;
  type?: string;
  name?: string;
  description?: string;
  iconKey?: string;
  icon?: React.ReactNode;
  data?: Record<string, unknown>;
}

export interface WorkflowMetadataState {
  workflowName: string;
  setWorkflowName: React.Dispatch<React.SetStateAction<string>>;
  workflowDescription: string;
  setWorkflowDescription: React.Dispatch<React.SetStateAction<string>>;
  currentWorkflowId: string | null;
  setCurrentWorkflowId: React.Dispatch<React.SetStateAction<string | null>>;
  workflowVersions: StoredWorkflow["versions"];
  setWorkflowVersions: React.Dispatch<
    React.SetStateAction<StoredWorkflow["versions"]>
  >;
  workflowTags: string[];
  setWorkflowTags: React.Dispatch<React.SetStateAction<string[]>>;
}

export interface CredentialState {
  credentials: Credential[];
  setCredentials: React.Dispatch<React.SetStateAction<Credential[]>>;
  isCredentialsLoading: boolean;
  setIsCredentialsLoading: React.Dispatch<React.SetStateAction<boolean>>;
}
