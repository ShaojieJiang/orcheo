import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactFlowInstance } from "@xyflow/react";

import type {
  CanvasEdge,
  CanvasNode,
} from "@features/workflow/pages/workflow-canvas/helpers/types";

type UseWorkflowSearchArgs = {
  nodesRef: React.MutableRefObject<CanvasNode[]>;
  reactFlowInstance: React.MutableRefObject<
    ReactFlowInstance<CanvasNode, CanvasEdge> | null
  >;
};

export const useWorkflowSearch = ({
  nodesRef,
  reactFlowInstance,
}: UseWorkflowSearchArgs) => {
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [searchMatches, setSearchMatches] = useState<string[]>([]);
  const [currentSearchIndex, setCurrentSearchIndex] = useState(0);

  const searchMatchSet = useMemo(
    () => new Set(searchMatches),
    [searchMatches],
  );

  const highlightMatch = useCallback(
    (index: number) => {
      const instance = reactFlowInstance.current;
      if (!instance) {
        return;
      }

      const nodeId = searchMatches[index];
      if (!nodeId) {
        return;
      }

      const node = instance.getNode(nodeId);
      if (!node) {
        return;
      }

      const position = node.positionAbsolute ?? node.position;
      const width = node.measured?.width ?? node.width ?? 180;
      const height = node.measured?.height ?? node.height ?? 120;

      const centerX = (position?.x ?? 0) + width / 2;
      const centerY = (position?.y ?? 0) + height / 2;

      const zoomLevel =
        typeof instance.getZoom === "function"
          ? Math.max(instance.getZoom(), 1.2)
          : 1.2;

      instance.setCenter(centerX, centerY, {
        zoom: zoomLevel,
        duration: 300,
      });
    },
    [reactFlowInstance, searchMatches],
  );

  const handleSearchNodes = useCallback(
    (query: string) => {
      const normalized = query.trim().toLowerCase();

      if (!normalized) {
        setSearchMatches([]);
        setCurrentSearchIndex(0);
        return;
      }

      const matches = nodesRef.current
        .filter((node) => {
          const label = String(node.data?.label ?? "").toLowerCase();
          const description = String(node.data?.description ?? "").toLowerCase();
          return (
            label.includes(normalized) ||
            description.includes(normalized) ||
            node.id.toLowerCase().includes(normalized)
          );
        })
        .map((node) => node.id);

      setSearchMatches(matches);
      setCurrentSearchIndex(matches.length > 0 ? 0 : 0);
    },
    [nodesRef],
  );

  const handleHighlightNext = useCallback(() => {
    if (searchMatches.length === 0) {
      return;
    }
    setCurrentSearchIndex((index) => (index + 1) % searchMatches.length);
  }, [searchMatches]);

  const handleHighlightPrevious = useCallback(() => {
    if (searchMatches.length === 0) {
      return;
    }
    setCurrentSearchIndex(
      (index) => (index - 1 + searchMatches.length) % searchMatches.length,
    );
  }, [searchMatches]);

  const handleCloseSearch = useCallback(() => {
    setIsSearchOpen(false);
    setSearchMatches([]);
    setCurrentSearchIndex(0);
  }, []);

  const handleToggleSearch = useCallback(() => {
    setIsSearchOpen((previous) => {
      const next = !previous;
      setSearchMatches([]);
      setCurrentSearchIndex(0);
      return next;
    });
  }, []);

  useEffect(() => {
    if (!isSearchOpen) {
      return;
    }

    if (searchMatches.length === 0) {
      return;
    }

    const safeIndex = Math.min(
      currentSearchIndex,
      Math.max(searchMatches.length - 1, 0),
    );

    if (safeIndex !== currentSearchIndex) {
      setCurrentSearchIndex(safeIndex);
      return;
    }

    highlightMatch(safeIndex);
  }, [
    currentSearchIndex,
    highlightMatch,
    isSearchOpen,
    searchMatches,
    setCurrentSearchIndex,
  ]);

  return {
    isSearchOpen,
    setIsSearchOpen,
    searchMatches,
    setSearchMatches,
    currentSearchIndex,
    setCurrentSearchIndex,
    searchMatchSet,
    handleSearchNodes,
    handleHighlightNext,
    handleHighlightPrevious,
    handleCloseSearch,
    handleToggleSearch,
  };
};
