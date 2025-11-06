import { toast } from "@/hooks/use-toast";
import {
  buildClipboardPayload,
  encodeClipboardPayload,
  signatureFromClipboardPayload,
} from "@features/workflow/pages/workflow-canvas/helpers/clipboard";
import {
  toPersistedEdge,
  toPersistedNode,
} from "@features/workflow/pages/workflow-canvas/helpers/transformers";
import type {
  CanvasEdge,
  CanvasNode,
  CopyClipboardOptions,
  CopyClipboardResult,
  WorkflowClipboardPayload,
} from "@features/workflow/pages/workflow-canvas/helpers/types";

interface CopySelectionOptions {
  nodesToCopy: CanvasNode[];
  edges: CanvasEdge[];
  copyOptions?: CopyClipboardOptions;
}

interface CopySelectionResult {
  result: CopyClipboardResult;
  payload: WorkflowClipboardPayload;
  signature: string;
}

export async function copySelectionToClipboard(
  options: CopySelectionOptions,
): Promise<CopySelectionResult | null> {
  const { nodesToCopy, edges, copyOptions = {} } = options;

  if (nodesToCopy.length === 0) {
    toast({
      title: "No nodes selected",
      description: "Select at least one node to copy.",
      variant: "destructive",
    });
    return null;
  }

  const selectedIds = new Set(nodesToCopy.map((node) => node.id));
  const persistedNodes = nodesToCopy.map(toPersistedNode);
  const persistedEdges = edges
    .filter(
      (edge) => selectedIds.has(edge.source) && selectedIds.has(edge.target),
    )
    .map(toPersistedEdge);

  const payload = buildClipboardPayload(persistedNodes, persistedEdges);
  const signature = signatureFromClipboardPayload(payload);

  let systemClipboardCopied = false;

  if (
    typeof navigator !== "undefined" &&
    navigator.clipboard &&
    typeof navigator.clipboard.writeText === "function"
  ) {
    try {
      await navigator.clipboard.writeText(encodeClipboardPayload(payload));
      systemClipboardCopied = true;
    } catch (error) {
      console.warn("Failed to write workflow selection to clipboard", error);
    }
  }

  if (!copyOptions.skipSuccessToast) {
    toast({
      title: nodesToCopy.length === 1 ? "Node copied" : "Nodes copied",
      description: `${nodesToCopy.length} node${
        nodesToCopy.length === 1 ? "" : "s"
      } copied${systemClipboardCopied ? "" : " (available for in-app paste)"}.`,
    });
  } else if (!systemClipboardCopied) {
    toast({
      title: "Nodes copied (in-app clipboard)",
      description:
        "System clipboard unavailable. Paste with Ctrl/Cmd+V in this tab.",
    });
  }

  return {
    payload,
    signature,
    result: {
      success: true,
      nodeCount: nodesToCopy.length,
      edgeCount: persistedEdges.length,
      usedFallback: !systemClipboardCopied,
    },
  };
}
