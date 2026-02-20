import { useState } from "react";

export function useCanvasUiState() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("workflow");
  const [hoveredEdgeId, setHoveredEdgeId] = useState<string | null>(null);

  return {
    sidebarCollapsed,
    setSidebarCollapsed,
    selectedNodeId,
    setSelectedNodeId,
    activeTab,
    setActiveTab,
    hoveredEdgeId,
    setHoveredEdgeId,
  };
}
