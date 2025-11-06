import { useEffect } from "react";
import type { MutableRefObject } from "react";

import type { CanvasNode } from "@features/workflow/pages/workflow-canvas/helpers/types";

interface UseWorkflowKeybindingsParams {
  nodesRef: MutableRefObject<CanvasNode[]>;
  deleteNodes: (ids: string[]) => void;
  handleUndo: () => void;
  handleRedo: () => void;
  copySelectedNodes: () => Promise<void>;
  cutSelectedNodes: () => Promise<void>;
  pasteNodes: () => Promise<void>;
  setIsSearchOpen: (value: boolean) => void;
  setSearchMatches: (value: string[]) => void;
  setCurrentSearchIndex: (index: number) => void;
}

export function useWorkflowKeybindings({
  nodesRef,
  deleteNodes,
  handleUndo,
  handleRedo,
  copySelectedNodes,
  cutSelectedNodes,
  pasteNodes,
  setIsSearchOpen,
  setSearchMatches,
  setCurrentSearchIndex,
}: UseWorkflowKeybindingsParams) {
  useEffect(() => {
    const targetDocument =
      typeof document !== "undefined" ? document : undefined;
    if (!targetDocument) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const isEditable =
        !!target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable);

      if (
        (event.key === "Delete" || event.key === "Backspace") &&
        !isEditable
      ) {
        const selectedIds = nodesRef.current
          .filter((node) => node.selected)
          .map((node) => node.id);
        if (selectedIds.length > 0) {
          event.preventDefault();
          deleteNodes(selectedIds);
          return;
        }
      }

      if (!(event.ctrlKey || event.metaKey)) {
        return;
      }

      const key = event.key.toLowerCase();

      if ((key === "c" || key === "x" || key === "v") && isEditable) {
        return;
      }

      if (key === "c") {
        event.preventDefault();
        void copySelectedNodes();
        return;
      }

      if (key === "x") {
        event.preventDefault();
        void cutSelectedNodes();
        return;
      }

      if (key === "v") {
        event.preventDefault();
        void pasteNodes();
        return;
      }

      if (key === "f") {
        event.preventDefault();
        setIsSearchOpen(true);
        setSearchMatches([]);
        setCurrentSearchIndex(0);
        return;
      }

      if (key === "z") {
        event.preventDefault();
        if (event.shiftKey) {
          handleRedo();
        } else {
          handleUndo();
        }
        return;
      }

      if (key === "y") {
        event.preventDefault();
        handleRedo();
      }
    };

    targetDocument.addEventListener("keydown", handleKeyDown);
    return () => targetDocument.removeEventListener("keydown", handleKeyDown);
  }, [
    nodesRef,
    deleteNodes,
    handleRedo,
    handleUndo,
    copySelectedNodes,
    cutSelectedNodes,
    pasteNodes,
    setCurrentSearchIndex,
    setIsSearchOpen,
    setSearchMatches,
  ]);
}
