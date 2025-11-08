import type {
  Workflow,
  WorkflowEdge,
  WorkflowNode,
} from "@features/workflow/data/workflow-data";
import type { WorkflowDiffResult, WorkflowSnapshot } from "./workflow-diff";

export interface ApiWorkflow {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  tags: string[];
  is_archived: boolean;
  is_public: boolean;
  require_login: boolean;
  published_at: string | null;
  published_by: string | null;
  publish_token_rotated_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApiWorkflowVersion {
  id: string;
  workflow_id: string;
  version: number;
  graph: Record<string, unknown>;
  metadata: unknown;
  notes: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface CanvasVersionMetadata {
  snapshot?: WorkflowSnapshot;
  summary?: WorkflowDiffResult["summary"];
  message?: string;
  canvasToGraph?: Record<string, string>;
  graphToCanvas?: Record<string, string>;
}

export interface RequestOptions extends RequestInit {
  expectJson?: boolean;
}

export interface WorkflowVersionRecord {
  id: string;
  version: string;
  versionNumber: number;
  timestamp: string;
  message: string;
  author: Workflow["owner"];
  summary: WorkflowDiffResult["summary"];
  snapshot: WorkflowSnapshot;
  graphToCanvas?: Record<string, string>;
}

export interface StoredWorkflow extends Workflow {
  versions: WorkflowVersionRecord[];
  isArchived?: boolean;
}

export interface SaveWorkflowInput {
  id?: string;
  name: string;
  description?: string;
  tags?: string[];
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

export interface SaveWorkflowOptions {
  versionMessage?: string;
  actor?: string;
}
