import type { Edge, Node } from "@xyflow/react";

export type NodeStatus = "idle" | "running" | "success" | "error" | "warning";

export type CanvasNode = Node<{
  label?: string;
  type?: string;
  status?: NodeStatus;
  [key: string]: unknown;
}>;

export type CanvasEdge = Edge<Record<string, unknown>>;

export interface GraphBuildResult {
  config: {
    nodes: Array<Record<string, unknown>>;
    edges: Array<{ source: string; target: string }>;
    edge_nodes?: Array<Record<string, unknown>>;
    conditional_edges?: Array<{
      source: string;
      path: string;
      mapping: Record<string, string>;
      default?: string;
    }>;
  };
  canvasToGraph: Record<string, string>;
  graphToCanvas: Record<string, string>;
  warnings: string[];
}

export type GraphEdge = { source: string; target: string };

export type ConditionalEdge = {
  source: string;
  path: string;
  mapping: Record<string, string>;
  default?: string;
};

export type MaybeYieldFn = () => Promise<void>;

export interface GraphNameMaps {
  canvasToGraph: Record<string, string>;
  graphToCanvas: Record<string, string>;
}

export interface NodeProcessingContext {
  canvasToGraph: Record<string, string>;
  maybeYield: MaybeYieldFn;
  warnings: string[];
}

export interface NodeProcessingArtifacts {
  graphNodes: Array<Record<string, unknown>>;
  graphEdgeNodes: Array<Record<string, unknown>>;
  executableNodes: CanvasNode[];
  branchPathByCanvasId: Record<string, string>;
  defaultBranchKeyByCanvasId: Record<string, string | undefined>;
  decisionNodeNameByCanvasId: Record<string, string>;
  decisionNodeTypeByCanvasId: Record<string, string>;
}

export interface EdgeProcessingParams {
  edges: CanvasEdge[];
  canvasToGraph: Record<string, string>;
  branchPathByCanvasId: Record<string, string>;
  defaultBranchKeyByCanvasId: Record<string, string | undefined>;
  decisionNodeNameByCanvasId: Record<string, string>;
  decisionNodeTypeByCanvasId: Record<string, string>;
  maybeYield: MaybeYieldFn;
}

export interface EdgeProcessingResult {
  graphEdges: GraphEdge[];
  conditionalEdges: ConditionalEdge[];
}

export interface TerminalConnectionParams {
  executableNodes: CanvasNode[];
  canvasToGraph: Record<string, string>;
  graphEdges: GraphEdge[];
  conditionalEdges: ConditionalEdge[];
  maybeYield: MaybeYieldFn;
}
