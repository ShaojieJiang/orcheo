import { useEffect } from "react";
import type { MutableRefObject } from "react";

import type { CanvasNode } from "@features/workflow/pages/workflow-canvas/helpers/types";

const isEditableTarget = (target: EventTarget | null): boolean => {
  if (!(target instanceof HTMLElement)) {
    return false;
  }

  return (
    target.tagName === "INPUT" ||
    target.tagName === "TEXTAREA" ||
    target.isContentEditable ||
    target.closest(
      "[contenteditable=''], [contenteditable='true'], [contenteditable='plaintext-only']",
    ) !== null
  );
};

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

export function useWorkflowKeybindings(params: UseWorkflowKeybindingsParams) {
  const {
    nodesRef,
    deleteNodes,
    handleUndo,
    handleRedo,
    setIsSearchOpen,
    setSearchMatches,
    setCurrentSearchIndex,
  } = params;

  useEffect(() => {
    const targetDocument =
      typeof document !== "undefined" ? document : undefined;
    if (!targetDocument) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      const isEditable = isEditableTarget(event.target);

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

      if (key === "c" || key === "x" || key === "v") {
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
    setCurrentSearchIndex,
    setIsSearchOpen,
    setSearchMatches,
  ]);
}
