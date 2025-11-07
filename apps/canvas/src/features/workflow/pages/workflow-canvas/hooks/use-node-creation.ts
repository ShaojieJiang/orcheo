import { useCallback } from "react";
import type { MutableRefObject } from "react";
import type { ReactFlowInstance } from "@xyflow/react";

import {
  buildNodeBaseData,
  createStandardNode,
  createStickyNode,
} from "@features/workflow/pages/workflow-canvas/hooks/node-factory";

import type {
  CanvasEdge,
  CanvasNode,
  NodeData,
  SidebarNodeDefinition,
} from "@features/workflow/pages/workflow-canvas/helpers/types";

interface UseNodeCreationParams {
  reactFlowWrapper: MutableRefObject<HTMLDivElement | null>;
  reactFlowInstance: MutableRefObject<ReactFlowInstance<
    CanvasNode,
    CanvasEdge
  > | null>;
  nodesRef: MutableRefObject<CanvasNode[]>;
  setNodes: React.Dispatch<React.SetStateAction<CanvasNode[]>>;
  handleOpenChat: (nodeId: string) => void;
  handleUpdateStickyNoteNode: (nodeId: string, data: Partial<NodeData>) => void;
}

export function useNodeCreation({
  reactFlowWrapper,
  reactFlowInstance,
  nodesRef,
  setNodes,
  handleOpenChat,
  handleUpdateStickyNoteNode,
}: UseNodeCreationParams) {
  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  const handleAddNode = useCallback(
    (node: SidebarNodeDefinition) => {
      if (!reactFlowInstance.current) {
        return;
      }

      const base = buildNodeBaseData(node, nodesRef);
      if (base.nodeType === "stickyNote") {
        const position = {
          x: Math.random() * 300 + 100,
          y: Math.random() * 300 + 100,
        };
        const stickyNode = createStickyNode(
          base,
          position,
          handleUpdateStickyNoteNode,
        );
        setNodes((nodes) => [...nodes, stickyNode]);
        return;
      }

      const position = {
        x: Math.random() * 300 + 100,
        y: Math.random() * 300 + 100,
      };
      const newNode = createStandardNode(base, position, handleOpenChat);
      setNodes((nodes) => [...nodes, newNode]);
    },
    [
      handleOpenChat,
      handleUpdateStickyNoteNode,
      nodesRef,
      reactFlowInstance,
      setNodes,
    ],
  );

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();

      if (!reactFlowWrapper.current || !reactFlowInstance.current) {
        return;
      }

      const bounds = reactFlowWrapper.current.getBoundingClientRect();
      const raw = event.dataTransfer.getData("application/reactflow");
      if (!raw) {
        return;
      }

      try {
        const node = JSON.parse(raw) as SidebarNodeDefinition;
        const position = reactFlowInstance.current.project({
          x: event.clientX - bounds.left,
          y: event.clientY - bounds.top,
        });
        const base = buildNodeBaseData(node, nodesRef);

        if (base.nodeType === "stickyNote") {
          const stickyNode = createStickyNode(
            base,
            position,
            handleUpdateStickyNoteNode,
          );
          setNodes((nodes) => nodes.concat(stickyNode));
          return;
        }

        const newNode = createStandardNode(base, position, handleOpenChat);
        setNodes((nodes) => nodes.concat(newNode));
      } catch (error) {
        console.error("Error adding new node:", error);
      }
    },
    [
      handleOpenChat,
      handleUpdateStickyNoteNode,
      nodesRef,
      reactFlowInstance,
      reactFlowWrapper,
      setNodes,
    ],
  );

  return {
    onDragOver,
    onDrop,
    handleAddNode,
  };
}
