import { useCallback } from "react";
import type {
  Dispatch,
  MutableRefObject,
  SetStateAction,
} from "react";

import { toast } from "@/hooks/use-toast";
import {
  cloneEdge,
  cloneNode,
} from "@features/workflow/pages/workflow-canvas/helpers/clipboard";
import {
  createIdentityAllocator,
} from "@features/workflow/pages/workflow-canvas/helpers/node-identity";
import type {
  CanvasEdge,
  CanvasNode,
  NodeData,
} from "@features/workflow/pages/workflow-canvas/helpers/types";

interface DuplicateNodesOptions {
  nodes: CanvasNode[];
  edges: CanvasEdge[];
  nodesRef: MutableRefObject<CanvasNode[]>;
  isRestoringRef: MutableRefObject<boolean>;
  recordSnapshot: (options?: { force?: boolean }) => void;
  setNodesState: Dispatch<SetStateAction<CanvasNode[]>>;
  setEdgesState: Dispatch<SetStateAction<CanvasEdge[]>>;
  handleOpenChat: (nodeId: string) => void;
}

interface DuplicateNodesHandlers {
  handleDuplicateSelectedNodes: () => void;
}

export function useWorkflowDuplicateNodes(
  options: DuplicateNodesOptions,
): DuplicateNodesHandlers {
  const {
    nodes,
    edges,
    nodesRef,
    isRestoringRef,
    recordSnapshot,
    setNodesState,
    setEdgesState,
    handleOpenChat,
  } = options;

  const handleDuplicateSelectedNodes = useCallback(() => {
    const selectedNodes = nodes.filter((node) => node.selected);
    if (selectedNodes.length === 0) {
      toast({
        title: "No nodes selected",
        description: "Select at least one node to duplicate.",
        variant: "destructive",
      });
      return;
    }

    const idMap = new Map<string, string>();
    const allocateIdentity = createIdentityAllocator(nodesRef.current);
    const duplicatedNodes = selectedNodes.map((node) => {
      const clonedNode = cloneNode(node);
      const baseLabel =
        typeof clonedNode.data?.label === "string" &&
        clonedNode.data.label.trim().length > 0
          ? `${clonedNode.data.label} Copy`
          : `${clonedNode.id} Copy`;
      const { id: newId, label } = allocateIdentity(baseLabel);
      idMap.set(node.id, newId);
      const duplicatedData: NodeData = {
        ...(clonedNode.data as NodeData),
        label,
      };
      if (clonedNode.type === "chatTrigger") {
        duplicatedData.onOpenChat = () => handleOpenChat(newId);
      }
      return {
        ...clonedNode,
        id: newId,
        position: {
          x: (clonedNode.position?.x ?? 0) + 40,
          y: (clonedNode.position?.y ?? 0) + 40,
        },
        selected: false,
        data: duplicatedData,
      } as CanvasNode;
    });

    const selectedIds = new Set(selectedNodes.map((node) => node.id));
    const duplicatedEdges = edges
      .filter(
        (edge) => selectedIds.has(edge.source) && selectedIds.has(edge.target),
      )
      .map((edge) => {
        const sourceId = idMap.get(edge.source);
        const targetId = idMap.get(edge.target);
        if (!sourceId || !targetId) {
          return null;
        }
        const clonedEdge = cloneEdge(edge);
        return {
          ...clonedEdge,
          id: `edge-${sourceId}-${targetId}-${Math.random()
            .toString(36)
            .slice(2, 8)}`,
          source: sourceId,
          target: targetId,
          selected: false,
        } as CanvasEdge;
      })
      .filter(Boolean) as CanvasEdge[];

    isRestoringRef.current = true;
    recordSnapshot({ force: true });
    try {
      setNodesState((current) => [...current, ...duplicatedNodes]);
      if (duplicatedEdges.length > 0) {
        setEdgesState((current) => [...current, ...duplicatedEdges]);
      }
    } catch (error) {
      isRestoringRef.current = false;
      throw error;
    }

    toast({
      title: "Nodes duplicated",
      description: `${duplicatedNodes.length} node${
        duplicatedNodes.length === 1 ? "" : "s"
      } copied with their connections.`,
    });
  }, [
    edges,
    handleOpenChat,
    isRestoringRef,
    nodes,
    nodesRef,
    recordSnapshot,
    setEdgesState,
    setNodesState,
  ]);

  return { handleDuplicateSelectedNodes };
}
