import { useMemo } from "react";

import type {
  StickyNoteColor,
  StickyNoteNodeData,
} from "@features/workflow/components/nodes/sticky-note-node";
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

type UseDecoratedNodesArgs = {
  nodes: CanvasNode[];
  isSearchOpen: boolean;
  searchMatchSet: Set<string>;
  searchMatches: string[];
  currentSearchIndex: number;
  handleDeleteNode: (id: string) => void;
  handleUpdateStickyNoteNode: (
    id: string,
    updates: Partial<
      Pick<StickyNoteNodeData, "color" | "content" | "width" | "height">
    >,
  ) => void;
};

export const useDecoratedNodes = ({
  nodes,
  isSearchOpen,
  searchMatchSet,
  searchMatches,
  currentSearchIndex,
  handleDeleteNode,
  handleUpdateStickyNoteNode,
}: UseDecoratedNodesArgs) => {
  return useMemo(() => {
    return nodes.map((node) => {
      const isMatch = searchMatchSet.has(node.id);
      const isActive =
        isMatch &&
        isSearchOpen &&
        searchMatches[currentSearchIndex] === node.id;
      const isStickyNoteNode = node.type === "stickyNote";

      const baseData = {
        ...node.data,
        onDelete: handleDeleteNode,
        ...(isStickyNoteNode
          ? { onUpdateStickyNote: handleUpdateStickyNoteNode }
          : {}),
      } as NodeData & Record<string, unknown>;

      const augmentedData = isStickyNoteNode
        ? ({
            ...baseData,
            label:
              typeof baseData.label === "string" && baseData.label.length > 0
                ? baseData.label
                : "Sticky Note",
            color: isStickyNoteColor(baseData.color)
              ? (baseData.color as StickyNoteColor)
              : DEFAULT_STICKY_NOTE_COLOR,
            content: sanitizeStickyNoteContent(baseData.content),
            width: sanitizeStickyNoteDimension(
              baseData.width,
              DEFAULT_STICKY_NOTE_WIDTH,
              STICKY_NOTE_MIN_WIDTH,
            ),
            height: sanitizeStickyNoteDimension(
              baseData.height,
              DEFAULT_STICKY_NOTE_HEIGHT,
              STICKY_NOTE_MIN_HEIGHT,
            ),
            onUpdateStickyNote: handleUpdateStickyNoteNode,
          } as NodeData)
        : baseData;

      const decoratedData = !isSearchOpen
        ? {
            ...augmentedData,
            isSearchMatch: false,
            isSearchActive: false,
          }
        : {
            ...augmentedData,
            isSearchMatch: isMatch,
            isSearchActive: isActive,
          };

      return {
        ...node,
        data: decoratedData,
        ...(isStickyNoteNode ? { connectable: false } : {}),
      };
    });
  }, [
    currentSearchIndex,
    handleDeleteNode,
    handleUpdateStickyNoteNode,
    isSearchOpen,
    nodes,
    searchMatchSet,
    searchMatches,
  ]);
};
