import React from "react";
import { Panel } from "@xyflow/react";

import SidebarPanel from "@features/workflow/components/panels/sidebar-panel";
import WorkflowFlow from "@features/workflow/components/canvas/workflow-flow";
import WorkflowControls from "@features/workflow/components/canvas/workflow-controls";
import WorkflowSearch from "@features/workflow/components/canvas/workflow-search";
import ConnectionValidator from "@features/workflow/components/canvas/connection-validator";
import { EdgeHoverContext } from "@features/workflow/components/canvas/edge-hover-context";

import type {
  CanvasEdge,
  CanvasNode,
  SidebarNodeDefinition,
} from "@features/workflow/pages/workflow-canvas/helpers/types";
import type { Connection } from "@xyflow/react";
import type { MutableRefObject } from "react";
import type { ValidationError } from "@features/workflow/pages/workflow-canvas/helpers/types";

type WorkflowFlowProps = React.ComponentProps<typeof WorkflowFlow>;

interface FlowHandlers extends Pick<
  WorkflowFlowProps,
  | "onNodesChange"
  | "onEdgesChange"
  | "onNodeClick"
  | "onNodeDoubleClick"
  | "onEdgeMouseEnter"
  | "onEdgeMouseLeave"
  | "onInit"
> {
  nodes: CanvasNode[];
  edges: CanvasEdge[];
  onConnect: (connection: Connection) => void;
}

interface SearchHandlers {
  isOpen: boolean;
  onSearch: (value: string) => void;
  onHighlightNext: () => void;
  onHighlightPrevious: () => void;
  onClose: () => void;
  matchCount: number;
  currentMatchIndex: number;
  className?: string;
}

interface ControlsHandlers {
  isRunning: boolean;
  onRun: () => void;
  onPause: () => void;
  onSave: () => void;
  onUndo: () => void;
  onRedo: () => void;
  canUndo: boolean;
  canRedo: boolean;
  onDuplicate: () => void;
  onExport: () => void;
  onImport: () => void;
  onToggleSearch: () => void;
  isSearchOpen: boolean;
}

interface ConnectionValidationProps {
  errors: ValidationError[];
  onDismiss: () => void;
  onFix: () => void;
}

export interface CanvasTabContentProps {
  sidebarCollapsed: boolean;
  onToggleSidebar: () => void;
  onAddNode: (node: SidebarNodeDefinition) => void;
  reactFlowWrapperRef: MutableRefObject<HTMLDivElement | null>;
  onDragOver: (event: React.DragEvent) => void;
  onDrop: (event: React.DragEvent) => void;
  edgeHoverContextValue: {
    hoveredEdgeId: string | null;
    setHoveredEdgeId: (value: string | null) => void;
  };
  flowHandlers: FlowHandlers;
  searchHandlers: SearchHandlers;
  controlsHandlers: ControlsHandlers;
  fileInputRef: React.RefObject<HTMLInputElement>;
  validation: ConnectionValidationProps;
  onFileSelected: (event: React.ChangeEvent<HTMLInputElement>) => void;
}

export function CanvasTabContent({
  sidebarCollapsed,
  onToggleSidebar,
  onAddNode,
  reactFlowWrapperRef,
  onDragOver,
  onDrop,
  edgeHoverContextValue,
  flowHandlers,
  searchHandlers,
  controlsHandlers,
  fileInputRef,
  validation,
  onFileSelected,
}: CanvasTabContentProps) {
  return (
    <div className="flex h-full min-h-0">
      <SidebarPanel
        isCollapsed={sidebarCollapsed}
        onToggleCollapse={onToggleSidebar}
        onAddNode={onAddNode}
      />

      <div
        ref={reactFlowWrapperRef}
        className="relative flex-1 h-full min-h-0"
        onDragOver={onDragOver}
        onDrop={onDrop}
      >
        <EdgeHoverContext.Provider value={edgeHoverContextValue}>
          <WorkflowFlow
            nodes={flowHandlers.nodes}
            edges={flowHandlers.edges}
            onNodesChange={flowHandlers.onNodesChange}
            onEdgesChange={flowHandlers.onEdgesChange}
            onConnect={flowHandlers.onConnect}
            onNodeClick={flowHandlers.onNodeClick}
            onNodeDoubleClick={flowHandlers.onNodeDoubleClick}
            onEdgeMouseEnter={flowHandlers.onEdgeMouseEnter}
            onEdgeMouseLeave={flowHandlers.onEdgeMouseLeave}
            onInit={flowHandlers.onInit}
            fitView
            snapToGrid
            snapGrid={[15, 15]}
            editable
          >
            <WorkflowSearch {...searchHandlers} />
            <Panel position="top-left" className="m-4">
              <WorkflowControls {...controlsHandlers} />
            </Panel>
            <input
              ref={fileInputRef}
              type="file"
              accept="application/json"
              className="hidden"
              onChange={onFileSelected}
            />
          </WorkflowFlow>
        </EdgeHoverContext.Provider>
        <ConnectionValidator
          errors={validation.errors}
          onDismiss={validation.onDismiss}
          onFix={validation.onFix}
        />
      </div>
    </div>
  );
}
