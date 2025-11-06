import type {
  CanvasEdge,
  CanvasNode,
  WorkflowClipboardPayload,
} from "./types";
import {
  toPersistedEdge,
  toPersistedNode,
} from "./transformers";

export const WORKFLOW_CLIPBOARD_HEADER = "ORCHEO_WORKFLOW_CLIPBOARD_V1:";
export const PASTE_BASE_OFFSET = 40;
export const PASTE_OFFSET_INCREMENT = 24;
export const PASTE_OFFSET_MAX_STEPS = 5;

export const encodeClipboardPayload = (
  payload: WorkflowClipboardPayload,
) => `${WORKFLOW_CLIPBOARD_HEADER}${JSON.stringify(payload)}`;

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
        nodes: parsed.nodes,
        edges: parsed.edges,
        copiedAt:
          typeof parsed.copiedAt === "number" ? parsed.copiedAt : undefined,
      } as WorkflowClipboardPayload;
    }
  } catch {
    return null;
  }

  return null;
};

export const buildClipboardPayload = (
  nodesToPersist: ReturnType<typeof toPersistedNode>[],
  edgesToPersist: ReturnType<typeof toPersistedEdge>[],
): WorkflowClipboardPayload => ({
  version: 1,
  type: "workflow-selection",
  nodes: nodesToPersist,
  edges: edgesToPersist,
  copiedAt: Date.now(),
});

export const signatureFromClipboardPayload = (
  payload: WorkflowClipboardPayload,
) =>
  typeof payload.copiedAt === "number"
    ? `ts:${payload.copiedAt}`
    : `ids:${payload.nodes
        .map((node) => node.id)
        .sort()
        .join("|")}`;

export const cloneNode = (node: CanvasNode): CanvasNode => ({
  ...node,
  position: node.position ? { ...node.position } : node.position,
  data: node.data ? { ...node.data } : node.data,
});

export const cloneEdge = (edge: CanvasEdge): CanvasEdge => ({
  ...edge,
  data: edge.data ? { ...edge.data } : edge.data,
});
