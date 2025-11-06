import { WORKFLOW_CLIPBOARD_HEADER } from "./constants";
import type {
  CopyClipboardOptions,
  CopyClipboardResult,
  WorkflowClipboardPayload,
} from "./types";
import type {
  WorkflowEdge as PersistedWorkflowEdge,
  WorkflowNode as PersistedWorkflowNode,
} from "@features/workflow/data/workflow-data";
import { cloneEdge, cloneNode, toPersistedEdge, toPersistedNode } from "./transforms";
import type { CanvasEdge, CanvasNode } from "./types";

export const encodeClipboardPayload = (payload: WorkflowClipboardPayload) =>
  `${WORKFLOW_CLIPBOARD_HEADER}${JSON.stringify(payload)}`;

export const decodeClipboardPayloadString = (
  serialized: string,
): WorkflowClipboardPayload | null => {
  if (typeof serialized !== "string") {
    return null;
  }
  const trimmed = serialized.trim();
  if (trimmed.length === 0) {
    return null;
  }

  const payloadString = trimmed.startsWith(WORKFLOW_CLIPBOARD_HEADER)
    ? trimmed.slice(WORKFLOW_CLIPBOARD_HEADER.length)
    : trimmed;

  try {
    const parsed = JSON.parse(
      payloadString,
    ) as Partial<WorkflowClipboardPayload>;
    if (
      parsed &&
      parsed.version === 1 &&
      parsed.type === "workflow-selection" &&
      Array.isArray(parsed.nodes) &&
      Array.isArray(parsed.edges)
    ) {
      return {
        version: 1,
        type: "workflow-selection",
        nodes: parsed.nodes as PersistedWorkflowNode[],
        edges: parsed.edges as PersistedWorkflowEdge[],
        copiedAt:
          typeof parsed.copiedAt === "number" ? parsed.copiedAt : undefined,
      };
    }
  } catch {
    return null;
  }

  return null;
};

export const buildClipboardPayload = (
  nodesToPersist: PersistedWorkflowNode[],
  edgesToPersist: PersistedWorkflowEdge[],
): WorkflowClipboardPayload => ({
  version: 1,
  type: "workflow-selection",
  nodes: nodesToPersist,
  edges: edgesToPersist,
  copiedAt: Date.now(),
});

export const signatureFromClipboardPayload = (payload: WorkflowClipboardPayload) =>
  typeof payload.copiedAt === "number"
    ? `ts:${payload.copiedAt}`
    : `ids:${payload.nodes
        .map((node) => node.id)
        .sort()
        .join("|")}`;

export const cloneSelectionNodes = (nodes: CanvasNode[]) =>
  nodes.map((node) => cloneNode(node));

export const cloneSelectionEdges = (edges: CanvasEdge[]) =>
  edges.map((edge) => cloneEdge(edge));

export const toPersistedSelectionNodes = (nodes: CanvasNode[]) =>
  nodes.map((node) => toPersistedNode(node));

export const toPersistedSelectionEdges = (edges: CanvasEdge[]) =>
  edges.map((edge) => toPersistedEdge(edge));

export const copyNodesToClipboardPayload = (
  nodesToCopy: CanvasNode[],
  edgesToCopy: CanvasEdge[],
  options: CopyClipboardOptions = {},
): CopyClipboardResult => {
  if (nodesToCopy.length === 0) {
    return {
      success: false,
      nodeCount: 0,
      edgeCount: 0,
      usedFallback: false,
    };
  }

  const nodesToPersist = toPersistedSelectionNodes(nodesToCopy);
  const edgesToPersist = toPersistedSelectionEdges(edgesToCopy);

  const payload = buildClipboardPayload(nodesToPersist, edgesToPersist);
  const encoded = encodeClipboardPayload(payload);

  try {
    if (
      !options.skipSuccessToast &&
      navigator.clipboard &&
      typeof navigator.clipboard.writeText === "function"
    ) {
      void navigator.clipboard.writeText(encoded);
    }
    return {
      success: true,
      nodeCount: nodesToCopy.length,
      edgeCount: edgesToCopy.length,
      usedFallback: false,
    };
  } catch {
    return {
      success: true,
      nodeCount: nodesToCopy.length,
      edgeCount: edgesToCopy.length,
      usedFallback: true,
    };
  }
};
