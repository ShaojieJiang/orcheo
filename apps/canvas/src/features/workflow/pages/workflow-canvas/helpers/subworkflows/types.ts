import type {
  WorkflowEdge as PersistedWorkflowEdge,
  WorkflowNode as PersistedWorkflowNode,
} from "@features/workflow/data/workflow-data";

export type SubworkflowStructure = {
  nodes: PersistedWorkflowNode[];
  edges: PersistedWorkflowEdge[];
};
