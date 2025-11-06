import { useCallback, useRef } from "react";
import type {
  Dispatch,
  MutableRefObject,
  SetStateAction,
} from "react";

import { toast } from "@/hooks/use-toast";
import {
  decodeClipboardPayloadString,
  signatureFromClipboardPayload,
} from "@features/workflow/pages/workflow-canvas/helpers/clipboard";
import type {
  CanvasEdge,
  CanvasNode,
  CopyClipboardResult,
  WorkflowClipboardPayload,
} from "@features/workflow/pages/workflow-canvas/helpers/types";
import type {
  WorkflowEdge as PersistedWorkflowEdge,
  WorkflowNode as PersistedWorkflowNode,
} from "@features/workflow/data/workflow-data";

import { copySelectionToClipboard } from "./workflow-clipboard-copy";
import { preparePasteSelection } from "./workflow-clipboard-paste";

interface WorkflowClipboardOptions {
  nodesRef: MutableRefObject<CanvasNode[]>;
  edgesRef: MutableRefObject<CanvasEdge[]>;
  recordSnapshot: (options?: { force?: boolean }) => void;
  setNodesState: Dispatch<SetStateAction<CanvasNode[]>>;
  setEdgesState: Dispatch<SetStateAction<CanvasEdge[]>>;
  deleteNodes: (
    ids: string[],
    options?: { suppressToast?: boolean },
  ) => void;
  isRestoringRef: MutableRefObject<boolean>;
  convertPersistedNodesToCanvas: (
    nodes: PersistedWorkflowNode[],
  ) => CanvasNode[];
  convertPersistedEdgesToCanvas: (
    edges: PersistedWorkflowEdge[],
  ) => CanvasEdge[];
}

interface WorkflowClipboardHandlers {
  copySelectedNodes: () => Promise<CopyClipboardResult>;
  cutSelectedNodes: () => Promise<void>;
  pasteNodes: () => Promise<void>;
}

const EMPTY_RESULT: CopyClipboardResult = {
  success: false,
  nodeCount: 0,
  edgeCount: 0,
  usedFallback: false,
};

export function useWorkflowClipboard(
  options: WorkflowClipboardOptions,
): WorkflowClipboardHandlers {
  const {
    nodesRef,
    edgesRef,
    recordSnapshot,
    setNodesState,
    setEdgesState,
    deleteNodes,
    isRestoringRef,
    convertPersistedNodesToCanvas,
    convertPersistedEdgesToCanvas,
  } = options;

  const clipboardRef = useRef<WorkflowClipboardPayload | null>(null);
  const pasteOffsetStepRef = useRef(0);
  const lastClipboardSignatureRef = useRef<string | null>(null);

  const copySelectedNodes = useCallback(async () => {
    const nodesToCopy = nodesRef.current.filter((node) => node.selected);
    const copyResult = await copySelectionToClipboard({
      nodesToCopy,
      edges: edgesRef.current,
    });

    if (!copyResult) {
      return EMPTY_RESULT;
    }

    clipboardRef.current = copyResult.payload;
    pasteOffsetStepRef.current = 0;
    lastClipboardSignatureRef.current = copyResult.signature;

    return copyResult.result;
  }, [edgesRef, nodesRef]);

  const cutSelectedNodes = useCallback(async () => {
    const nodesToCut = nodesRef.current.filter((node) => node.selected);
    const nodeIds = nodesToCut.map((node) => node.id);
    const copyResult = await copySelectionToClipboard({
      nodesToCopy: nodesToCut,
      edges: edgesRef.current,
      copyOptions: { skipSuccessToast: true },
    });

    if (!copyResult) {
      return;
    }

    clipboardRef.current = copyResult.payload;
    pasteOffsetStepRef.current = 0;
    lastClipboardSignatureRef.current = copyResult.signature;

    deleteNodes(nodeIds, { suppressToast: true });

    const fallbackNote = copyResult.result.usedFallback
      ? "System clipboard unavailable. Paste with Ctrl/Cmd+V in this tab."
      : "Paste with Ctrl/Cmd+V.";

    toast({
      title: nodeIds.length === 1 ? "Node cut" : "Nodes cut",
      description: `${nodeIds.length} node${
        nodeIds.length === 1 ? "" : "s"
      } ready to paste. ${fallbackNote}`,
    });
  }, [deleteNodes, edgesRef, nodesRef]);

  const pasteNodes = useCallback(async () => {
    let payload: WorkflowClipboardPayload | null = null;

    if (
      typeof navigator !== "undefined" &&
      navigator.clipboard &&
      typeof navigator.clipboard.readText === "function"
    ) {
      try {
        const clipboardText = await navigator.clipboard.readText();
        const parsed = decodeClipboardPayloadString(clipboardText);
        if (parsed) {
          payload = parsed;
        }
      } catch (error) {
        // Ignore read failures and rely on in-app clipboard.
      }
    }

    if (!payload) {
      payload = clipboardRef.current;
    }

    if (!payload || payload.nodes.length === 0) {
      toast({
        title: "Nothing to paste",
        description: "Copy nodes before pasting.",
        variant: "destructive",
      });
      return;
    }

    const signature = signatureFromClipboardPayload(payload);
    if (signature !== lastClipboardSignatureRef.current) {
      pasteOffsetStepRef.current = 0;
      lastClipboardSignatureRef.current = signature;
    }

    clipboardRef.current = payload;

    const preparation = preparePasteSelection({
      payload,
      existingNodes: nodesRef.current,
      pasteStep: pasteOffsetStepRef.current,
      convertPersistedNodesToCanvas,
      convertPersistedEdgesToCanvas,
    });

    if (!preparation) {
      toast({
        title: "Nothing to paste",
        description: "Copied selection has no nodes.",
        variant: "destructive",
      });
      return;
    }

    pasteOffsetStepRef.current = preparation.nextStep;

    isRestoringRef.current = true;
    recordSnapshot({ force: true });
    try {
      setNodesState((current) => [...current, ...preparation.nodes]);
      if (preparation.edges.length > 0) {
        setEdgesState((current) => [...current, ...preparation.edges]);
      }
    } catch (error) {
      isRestoringRef.current = false;
      throw error;
    }

    const edgeCount = preparation.edges.length;
    const connectionsNote =
      edgeCount > 0
        ? ` with ${edgeCount} connection${edgeCount === 1 ? "" : "s"}`
        : "";

    toast({
      title:
        preparation.nodes.length === 1 ? "Node pasted" : "Nodes pasted",
      description: `Added ${preparation.nodes.length} node${
        preparation.nodes.length === 1 ? "" : "s"
      }${connectionsNote}.`,
    });
  }, [
    convertPersistedEdgesToCanvas,
    convertPersistedNodesToCanvas,
    isRestoringRef,
    nodesRef,
    recordSnapshot,
    setEdgesState,
    setNodesState,
  ]);

  return {
    copySelectedNodes,
    cutSelectedNodes,
    pasteNodes,
  };
}
