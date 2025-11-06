import { useCallback } from "react";

import type { StickyNoteNodeData } from "@features/workflow/components/nodes/sticky-note-node";
import {
  DEFAULT_STICKY_NOTE_COLOR,
  DEFAULT_STICKY_NOTE_HEIGHT,
  DEFAULT_STICKY_NOTE_WIDTH,
  STICKY_NOTE_MIN_HEIGHT,
  STICKY_NOTE_MIN_WIDTH,
  isStickyNoteColor,
  sanitizeStickyNoteContent,
  sanitizeStickyNoteDimension,
} from "@features/workflow/pages/workflow-canvas/helpers/sticky-notes";
import type {
  CanvasNode,
  NodeData,
} from "@features/workflow/pages/workflow-canvas/helpers/types";

type UseWorkflowStickyNotesArgs = {
  setNodes: React.Dispatch<React.SetStateAction<CanvasNode[]>>;
};

export const useWorkflowStickyNotes = ({
  setNodes,
}: UseWorkflowStickyNotesArgs) => {
  const handleUpdateStickyNoteNode = useCallback(
    (
      nodeId: string,
      updates: Partial<
        Pick<StickyNoteNodeData, "color" | "content" | "width" | "height">
      >,
    ) => {
      setNodes((nodes) =>
        nodes.map((node) => {
          if (node.id !== nodeId) {
            return node;
          }

          const sanitizedUpdates: Record<string, unknown> = {};

          if ("color" in updates) {
            sanitizedUpdates.color = isStickyNoteColor(updates.color)
              ? updates.color
              : DEFAULT_STICKY_NOTE_COLOR;
          }

          if ("content" in updates && typeof updates.content === "string") {
            sanitizedUpdates.content = sanitizeStickyNoteContent(
              updates.content,
            );
          }

          if ("width" in updates && typeof updates.width === "number") {
            sanitizedUpdates.width = sanitizeStickyNoteDimension(
              updates.width,
              DEFAULT_STICKY_NOTE_WIDTH,
              STICKY_NOTE_MIN_WIDTH,
            );
          }

          if ("height" in updates && typeof updates.height === "number") {
            sanitizedUpdates.height = sanitizeStickyNoteDimension(
              updates.height,
              DEFAULT_STICKY_NOTE_HEIGHT,
              STICKY_NOTE_MIN_HEIGHT,
            );
          }

          if (Object.keys(sanitizedUpdates).length === 0) {
            return node;
          }

          return {
            ...node,
            data: {
              ...(node.data as NodeData),
              ...sanitizedUpdates,
            },
          };
        }),
      );
    },
    [setNodes],
  );

  return {
    handleUpdateStickyNoteNode,
  };
};
