import type {
  WorkflowExecution,
  WorkflowEdge as HistoryWorkflowEdge,
  WorkflowNode as HistoryWorkflowNode,
} from "@features/workflow/components/panels/workflow-execution-history";
import type {
  StoredWorkflow,
  WorkflowVersionRecord,
} from "@features/workflow/lib/workflow-storage";

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
  inputs?: Record<string, unknown>;
  steps: RunHistoryStepResponse[];
}

export type SnapshotNode = StoredWorkflow["nodes"][number];
export type SnapshotEdge = StoredWorkflow["edges"][number];

export type WorkflowLookup = {
  defaultNodes: SnapshotNode[];
  defaultEdges: SnapshotEdge[];
  defaultMapping: Record<string, string>;
  versions: Map<string, WorkflowVersionRecord>;
};

export type { WorkflowExecution, HistoryWorkflowEdge, HistoryWorkflowNode };
