import type { Edge, Node } from "@xyflow/react";
import { DEFAULT_PYTHON_CODE } from "@features/workflow/lib/python-node";

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

  const getBackendType = (node: CanvasNode): string | undefined => {
    const data = node.data ?? {};
    const raw = data?.backendType;
    if (typeof raw === "string" && raw.trim().length > 0) {
      return raw.trim();
    }
    return undefined;
  };

  nodes.forEach((node, index) => {
    const label = String(node.data?.label ?? node.id ?? `node-${index + 1}`);
    const base = slugify(label, `node-${index + 1}`);
    const unique = ensureUniqueName(base, usedNames);
    canvasToGraph[node.id] = unique;
    graphToCanvas[unique] = node.id;
  });

  const graphNodes: Array<Record<string, unknown>> = [
    { name: "START", type: "START" },
    ...nodes.map((node, index) => {
      const data = node.data ?? {};
      const semanticTypeRaw =
        typeof data?.type === "string" ? data.type.toLowerCase() : undefined;
      const defaultCode =
        semanticTypeRaw === "python" ? DEFAULT_PYTHON_CODE : DEFAULT_NODE_CODE;
      const code =
        typeof data?.code === "string" && data.code.length > 0
          ? data.code
          : defaultCode;

      const backendType = getBackendType(node) ?? "PythonCode";

      const nodeConfig: Record<string, unknown> = {
        name: canvasToGraph[node.id],
        type: backendType,
        display_name: node.data?.label ?? node.id ?? `Node ${index + 1}`,
        canvas_id: node.id,
      };

      if (backendType === "PythonCode") {
        nodeConfig.code = code;
      }

      if (backendType === "IfElseNode") {
        nodeConfig.left = data?.left ?? null;
        nodeConfig.right = data?.right ?? null;
        nodeConfig.operator = data?.operator ?? "equals";
        nodeConfig.case_sensitive = data?.caseSensitive ?? true;
      }

      if (backendType === "SwitchNode") {
        nodeConfig.value = data?.value ?? null;
        nodeConfig.case_sensitive = data?.caseSensitive ?? true;
      }

      if (backendType === "WhileNode") {
        nodeConfig.left = data?.left ?? null;
        nodeConfig.right = data?.right ?? null;
        nodeConfig.operator = data?.operator ?? "less_than";
        nodeConfig.case_sensitive = data?.caseSensitive ?? true;
        if (typeof data?.maxIterations === "number") {
          nodeConfig.max_iterations = data.maxIterations;
        }
      }

      if (backendType === "SetVariableNode") {
        nodeConfig.target_path = data?.targetPath ?? "context.value";
        nodeConfig.value = data?.value ?? null;
      }

      if (backendType === "DelayNode") {
        const delayValue = data?.durationSeconds;
        const parsed =
          typeof delayValue === "number" ? delayValue : Number(delayValue ?? 0);
        nodeConfig.duration_seconds = Number.isFinite(parsed) ? parsed : 0;
      }

      if (backendType === "StickyNoteNode") {
        nodeConfig.title = data?.title ?? nodeConfig.display_name;
        nodeConfig.body = data?.content ?? "";
      }

      return nodeConfig;
    }),
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
