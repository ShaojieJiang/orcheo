import {
  PASTE_BASE_OFFSET,
  PASTE_OFFSET_INCREMENT,
  PASTE_OFFSET_MAX_STEPS,
} from "@features/workflow/pages/workflow-canvas/helpers/clipboard";
import { generateRandomId } from "@features/workflow/pages/workflow-canvas/helpers/id";
import {
  createIdentityAllocator,
  sanitizeLabel,
} from "@features/workflow/pages/workflow-canvas/helpers/node-identity";
import type {
  CanvasEdge,
  CanvasNode,
  WorkflowClipboardPayload,
} from "@features/workflow/pages/workflow-canvas/helpers/types";
import type {
  WorkflowEdge as PersistedWorkflowEdge,
  WorkflowNode as PersistedWorkflowNode,
} from "@features/workflow/data/workflow-data";

interface PreparePasteOptions {
  payload: WorkflowClipboardPayload;
  existingNodes: CanvasNode[];
  pasteStep: number;
  convertPersistedNodesToCanvas: (
    nodes: PersistedWorkflowNode[],
  ) => CanvasNode[];
  convertPersistedEdgesToCanvas: (
    edges: PersistedWorkflowEdge[],
  ) => CanvasEdge[];
}

interface PreparePasteResult {
  nodes: CanvasNode[];
  edges: CanvasEdge[];
  nextStep: number;
}

export function preparePasteSelection(
  options: PreparePasteOptions,
): PreparePasteResult | null {
  const {
    payload,
    existingNodes,
    pasteStep,
    convertPersistedNodesToCanvas,
    convertPersistedEdgesToCanvas,
  } = options;

  if (payload.nodes.length === 0) {
    return null;
  }

  const offset = PASTE_BASE_OFFSET + pasteStep * PASTE_OFFSET_INCREMENT;
  const nextStep = Math.min(pasteStep + 1, PASTE_OFFSET_MAX_STEPS);
  const idMap = new Map<string, string>();
  const allocateIdentity = createIdentityAllocator(existingNodes);

  const remappedNodes = payload.nodes.map((node) => {
    const baseLabel =
      typeof node.data?.label === "string" && node.data.label.trim().length > 0
        ? node.data.label
        : sanitizeLabel(node.id);
    const { id: newId, label } = allocateIdentity(baseLabel);
    idMap.set(node.id, newId);
    const position = node.position ?? { x: 0, y: 0 };
    return {
      ...node,
      id: newId,
      position: {
        x: position.x + offset,
        y: position.y + offset,
      },
      data: {
        ...node.data,
        label,
      },
    };
  });

  const remappedEdges = payload.edges
    .map((edge) => {
      const sourceId = idMap.get(edge.source);
      const targetId = idMap.get(edge.target);
      if (!sourceId || !targetId) {
        return null;
      }
      return {
        ...edge,
        id: generateRandomId("edge"),
        source: sourceId,
        target: targetId,
      };
    })
    .filter(Boolean) as PersistedWorkflowEdge[];

  const canvasNodes = convertPersistedNodesToCanvas(remappedNodes);
  const canvasEdges = convertPersistedEdgesToCanvas(remappedEdges);

  if (canvasNodes.length === 0) {
    return null;
  }

  return {
    nodes: canvasNodes,
    edges: canvasEdges,
    nextStep,
  };
}
