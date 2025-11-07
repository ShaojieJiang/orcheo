import type { Edge, Node } from "@xyflow/react";

export type NodeRuntimeCacheEntry = {
  inputs?: unknown;
  outputs?: unknown;
  messages?: unknown;
  raw?: unknown;
  updatedAt?: string;
};

export interface NodeInspectorProps {
  node?: {
    id: string;
    type: string;
    data: Record<string, unknown>;
  };
  nodes?: Node[];
  edges?: Edge[];
  onClose?: () => void;
  onSave?: (nodeId: string, data: Record<string, unknown>) => void;
  runtimeCache?: Record<string, NodeRuntimeCacheEntry>;
  onCacheRuntime?: (nodeId: string, runtime: NodeRuntimeCacheEntry) => void;
  className?: string;
}

export interface SchemaField {
  name: string;
  type: string;
  path: string;
  description?: string;
}
