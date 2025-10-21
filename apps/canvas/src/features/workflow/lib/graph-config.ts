import type { Edge, Node } from "@xyflow/react";

type NodeStatus = "idle" | "running" | "success" | "error" | "warning";

type CanvasNode = Node<{
  label?: string;
  type?: string;
  status?: NodeStatus;
  [key: string]: unknown;
}>;

type CanvasEdge = Edge<Record<string, unknown>>;

export interface GraphBuildResult {
  config: {
    nodes: Array<Record<string, unknown>>;
    edges: Array<{ source: string; target: string }>;
  };
  canvasToGraph: Record<string, string>;
  graphToCanvas: Record<string, string>;
}

const DEFAULT_NODE_CODE = "return state";

const slugify = (value: string, fallback: string): string => {
  const slug = value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .replace(/-{2,}/g, "-");
  return slug || fallback;
};

const ensureUniqueName = (candidate: string, used: Set<string>): string => {
  if (!used.has(candidate)) {
    used.add(candidate);
    return candidate;
  }
  let counter = 2;
  while (used.has(`${candidate}-${counter}`)) {
    counter += 1;
  }
  const unique = `${candidate}-${counter}`;
  used.add(unique);
  return unique;
};

export const buildGraphConfigFromCanvas = (
  nodes: CanvasNode[],
  edges: CanvasEdge[],
): GraphBuildResult => {
  const canvasToGraph: Record<string, string> = {};
  const graphToCanvas: Record<string, string> = {};
  const usedNames = new Set<string>();

  nodes.forEach((node, index) => {
    const label = String(node.data?.label ?? node.id ?? `node-${index + 1}`);
    const base = slugify(label, `node-${index + 1}`);
    const unique = ensureUniqueName(base, usedNames);
    canvasToGraph[node.id] = unique;
    graphToCanvas[unique] = node.id;
  });

  const graphNodes: Array<Record<string, unknown>> = [
    { name: "START", type: "START" },
    ...nodes.map((node, index) => ({
      name: canvasToGraph[node.id],
      type: "PythonCode",
      code: DEFAULT_NODE_CODE,
      display_name: node.data?.label ?? node.id ?? `Node ${index + 1}`,
      canvas_id: node.id,
    })),
    { name: "END", type: "END" },
  ];

  const graphEdges: Array<{ source: string; target: string }> = [];

  edges.forEach((edge) => {
    const source = canvasToGraph[edge.source];
    const target = canvasToGraph[edge.target];
    if (source && target) {
      graphEdges.push({ source, target });
    }
  });

  if (nodes.length === 0) {
    graphEdges.push({ source: "START", target: "END" });
  } else {
    const incoming = new Set(graphEdges.map((edge) => edge.target));
    const outgoing = new Set(graphEdges.map((edge) => edge.source));

    nodes.forEach((node) => {
      const graphName = canvasToGraph[node.id];
      if (!incoming.has(graphName)) {
        graphEdges.push({ source: "START", target: graphName });
      }
      if (!outgoing.has(graphName)) {
        graphEdges.push({ source: graphName, target: "END" });
      }
    });
  }

  return {
    config: { nodes: graphNodes, edges: graphEdges },
    canvasToGraph,
    graphToCanvas,
  };
};
