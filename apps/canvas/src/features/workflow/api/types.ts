export interface AuditRecord {
  actor: string;
  action: string;
  at: string;
  metadata: Record<string, unknown>;
}

export interface WorkflowSummary {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  tags: string[];
  is_archived: boolean;
  created_at: string;
  updated_at: string;
  audit_log: AuditRecord[];
}

export interface CanvasGraphNodeData {
  label?: string;
  description?: string;
  status?: string;
  [key: string]: unknown;
}

export interface CanvasGraphNode {
  id: string;
  type?: string;
  position?: { x: number; y: number };
  data?: CanvasGraphNodeData;
  style?: Record<string, unknown>;
  draggable?: boolean;
  [key: string]: unknown;
}

export interface CanvasGraphEdge {
  id?: string;
  source: string;
  target: string;
  sourceHandle?: string | null;
  targetHandle?: string | null;
  type?: string;
  animated?: boolean;
  label?: string;
  style?: Record<string, unknown>;
  markerEnd?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface CanvasGraphDefinition {
  format?: string;
  nodes?: CanvasGraphNode[];
  edges?: CanvasGraphEdge[];
  [key: string]: unknown;
}

export interface WorkflowVersionRecord {
  id: string;
  workflow_id: string;
  version: number;
  graph: CanvasGraphDefinition;
  metadata: Record<string, unknown>;
  notes?: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
  audit_log: AuditRecord[];
}

export interface WorkflowVersionDiffResponse {
  base_version: number;
  target_version: number;
  diff: string[];
}
