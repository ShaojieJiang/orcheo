import React from "react";

export interface EdgeHoverContextValue {
  hoveredEdgeId: string | null;
  setHoveredEdgeId: (edgeId: string | null) => void;
}

export const EdgeHoverContext =
  React.createContext<EdgeHoverContextValue | null>(null);

export const useEdgeHoverContext = () => React.useContext(EdgeHoverContext);
