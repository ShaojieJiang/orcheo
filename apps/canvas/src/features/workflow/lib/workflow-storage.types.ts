import type {
  Workflow,
  WorkflowEdge,
  WorkflowNode,
} from "@features/workflow/data/workflow-data";
import type { WorkflowDiffResult, WorkflowSnapshot } from "./workflow-diff";

export interface ApiWorkflow {
  id: string;
  handle?: string | null;
  name: string;
  slug: string;
  description: string | null;
  tags: string[];
  is_archived: boolean;
  is_public: boolean;
  require_login: boolean;
  published_at: string | null;
  published_by: string | null;
  created_at: string;
  updated_at: string;
  share_url?: string | null;
  latest_version?: ApiWorkflowVersion | null;
  is_scheduled?: boolean;
}

export interface PublicWorkflowMetadata {
  id: string;
  handle?: string | null;
  name: string;
  description: string | null;
  is_public: boolean;
  require_login: boolean;
  share_url: string | null;
}

export interface WorkflowRunnableConfig {
  configurable?: Record<string, unknown>;
  run_name?: string;
  tags?: string[];
  metadata?: Record<string, unknown>;
  callbacks?: unknown[];
  recursion_limit?: number;
  max_concurrency?: number;
  prompts?: Record<string, unknown>;
}

export interface ApiWorkflowVersion {
  id: string;
  workflow_id: string;
  version: number;
  graph: Record<string, unknown>;
  mermaid?: string | null;
  metadata: unknown;
  runnable_config?: WorkflowRunnableConfig | null;
  notes: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface ApiWorkflowRun {
  id: string;
  workflow_id: string;
  workflow_version_id: string;
  status: string;
  triggered_by: string;
  input_payload: Record<string, unknown>;
  output_payload?: Record<string, unknown> | null;
  created_at?: string;
  updated_at?: string;
}

export interface WorkflowCredentialReadinessItem {
  name: string;
  placeholders: string[];
  available: boolean;
  credential_id?: string | null;
  provider?: string | null;
}

export interface WorkflowCredentialReadinessResponse {
  workflow_id: string;
  status: "ready" | "missing" | "not_required";
  referenced_credentials: WorkflowCredentialReadinessItem[];
  available_credentials: string[];
  missing_credentials: string[];
}

export interface WorkflowPublishResponse {
  workflow: ApiWorkflow;
  message?: string | null;
  share_url?: string | null;
}

export interface CronTriggerConfig {
  expression: string;
  timezone?: string;
  allow_overlapping?: boolean;
  start_at?: string | null;
  end_at?: string | null;
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
  mermaid?: string | null;
  runnableConfig?: WorkflowRunnableConfig | null;
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
  runnableConfig?: WorkflowRunnableConfig | null;
}
